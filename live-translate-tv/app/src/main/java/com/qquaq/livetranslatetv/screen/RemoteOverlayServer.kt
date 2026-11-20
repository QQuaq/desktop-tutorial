package com.qquaq.livetranslatetv.screen

import android.graphics.Color
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.net.InetAddress
import java.net.NetworkInterface
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketException
import java.util.concurrent.Executors

/** A box received over the network, in normalised (0..1) screen coordinates. */
data class RemoteBox(
    val x: Float,
    val y: Float,
    val w: Float,
    val h: Float,
    val text: String,
    val lines: Int,
    val background: Int,
    val foreground: Int,
)

data class RemoteFrame(val boxes: List<RemoteBox>, val ttlMs: Long)

/**
 * Minimal LAN HTTP endpoint so another device (PC or phone reading PS5 Remote Play, capture card, …)
 * can push already-translated text for the TV overlay. Protocol: see README "Ağdan çeviri alıcı".
 */
class RemoteOverlayServer(
    private val port: Int,
    private val token: String,
    private val screenSize: () -> Pair<Int, Int>,
    private val onFrame: (RemoteFrame) -> Unit,
    private val onClear: () -> Unit,
    private val status: () -> JSONObject,
) {
    private val pool = Executors.newFixedThreadPool(3)
    @Volatile private var socket: ServerSocket? = null

    fun start() {
        val server = ServerSocket(port, 16, InetAddress.getByName("0.0.0.0")).apply { reuseAddress = true }
        socket = server
        pool.execute {
            while (!server.isClosed) {
                val client = try {
                    server.accept()
                } catch (_: SocketException) {
                    break
                }
                pool.execute { handle(client) }
            }
        }
    }

    fun stop() {
        runCatching { socket?.close() }
        pool.shutdownNow()
    }

    private fun handle(client: Socket) = client.use { s ->
        s.soTimeout = 5000
        val response = try {
            val request = readRequest(s.getInputStream())
            route(request)
        } catch (e: BadRequest) {
            Response(400, JSONObject().put("error", e.message))
        } catch (e: Exception) {
            Log.w(TAG, "request failed", e)
            Response(500, JSONObject().put("error", e.javaClass.simpleName))
        }
        val body = response.json.toString().toByteArray(Charsets.UTF_8)
        val head = buildString {
            append("HTTP/1.1 ${response.code} ${reason(response.code)}\r\n")
            append("Content-Type: application/json; charset=utf-8\r\n")
            append("Content-Length: ${body.size}\r\n")
            append("Access-Control-Allow-Origin: *\r\n")
            append("Access-Control-Allow-Headers: Content-Type, Authorization, X-Token\r\n")
            append("Access-Control-Allow-Methods: GET, POST, DELETE, OPTIONS\r\n")
            append("Connection: close\r\n\r\n")
        }
        s.getOutputStream().apply {
            write(head.toByteArray(Charsets.US_ASCII))
            write(body)
            flush()
        }
    }

    private fun route(r: Request): Response {
        if (r.method == "OPTIONS") return Response(204, JSONObject())
        val path = r.path.substringBefore('?')
        if (path == "/" || path == "/ping") return Response(200, JSONObject().put("app", "live-translate-tv"))
        if (!authorised(r)) return Response(401, JSONObject().put("error", "missing or wrong token"))
        return when {
            r.method == "GET" && path == "/status" -> {
                val (w, h) = screenSize()
                Response(200, status().put("screen", JSONObject().put("width", w).put("height", h)))
            }
            r.method == "POST" && path == "/overlay" -> {
                val frame = parseFrame(JSONObject(r.body.ifBlank { "{}" }))
                onFrame(frame)
                Response(200, JSONObject().put("ok", true).put("boxes", frame.boxes.size))
            }
            (r.method == "DELETE" && path == "/overlay") || (r.method == "POST" && path == "/clear") -> {
                onClear()
                Response(200, JSONObject().put("ok", true))
            }
            else -> Response(404, JSONObject().put("error", "unknown endpoint"))
        }
    }

    private fun authorised(r: Request): Boolean {
        val header = r.headers["x-token"] ?: r.headers["authorization"]?.removePrefix("Bearer ")?.trim()
        val query = r.path.substringAfter("token=", "").substringBefore('&')
        return header == token || query == token
    }

    private fun parseFrame(json: JSONObject): RemoteFrame {
        val (sw, sh) = screenSize()
        val pixels = json.optString("coords", "normalized").startsWith("pix")
        val ttl = json.optLong("ttlMs", DEFAULT_TTL_MS).coerceIn(0, 10 * 60_000)
        val boxes = mutableListOf<RemoteBox>()
        json.optString("subtitle").takeIf { it.isNotBlank() }?.let {
            boxes += RemoteBox(0.1f, 0.80f, 0.8f, 0.09f, it.trim(), 1, Color.argb(220, 0, 0, 0), Color.WHITE)
        }
        val array = json.optJSONArray("boxes") ?: JSONArray()
        if (array.length() > MAX_BOXES) throw BadRequest("too many boxes (max $MAX_BOXES)")
        for (i in 0 until array.length()) {
            val b = array.getJSONObject(i)
            val text = b.optString("text").trim()
            if (text.isEmpty()) continue
            fun coord(key: String, size: Int): Float {
                if (!b.has(key)) throw BadRequest("box $i: missing '$key'")
                val v = b.getDouble(key).toFloat()
                return (if (pixels) v / size else v).coerceIn(0f, 1f)
            }
            boxes += RemoteBox(
                x = coord("x", sw), y = coord("y", sh), w = coord("w", sw), h = coord("h", sh),
                text = text,
                lines = b.optInt("lines", 1).coerceIn(1, 20),
                background = parseColor(b.optString("bg"), Color.argb(230, 0, 0, 0)),
                foreground = parseColor(b.optString("fg"), Color.WHITE),
            )
        }
        return RemoteFrame(boxes, ttl)
    }

    private fun parseColor(value: String, fallback: Int) =
        if (value.isBlank()) fallback else runCatching { Color.parseColor(value) }.getOrElse { fallback }

    private fun readRequest(input: InputStream): Request {
        val head = ByteArrayOutputStream()
        var matched = 0
        while (matched < 4) {
            val b = input.read()
            if (b < 0) throw BadRequest("connection closed")
            head.write(b)
            if (head.size() > MAX_HEADER) throw BadRequest("header too large")
            matched = when {
                (matched == 0 || matched == 2) && b == '\r'.code -> matched + 1
                (matched == 1 || matched == 3) && b == '\n'.code -> matched + 1
                b == '\r'.code -> 1
                else -> 0
            }
        }
        val lines = head.toString(Charsets.US_ASCII.name()).split("\r\n")
        val parts = lines.first().split(' ')
        if (parts.size < 2) throw BadRequest("bad request line")
        val headers = lines.drop(1).filter { ':' in it }.associate {
            it.substringBefore(':').trim().lowercase() to it.substringAfter(':').trim()
        }
        val length = headers["content-length"]?.toIntOrNull() ?: 0
        if (length > MAX_BODY) throw BadRequest("body too large")
        val body = ByteArray(length)
        var read = 0
        while (read < length) {
            val n = input.read(body, read, length - read)
            if (n < 0) break
            read += n
        }
        return Request(parts[0].uppercase(), parts[1], headers, String(body, 0, read, Charsets.UTF_8))
    }

    private data class Request(val method: String, val path: String, val headers: Map<String, String>, val body: String)
    private data class Response(val code: Int, val json: JSONObject)
    private class BadRequest(message: String) : Exception(message)

    private fun reason(code: Int) = when (code) {
        200 -> "OK"; 204 -> "No Content"; 400 -> "Bad Request"; 401 -> "Unauthorized"; 404 -> "Not Found"
        else -> "Internal Server Error"
    }

    companion object {
        const val PORT = 8765
        private const val TAG = "RemoteOverlay"
        private const val DEFAULT_TTL_MS = 10_000L
        private const val MAX_BOXES = 64
        private const val MAX_HEADER = 16 * 1024
        private const val MAX_BODY = 256 * 1024

        /** Site-local IPv4 addresses of this TV, for display in the UI. */
        fun lanAddresses(): List<String> = runCatching {
            NetworkInterface.getNetworkInterfaces().toList()
                .filter { it.isUp && !it.isLoopback }
                .flatMap { it.inetAddresses.toList() }
                .filter { it.isSiteLocalAddress && it.address.size == 4 }
                .mapNotNull { it.hostAddress }
        }.getOrDefault(emptyList())
    }
}
