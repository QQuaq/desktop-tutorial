package com.qquaq.livetranslatetv

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

class TranslationException : Exception()

/**
 * EN -> TR translation with the same provider order as live-translate/lib/translate.ts:
 * the PC server's /api/translate (if configured), then the Google endpoint that server proxies,
 * then Lingva, then MyMemory. None of these need an API key.
 */
class Translator(private val serverUrl: () -> String) {

    private val cache = object : LinkedHashMap<String, String>(256, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, String>?) = size > 500
    }

    suspend fun translateEnToTr(text: String): String = withContext(Dispatchers.IO) {
        val pieces = chunks(text)
        if (pieces.isEmpty()) throw TranslationException()
        pieces.joinToString(" ") { translateChunk(it) }
    }

    suspend fun testServer(baseUrl: String): String? = withContext(Dispatchers.IO) {
        viaServer(baseUrl, "Hello, how are you?")
    }

    private fun translateChunk(text: String): String {
        synchronized(cache) { cache[text] }?.let { return it }
        val providers = listOf(
            { serverUrl().takeIf { it.isNotBlank() }?.let { viaServer(it, text) } },
            { viaGoogle(text) },
            { viaLingva(text) },
            { viaMyMemory(text) },
        )
        for (provider in providers) {
            val result = runCatching(provider).getOrNull()?.trim()
            if (!result.isNullOrEmpty() && !isBadTranslation(result)) {
                synchronized(cache) { cache[text] = result }
                return result
            }
        }
        throw TranslationException()
    }

    private fun viaServer(baseUrl: String, text: String): String? {
        val endpoint = baseUrl.trim().trimEnd('/') + "/api/translate"
        val body = JSONObject().put("text", text).toString()
        val json = http(endpoint, postJson = body) ?: return null
        return JSONObject(json).optString("translated").takeIf { it.isNotBlank() }
    }

    private fun viaGoogle(text: String): String? {
        val url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=tr&dt=t&q=" + enc(text)
        val json = http(url) ?: return null
        val segments = JSONArray(json).optJSONArray(0) ?: return null
        return buildString {
            for (i in 0 until segments.length()) {
                segments.optJSONArray(i)?.let { append(it.optString(0, "")) }
            }
        }
    }

    private fun viaLingva(text: String): String? {
        val json = http("https://lingva.ml/api/v1/en/tr/" + enc(text).replace("+", "%20")) ?: return null
        return JSONObject(json).optString("translation")
    }

    private fun viaMyMemory(text: String): String? {
        val json = http("https://api.mymemory.translated.net/get?langpair=en%7Ctr&q=" + enc(text)) ?: return null
        val obj = JSONObject(json)
        if (obj.optInt("responseStatus") == 403) return null
        return obj.optJSONObject("responseData")?.optString("translatedText")
    }

    private fun http(url: String, postJson: String? = null): String? {
        val conn = URL(url).openConnection() as HttpURLConnection
        return try {
            conn.connectTimeout = 5000
            conn.readTimeout = 8000
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (compatible; LiveEnTrTv/0.1)")
            if (postJson != null) {
                conn.requestMethod = "POST"
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json")
                conn.outputStream.use { it.write(postJson.toByteArray(Charsets.UTF_8)) }
            }
            if (conn.responseCode !in 200..299) null
            else conn.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally {
            conn.disconnect()
        }
    }

    private fun enc(s: String) = URLEncoder.encode(s, "UTF-8")

    private fun isBadTranslation(text: String) =
        Regex("MYMEMORY WARNING", RegexOption.IGNORE_CASE).containsMatchIn(text) ||
            Regex("^NEXT AVAILABLE IN", RegexOption.IGNORE_CASE).containsMatchIn(text)

    companion object {
        private const val MAX_CHUNK = 450

        fun chunks(text: String): List<String> {
            var rest = text.trim()
            if (rest.isEmpty()) return emptyList()
            val parts = mutableListOf<String>()
            while (rest.length > MAX_CHUNK) {
                val slice = rest.substring(0, MAX_CHUNK)
                val breakAt = maxOf(slice.lastIndexOf(' '), slice.lastIndexOf(". "))
                val cut = if (breakAt > 80) breakAt else MAX_CHUNK
                parts += rest.substring(0, cut).trim()
                rest = rest.substring(cut).trim()
            }
            if (rest.isNotEmpty()) parts += rest
            return parts
        }
    }
}
