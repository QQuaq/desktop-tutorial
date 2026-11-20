package com.qquaq.livetranslatetv.screen

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class ModelStatus { UNKNOWN, DOWNLOADING, READY, FAILED }

data class ScreenTranslatorStatus(
    val running: Boolean = false,
    val model: ModelStatus = ModelStatus.UNKNOWN,
    val boxes: Int = 0,
    val frames: Int = 0,
    val ocrRuns: Int = 0,
    val lastError: String? = null,
)

/** Process-wide status of [ScreenTranslatorService], observed by the UI. */
object ScreenTranslatorState {
    private val _status = MutableStateFlow(ScreenTranslatorStatus())
    val status: StateFlow<ScreenTranslatorStatus> = _status.asStateFlow()

    fun update(transform: (ScreenTranslatorStatus) -> ScreenTranslatorStatus) {
        while (true) {
            val current = _status.value
            if (_status.compareAndSet(current, transform(current))) return
        }
    }
}
