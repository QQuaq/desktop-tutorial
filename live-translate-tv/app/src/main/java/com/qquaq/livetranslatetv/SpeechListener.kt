package com.qquaq.livetranslatetv

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

/**
 * Continuous English recognition on top of Android's one-utterance SpeechRecognizer:
 * it restarts after every result or recoverable error while [wantListening] is true,
 * which mirrors the web app's `continuous = true` + restart-on-end behaviour.
 * Must be used from the main thread.
 */
class SpeechListener(
    private val context: Context,
    private val onListeningChanged: (Boolean) -> Unit,
    private val onPartial: (String) -> Unit,
    private val onFinal: (String) -> Unit,
    private val onError: (Event) -> Unit,
) {
    enum class Event { PERMISSION, UNSUPPORTED, NO_SPEECH, OTHER }

    private val handler = Handler(Looper.getMainLooper())
    private var recognizer: SpeechRecognizer? = null
    private var wantListening = false
    private var consecutiveErrors = 0
    var lastErrorCode: Int = 0
        private set
    val isActive: Boolean get() = wantListening

    fun isAvailable(): Boolean = SpeechRecognizer.isRecognitionAvailable(context)

    fun start() {
        if (!isAvailable()) {
            onError(Event.UNSUPPORTED)
            return
        }
        wantListening = true
        consecutiveErrors = 0
        listenOnce()
    }

    fun stop() {
        wantListening = false
        handler.removeCallbacksAndMessages(null)
        recognizer?.let {
            it.cancel()
            it.destroy()
        }
        recognizer = null
        onListeningChanged(false)
    }

    private fun listenOnce() {
        if (!wantListening) return
        val rec = recognizer ?: SpeechRecognizer.createSpeechRecognizer(context).also {
            it.setRecognitionListener(listener)
            recognizer = it
        }
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "en-US")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
        }
        try {
            rec.startListening(intent)
        } catch (e: Exception) {
            scheduleRestart(recreate = true)
        }
    }

    private fun scheduleRestart(recreate: Boolean, delayMs: Long = 250) {
        if (!wantListening) return
        if (recreate) {
            recognizer?.destroy()
            recognizer = null
        }
        handler.postDelayed({ listenOnce() }, delayMs)
    }

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) = onListeningChanged(true)
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() {}
        override fun onEvent(eventType: Int, params: Bundle?) {}

        override fun onPartialResults(partialResults: Bundle?) {
            firstResult(partialResults)?.let(onPartial)
        }

        override fun onResults(results: Bundle?) {
            consecutiveErrors = 0
            firstResult(results)?.let(onFinal)
            scheduleRestart(recreate = false, delayMs = 50)
        }

        override fun onError(error: Int) {
            lastErrorCode = error
            when (error) {
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> {
                    stop()
                    onError(Event.PERMISSION)
                }
                SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> {
                    onError(Event.NO_SPEECH)
                    scheduleRestart(recreate = false)
                }
                else -> {
                    consecutiveErrors++
                    if (consecutiveErrors > 8) {
                        stop()
                        onError(Event.OTHER)
                        return
                    }
                    if (error != SpeechRecognizer.ERROR_CLIENT) onError(Event.OTHER)
                    val busy = error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY
                    scheduleRestart(recreate = true, delayMs = if (busy) 800 else 400L * consecutiveErrors)
                }
            }
        }
    }

    private fun firstResult(bundle: Bundle?): String? =
        bundle?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            ?.firstOrNull()
            ?.takeIf { it.isNotBlank() }
}
