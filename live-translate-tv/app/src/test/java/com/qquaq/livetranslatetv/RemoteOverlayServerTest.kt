package com.qquaq.livetranslatetv

import com.qquaq.livetranslatetv.screen.RemoteFrame
import com.qquaq.livetranslatetv.screen.RemoteOverlayServer
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.net.HttpURLConnection
import java.net.ServerSocket
import java.net.URL
import java.util.concurrent.CopyOnWriteArrayList

class RemoteOverlayServerTest {
    private val frames = CopyOnWriteArrayList<RemoteFrame>()
    private var clears = 0
    private val port = ServerSocket(0).use { it.localPort }
    private val server = RemoteOverlayServer(
        port = port,
        token = "secret12",
        screenSize = { 1920 to 1080 },
        onFrame = { frames += it },
        onClear = { clears++ },
        status = { JSONObject().put("ocr", false) },
    )

    @Before fun start() = server.start()
    @After fun stop() = server.stop()

    private fun call(method: String, path: String, body: String? = null, token: String? = "secret12"): Pair<Int, JSONObject> {
        val conn = URL("http://127.0.0.1:$port$path").openConnection() as HttpURLConnection
        conn.requestMethod = method
        token?.let { conn.setRequestProperty("X-Token", it) }
        if (body != null) {
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            conn.outputStream.use { it.write(body.toByteArray()) }
        }
        val code = conn.responseCode
        val text = (if (code < 400) conn.inputStream else conn.errorStream).bufferedReader().readText()
        return code to JSONObject(text)
    }

    @Test
    fun rejectsMissingOrWrongToken() {
        assertEquals(401, call("POST", "/overlay", "{\"subtitle\":\"x\"}", token = null).first)
        assertEquals(401, call("POST", "/overlay", "{\"subtitle\":\"x\"}", token = "nope").first)
        assertTrue(frames.isEmpty())
    }

    @Test
    fun acceptsNormalisedAndPixelBoxes() {
        val (code, json) = call(
            "POST", "/overlay",
            """{"boxes":[{"x":0.1,"y":0.8,"w":0.5,"h":0.1,"text":"Merhaba dünya","lines":2}],"ttlMs":3000}""",
        )
        assertEquals(200, code)
        assertEquals(1, json.getInt("boxes"))
        val box = frames.single().boxes.single()
        assertEquals("Merhaba dünya", box.text)
        assertEquals(0.8f, box.y, 1e-4f)
        assertEquals(2, box.lines)
        assertEquals(3000L, frames.single().ttlMs)

        call("POST", "/overlay", """{"coords":"pixels","boxes":[{"x":960,"y":540,"w":480,"h":108,"text":"Selam"}]}""")
        val px = frames.last().boxes.single()
        assertEquals(0.5f, px.x, 1e-4f)
        assertEquals(0.1f, px.h, 1e-4f)
    }

    @Test
    fun subtitleShortcutAndClear() {
        call("POST", "/overlay?token=secret12", """{"subtitle":"Görev tamamlandı"}""", token = null)
        assertEquals("Görev tamamlandı", frames.single().boxes.single().text)
        assertEquals(200, call("DELETE", "/overlay").first)
        assertEquals(1, clears)
    }

    @Test
    fun statusReportsScreenSize() {
        val (code, json) = call("GET", "/status")
        assertEquals(200, code)
        assertEquals(1920, json.getJSONObject("screen").getInt("width"))
        assertEquals(400, call("POST", "/overlay", """{"boxes":[{"y":0.1,"w":0.1,"h":0.1,"text":"no x"}]}""").first)
    }
}
