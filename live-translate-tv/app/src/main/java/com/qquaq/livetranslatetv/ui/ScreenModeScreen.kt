package com.qquaq.livetranslatetv.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Button
import androidx.tv.material3.ButtonDefaults
import androidx.tv.material3.OutlinedButton
import androidx.tv.material3.Text
import com.qquaq.livetranslatetv.R
import com.qquaq.livetranslatetv.screen.ModelStatus
import com.qquaq.livetranslatetv.screen.RemoteOverlayServer
import com.qquaq.livetranslatetv.screen.ScreenPermissions
import com.qquaq.livetranslatetv.screen.ScreenTranslatorState

@Composable
fun ScreenModeScreen(
    overlayGranted: Boolean,
    overlayHint: String?,
    remoteToken: String,
    onStart: () -> Unit,
    onStop: () -> Unit,
    onStartNetwork: () -> Unit,
    onStopNetwork: () -> Unit,
    onOpenOverlaySettings: () -> Unit,
    onBack: () -> Unit,
) {
    val status by ScreenTranslatorState.status.collectAsState()
    val context = LocalContext.current
    val primaryFocus = remember { FocusRequester() }
    LaunchedEffect(Unit) { primaryFocus.requestFocus() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 48.dp, vertical = 28.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            OutlinedButton(onClick = onBack) { Text(stringResource(R.string.back)) }
            Text(
                stringResource(R.string.screen_mode_title),
                color = Color.White,
                fontSize = 30.sp,
                fontWeight = FontWeight.Bold,
            )
        }
        Text(stringResource(R.string.screen_mode_desc), color = Muted, fontSize = 15.sp)

        StatusLine(
            stringResource(R.string.screen_status_overlay),
            stringResource(if (overlayGranted) R.string.screen_yes else R.string.screen_no),
            if (overlayGranted) Ok else Error,
        )
        if (!overlayGranted) {
            OutlinedButton(onClick = onOpenOverlaySettings) { Text(stringResource(R.string.screen_open_overlay_settings)) }
            Text(stringResource(R.string.screen_overlay_adb_help), color = Color.White, fontSize = 15.sp)
            Code(ScreenPermissions.adbOverlayCommand(context))
        }
        overlayHint?.let { Text(it, color = Error, fontSize = 14.sp) }
        status.lastError?.let { Text(it, color = Error, fontSize = 14.sp) }

        SectionTitle(stringResource(R.string.screen_section_ocr))
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            if (status.ocr) {
                Button(
                    onClick = onStop,
                    modifier = Modifier.focusRequester(primaryFocus),
                    colors = ButtonDefaults.colors(containerColor = Live, contentColor = Color.White),
                ) { Text(stringResource(R.string.screen_stop)) }
            } else {
                Button(onClick = onStart, modifier = Modifier.focusRequester(primaryFocus)) {
                    Text(stringResource(R.string.screen_start))
                }
            }
        }
        StatusLine(
            stringResource(R.string.screen_status_service),
            stringResource(if (status.ocr) R.string.screen_running else R.string.screen_stopped),
            if (status.ocr) Ok else Muted,
        )
        StatusLine(
            stringResource(R.string.screen_status_model),
            stringResource(
                when (status.model) {
                    ModelStatus.UNKNOWN -> R.string.screen_model_unknown
                    ModelStatus.DOWNLOADING -> R.string.screen_model_downloading
                    ModelStatus.READY -> R.string.screen_model_ready
                    ModelStatus.FAILED -> R.string.screen_model_failed
                },
            ),
            if (status.model == ModelStatus.READY) Ok else Muted,
        )
        if (status.ocr) {
            Text(stringResource(R.string.screen_stats, status.ocrRuns, status.boxes), color = Muted, fontSize = 14.sp)
        }

        SectionTitle(stringResource(R.string.screen_section_network))
        Text(stringResource(R.string.screen_network_desc), color = Muted, fontSize = 14.sp)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            if (status.network) {
                Button(
                    onClick = onStopNetwork,
                    colors = ButtonDefaults.colors(containerColor = Live, contentColor = Color.White),
                ) { Text(stringResource(R.string.screen_network_stop)) }
            } else {
                OutlinedButton(onClick = onStartNetwork) { Text(stringResource(R.string.screen_network_start)) }
            }
        }
        if (status.network) {
            val url = status.networkUrls.firstOrNull() ?: "http://<TV-IP>:${RemoteOverlayServer.PORT}"
            StatusLine(stringResource(R.string.screen_network_address), status.networkUrls.joinToString("  ").ifEmpty { url }, Ok)
            StatusLine(stringResource(R.string.screen_network_token), remoteToken, Ok)
            Text(stringResource(R.string.screen_stats_remote, status.remoteBoxes), color = Muted, fontSize = 14.sp)
            Code(
                "curl -X POST $url/overlay -H \"X-Token: $remoteToken\" -H \"Content-Type: application/json\" " +
                    "-d '{\"subtitle\":\"Merhaba dünya\"}'",
            )
        }

        Spacer(Modifier.size(4.dp))
        Text(stringResource(R.string.screen_limits), color = Muted, fontSize = 13.sp)
    }
}

@Composable
private fun SectionTitle(text: String) {
    Spacer(Modifier.size(6.dp))
    Text(text, color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
}

@Composable
private fun Code(text: String) {
    Text(
        text,
        color = Color(0xFFBFDBFE),
        fontFamily = FontFamily.Monospace,
        fontSize = 14.sp,
        modifier = Modifier
            .background(Stage, RoundedCornerShape(8.dp))
            .padding(horizontal = 12.dp, vertical = 8.dp),
    )
}

@Composable
private fun StatusLine(label: String, value: String, color: Color) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(label, color = Color.White, fontSize = 16.sp)
        Text(value, color = color, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
    }
}
