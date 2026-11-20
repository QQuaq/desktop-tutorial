package com.qquaq.livetranslatetv

import android.app.Application
import androidx.annotation.StringRes
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

enum class StatusKind { NEUTRAL, OK, ERROR }

data class Status(@StringRes val text: Int, val kind: StatusKind = StatusKind.NEUTRAL, val arg: String? = null)

class LiveTranslateViewModel(app: Application) : AndroidViewModel(app) {
    val prefs = Prefs(app)
    private val translator = Translator { prefs.serverUrl }
    private val translateLock = Mutex()

    var listening by mutableStateOf(false)
        private set
    var status by mutableStateOf<Status?>(null)
        private set
    var englishFinal by mutableStateOf("")
        private set
    var englishInterim by mutableStateOf("")
        private set
    val turkishLines = mutableStateListOf<String>()
    var turkishInterim by mutableStateOf("")
        private set
    var speakEnabled by mutableStateOf(prefs.speakEnabled)
        private set
    private var pendingTranslations = 0
    private var wantListening = false

    private val speaker = Speaker(app) {
        status = Status(R.string.err_tts, StatusKind.ERROR)
    }

    private val listener = SpeechListener(
        context = app,
        onListeningChanged = { active ->
            if (active && !listening) status = Status(R.string.status_listening, StatusKind.OK)
            listening = active || wantListening
        },
        onPartial = { text ->
            englishInterim = text
            turkishInterim = "…"
        },
        onFinal = { text -> appendFinal(text) },
        onError = { event -> onRecognitionError(event) },
    )

    val recognitionAvailable: Boolean get() = listener.isAvailable()

    fun startListening() {
        wantListening = true
        listening = true
        status = Status(R.string.status_listening, StatusKind.OK)
        listener.start()
    }

    fun stopListening() {
        wantListening = false
        listener.stop()
        listening = false
        englishInterim = ""
        turkishInterim = ""
        status = Status(R.string.status_stopped)
    }

    fun toggleListening() = if (listening) stopListening() else startListening()

    fun onPermissionDenied() {
        status = Status(R.string.err_permission, StatusKind.ERROR)
    }

    fun clearAll() {
        englishFinal = ""
        englishInterim = ""
        turkishLines.clear()
        turkishInterim = ""
        speaker.stop()
        status = null
    }

    fun toggleSpeak() {
        speakEnabled = !speakEnabled
        prefs.speakEnabled = speakEnabled
        if (!speakEnabled) speaker.stop()
    }

    fun onRecognisedText(text: String) = appendFinal(text)

    suspend fun testServer(url: String): String? = runCatching { translator.testServer(url) }.getOrNull()

    private fun appendFinal(chunk: String) {
        val text = chunk.trim()
        if (text.isEmpty()) return
        englishFinal = (if (englishFinal.isEmpty()) text else "$englishFinal $text").takeLast(2000)
        englishInterim = ""
        turkishInterim = ""
        pendingTranslations++
        status = Status(R.string.status_translating)
        viewModelScope.launch {
            translateLock.withLock {
                try {
                    val tr = translator.translateEnToTr(text)
                    turkishLines.add(tr)
                    while (turkishLines.size > 4) turkishLines.removeAt(0)
                    if (speakEnabled) speaker.speak(tr)
                    if (pendingTranslations == 1) {
                        status = if (listening) Status(R.string.status_listening_short, StatusKind.OK) else null
                    }
                } catch (e: Exception) {
                    status = Status(R.string.err_translate, StatusKind.ERROR)
                } finally {
                    pendingTranslations--
                }
            }
        }
    }

    private fun onRecognitionError(event: SpeechListener.Event) {
        when (event) {
            SpeechListener.Event.PERMISSION -> {
                wantListening = false
                listening = false
                status = Status(R.string.err_permission, StatusKind.ERROR)
            }
            SpeechListener.Event.UNSUPPORTED -> {
                wantListening = false
                listening = false
                status = Status(R.string.err_unsupported, StatusKind.ERROR)
            }
            SpeechListener.Event.NO_SPEECH -> {
                if (turkishInterim == "…") turkishInterim = ""
                englishInterim = ""
                status = Status(R.string.status_no_speech)
            }
            SpeechListener.Event.OTHER -> {
                if (!listener.isActive) {
                    wantListening = false
                    listening = false
                }
                status = Status(
                    R.string.err_recognition,
                    StatusKind.ERROR,
                    arg = errorName(listener.lastErrorCode),
                )
            }
        }
    }

    private fun errorName(code: Int) = when (code) {
        1 -> "network-timeout"
        2 -> "network"
        3 -> "audio"
        4 -> "server"
        5 -> "client"
        8 -> "busy"
        else -> code.toString()
    }

    override fun onCleared() {
        listener.stop()
        speaker.shutdown()
    }
}
