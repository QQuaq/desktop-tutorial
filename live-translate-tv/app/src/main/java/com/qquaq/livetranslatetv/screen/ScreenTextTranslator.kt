package com.qquaq.livetranslatetv.screen

import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Rect
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.common.model.DownloadConditions
import com.google.mlkit.nl.translate.TranslateLanguage
import com.google.mlkit.nl.translate.Translation
import com.google.mlkit.nl.translate.TranslatorOptions
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import com.qquaq.livetranslatetv.Translator
import kotlinx.coroutines.runBlocking
import java.util.concurrent.TimeUnit

/** One translated text block, in capture-bitmap coordinates. */
data class TranslatedBlock(
    val rect: Rect,
    val text: String,
    val lines: Int,
    val background: Int,
    val foreground: Int,
)

/**
 * OCR (ML Kit Latin, on-device) + EN->TR translation (ML Kit on-device, falling back to the
 * app's online provider chain while the model is missing). Blocking; call from a worker thread.
 */
class ScreenTextTranslator(serverUrl: () -> String) {
    private val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    private val mlTranslator = Translation.getClient(
        TranslatorOptions.Builder()
            .setSourceLanguage(TranslateLanguage.ENGLISH)
            .setTargetLanguage(TranslateLanguage.TURKISH)
            .build(),
    )
    private val online = Translator(serverUrl)
    @Volatile private var modelReady = false

    private val cache = object : LinkedHashMap<String, String>(256, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, String>?) = size > 800
    }
    private val recentOutputs = object : LinkedHashMap<String, Boolean>(64, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Boolean>?) = size > 200
    }

    fun downloadModel(onStatus: (ModelStatus) -> Unit) {
        onStatus(ModelStatus.DOWNLOADING)
        mlTranslator.downloadModelIfNeeded(DownloadConditions.Builder().build())
            .addOnSuccessListener {
                modelReady = true
                onStatus(ModelStatus.READY)
            }
            .addOnFailureListener { onStatus(ModelStatus.FAILED) }
    }

    fun process(frame: Bitmap): List<TranslatedBlock> {
        val text = Tasks.await(recognizer.process(InputImage.fromBitmap(frame, 0)), 10, TimeUnit.SECONDS)
        val result = mutableListOf<TranslatedBlock>()
        for (block in text.textBlocks) {
            val rect = block.boundingBox ?: continue
            val source = block.lines.joinToString(" ") { it.text }.replace(Regex("\\s+"), " ").trim()
            if (!looksEnglish(source, block.recognizedLanguage) || rect.height() < 8) continue
            if (synchronized(recentOutputs) { recentOutputs.containsKey(source) }) continue
            val translated = translate(source) ?: continue
            if (translated.equals(source, ignoreCase = true)) continue
            synchronized(recentOutputs) { recentOutputs[translated] = true }
            val bg = Frames.backgroundColor(frame, rect)
            val fg = if (Frames.luminance(bg) > 140) Color.BLACK else Color.WHITE
            result += TranslatedBlock(rect, translated, block.lines.size.coerceAtLeast(1), bg, fg)
        }
        return result
    }

    private fun translate(source: String): String? {
        synchronized(cache) { cache[source] }?.let { return it }
        val translated = if (modelReady) {
            runCatching { Tasks.await(mlTranslator.translate(source), 10, TimeUnit.SECONDS) }.getOrNull()
        } else {
            null
        } ?: runCatching { runBlocking { online.translateEnToTr(source) } }.getOrNull()
        translated?.trim()?.takeIf { it.isNotEmpty() }?.let { t -> synchronized(cache) { cache[source] = t } }
        return translated?.trim()
    }

    fun close() {
        recognizer.close()
        mlTranslator.close()
    }

    companion object {
        private val turkishChars = Regex("[çğıöşüÇĞİÖŞÜ]")
        private val letters = Regex("[A-Za-z]")

        fun looksEnglish(text: String, language: String?): Boolean {
            if (text.length < 2) return false
            val letterCount = letters.findAll(text).count()
            if (letterCount < 2 || letterCount < text.length * 0.4) return false
            if (turkishChars.containsMatchIn(text)) return false
            val lang = language.orEmpty()
            return lang.isEmpty() || lang == "und" || lang.startsWith("en")
        }
    }
}
