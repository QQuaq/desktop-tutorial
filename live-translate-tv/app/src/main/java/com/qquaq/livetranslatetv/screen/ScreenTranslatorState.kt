package com.qquaq.livetranslatetv.screen

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class ModelStatus { UNKNOWN, DOWNLOADING, READY, FAILED }

data class ScreenTranslatorStatus(
    /** On-device OCR of the captured screen (needs MediaProjection consent). */
    val ocr: Boolean = false,
    /** LAN receiver that accepts translated boxes from another device. */
    val network: Boolean = false,
    val networkUrls: List<String> = emptyList(),
    val model: ModelStatus = ModelStatus.UNKNOWN,
    val boxes: Int = 0,
    val remoteBoxes: Int = 0,
    val frames: Int = 0,
    val ocrRuns: Int = 0,
    val lastError: String? = null,
) {
    val running: Boolean get() = ocr || network
}

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
