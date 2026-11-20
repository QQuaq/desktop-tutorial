package com.qquaq.livetranslatetv.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Button
import androidx.tv.material3.ButtonDefaults
import androidx.tv.material3.ExperimentalTvMaterial3Api
import androidx.tv.material3.OutlinedButton
import androidx.tv.material3.Text
import com.qquaq.livetranslatetv.LiveTranslateViewModel
import com.qquaq.livetranslatetv.R
import com.qquaq.livetranslatetv.StatusKind

@OptIn(ExperimentalTvMaterial3Api::class)
@Composable
fun TranslateScreen(
    vm: LiveTranslateViewModel,
    onToggleMic: () -> Unit,
    onOpenSettings: () -> Unit,
) {
    val micFocus = remember { FocusRequester() }
    LaunchedEffect(Unit) { micFocus.requestFocus() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 48.dp, vertical = 28.dp),
    ) {
        Text(
            stringResource(R.string.title),
            color = Color.White,
            fontSize = 30.sp,
            fontWeight = FontWeight.Bold,
        )
        Text(stringResource(R.string.subtitle), color = Muted, fontSize = 15.sp)

        Spacer(Modifier.size(16.dp))
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(
                onClick = onToggleMic,
                modifier = Modifier.focusRequester(micFocus),
                colors = ButtonDefaults.colors(
                    containerColor = if (vm.listening) Live else Accent,
                    contentColor = Color.White,
                    focusedContainerColor = if (vm.listening) Color(0xFFF87171) else Color(0xFF60A5FA),
                    focusedContentColor = Color.White,
                ),
            ) {
                Box(
                    Modifier
                        .size(10.dp)
                        .background(if (vm.listening) Color.White else Color(0xFFBFDBFE), CircleShape),
                )
                Spacer(Modifier.width(10.dp))
                Text(stringResource(if (vm.listening) R.string.mic_stop else R.string.mic_start))
            }
            OutlinedButton(onClick = vm::clearAll) { Text(stringResource(R.string.clear)) }
            OutlinedButton(onClick = vm::toggleSpeak) {
                Text(stringResource(if (vm.speakEnabled) R.string.speak_on else R.string.speak_off))
            }
            OutlinedButton(onClick = onOpenSettings) { Text(stringResource(R.string.settings)) }

            vm.status?.let { st ->
                Spacer(Modifier.width(8.dp))
                Text(
                    stringResource(st.text, st.arg ?: ""),
                    color = when (st.kind) {
                        StatusKind.OK -> Ok
                        StatusKind.ERROR -> Error
                        StatusKind.NEUTRAL -> Muted
                    },
                    fontSize = 15.sp,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        Spacer(Modifier.size(20.dp))
        SubtitleStage(vm, Modifier.weight(1f).fillMaxWidth())

        Spacer(Modifier.size(14.dp))
        Text(stringResource(R.string.english_label), color = Muted, fontSize = 13.sp)
        val english = buildString {
            append(vm.englishFinal.takeLast(220))
            if (vm.englishInterim.isNotEmpty()) append(" ").append(vm.englishInterim)
        }.trim()
        Text(
            english.ifEmpty { "—" },
            color = Color(0xFFC5D0E4),
            fontSize = 16.sp,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        Spacer(Modifier.size(6.dp))
        Text(stringResource(R.string.hint), color = Muted, fontSize = 12.sp)
    }
}

@Composable
private fun SubtitleStage(vm: LiveTranslateViewModel, modifier: Modifier) {
    val lines = vm.turkishLines
    val last = lines.lastOrNull()
    val previous = lines.getOrNull(lines.size - 2)
    val main = vm.turkishInterim.ifEmpty { last ?: "" }
    val dim = if (vm.turkishInterim.isNotEmpty()) last else previous

    Box(
        modifier = modifier
            .background(Stage, RoundedCornerShape(20.dp))
            .border(1.dp, Border, RoundedCornerShape(20.dp))
            .padding(horizontal = 36.dp, vertical = 24.dp),
    ) {
        Text(
            stringResource(R.string.subtitle_label).uppercase(),
            color = Muted,
            fontSize = 12.sp,
            letterSpacing = 2.sp,
            modifier = Modifier.align(Alignment.TopStart),
        )
        Column(
            modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            if (main.isEmpty()) {
                Text(
                    stringResource(if (vm.listening) R.string.empty_listening else R.string.empty_idle),
                    color = Muted,
                    fontSize = 26.sp,
                    textAlign = TextAlign.Center,
                )
            } else {
                if (!dim.isNullOrEmpty() && dim != main) {
                    Text(
                        dim,
                        color = Color(0xFF7D8BA6),
                        fontSize = 26.sp,
                        textAlign = TextAlign.Center,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Spacer(Modifier.size(10.dp))
                }
                Text(
                    main,
                    color = if (vm.turkishInterim.isNotEmpty()) Color(0xFFBFC9DB) else Color.White,
                    fontSize = 40.sp,
                    lineHeight = 50.sp,
                    fontWeight = FontWeight.SemiBold,
                    textAlign = TextAlign.Center,
                    maxLines = 4,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}
