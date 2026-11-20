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
import kotlin.math.abs

/** One translated text block, in capture-bitmap coordinates. */
data class TranslatedBlock(
    val rect: Rect,
    val text: String,
    val lines: Int,
    val background: Int,
    val foreground: Int,
)

/** OCR text block in capture-bitmap coordinates. */
data class OcrBlock(
    val left: Int,
    val top: Int,
    val right: Int,
    val bottom: Int,
    val text: String,
    val lines: Int,
    val language: String?,
) {
    val lineHeight: Float get() = (bottom - top).toFloat().coerceAtLeast(1f) / lines
}

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
        val ocrBlocks = text.textBlocks.mapNotNull { block ->
            val box = block.boundingBox ?: return@mapNotNull null
            OcrBlock(
                box.left, box.top, box.right, box.bottom,
                block.lines.joinToString(" ") { it.text }.replace(Regex("\\s+"), " ").trim(),
                block.lines.size.coerceAtLeast(1),
                block.recognizedLanguage,
            )
        }
        for (block in mergeContinuations(ocrBlocks)) {
            val rect = Rect(block.left, block.top, block.right, block.bottom)
            val source = block.text
            if (!looksEnglish(source, block.language) || rect.height() < 8) continue
            if (synchronized(recentOutputs) { recentOutputs.containsKey(source) }) continue
            val translated = translate(source) ?: continue
            if (translated.equals(source, ignoreCase = true)) continue
            synchronized(recentOutputs) { recentOutputs[translated] = true }
            val bg = Frames.backgroundColor(frame, rect)
            val fg = if (Frames.luminance(bg) > 140) Color.BLACK else Color.WHITE
            result += TranslatedBlock(rect, translated, block.lines, bg, fg)
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

        /**
         * ML Kit sometimes splits one wrapped sentence into two blocks ("…start the movie from the" /
         * "beginning."); translated separately, the tail becomes nonsense. Joins a block into the one above
         * when it starts lowercase, is left-aligned with it, has a similar line height and directly follows it.
         */
        fun mergeContinuations(blocks: List<OcrBlock>): List<OcrBlock> {
            val merged = mutableListOf<OcrBlock>()
            for (block in blocks.sortedWith(compareBy({ it.top }, { it.left }))) {
                val index = merged.indexOfLast { it.continuesInto(block) }
                if (index < 0) {
                    merged += block
                } else {
                    val above = merged[index]
                    merged[index] = OcrBlock(
                        minOf(above.left, block.left), above.top, maxOf(above.right, block.right), block.bottom,
                        "${above.text} ${block.text}", above.lines + block.lines, above.language,
                    )
                }
            }
            return merged
        }

        private fun OcrBlock.continuesInto(next: OcrBlock): Boolean {
            val first = next.text.firstOrNull() ?: return false
            if (!first.isLowerCase() || text.isEmpty() || text.last() in ".!?:") return false
            // OCR box heights vary with ascenders/descenders ("from the" vs "beginning."), hence the loose ratio.
            val ratio = next.lineHeight / lineHeight
            val lineH = maxOf(lineHeight, next.lineHeight)
            val gap = next.top - bottom
            return abs(next.left - left) <= lineH * 0.6f && ratio in 0.65f..1.55f &&
                gap >= -lineH * 0.3f && gap <= lineH * 0.8f
        }

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
