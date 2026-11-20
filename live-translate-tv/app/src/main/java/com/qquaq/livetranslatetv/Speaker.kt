package com.qquaq.livetranslatetv

import android.content.Context
import android.speech.tts.TextToSpeech
import java.util.Locale

class Speaker(context: Context, private val onUnavailable: () -> Unit) : TextToSpeech.OnInitListener {
    private var ready = false
    private var lastSpoken = ""
    private val tts = TextToSpeech(context.applicationContext, this)

    override fun onInit(status: Int) {
        if (status != TextToSpeech.SUCCESS) return
        val result = tts.setLanguage(Locale("tr", "TR"))
        ready = result != TextToSpeech.LANG_MISSING_DATA && result != TextToSpeech.LANG_NOT_SUPPORTED
        tts.setSpeechRate(0.96f)
    }

    fun speak(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty() || trimmed == lastSpoken) return
        if (!ready) {
            onUnavailable()
            return
        }
        lastSpoken = trimmed
        tts.speak(trimmed, TextToSpeech.QUEUE_ADD, null, trimmed.hashCode().toString())
    }

    fun stop() {
        lastSpoken = ""
        tts.stop()
    }

    fun shutdown() = tts.shutdown()
}
