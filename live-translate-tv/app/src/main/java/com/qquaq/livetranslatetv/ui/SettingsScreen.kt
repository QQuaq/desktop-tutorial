package com.qquaq.livetranslatetv.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Button
import androidx.tv.material3.OutlinedButton
import androidx.tv.material3.Text
import com.qquaq.livetranslatetv.LiveTranslateViewModel
import com.qquaq.livetranslatetv.R
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(
    vm: LiveTranslateViewModel,
    onBack: () -> Unit,
    onLanguageChanged: (String) -> Unit,
) {
    var url by remember { mutableStateOf(vm.prefs.serverUrl) }
    var message by remember { mutableStateOf<String?>(null) }
    var fieldFocused by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val keyboard = LocalSoftwareKeyboardController.current
    val focusManager = LocalFocusManager.current
    val backFocus = remember { FocusRequester() }
    LaunchedEffect(Unit) { backFocus.requestFocus() }

    val testing = stringResource(R.string.server_test_testing)
    val ok = stringResource(R.string.server_test_ok)
    val fail = stringResource(R.string.server_test_fail)
    val saved = stringResource(R.string.saved)

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 48.dp, vertical = 28.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            OutlinedButton(onClick = onBack, modifier = Modifier.focusRequester(backFocus)) {
                Text(stringResource(R.string.back))
            }
            Text(
                stringResource(R.string.settings_title),
                color = Color.White,
                fontSize = 30.sp,
                fontWeight = FontWeight.Bold,
            )
        }

        Text(stringResource(R.string.language_label), color = Color.White, fontSize = 18.sp)
        val lang = vm.prefs.uiLanguage
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            LanguageButton(stringResource(R.string.language_tr), lang == "tr") { if (lang != "tr") onLanguageChanged("tr") }
            LanguageButton(stringResource(R.string.language_en), lang == "en") { if (lang != "en") onLanguageChanged("en") }
        }

        Spacer(Modifier.size(4.dp))
        Text(stringResource(R.string.server_url_label), color = Color.White, fontSize = 18.sp)
        Text(stringResource(R.string.server_url_help), color = Muted, fontSize = 14.sp)
        Box(
            Modifier
                .width(560.dp)
                .background(Stage, RoundedCornerShape(12.dp))
                .border(2.dp, if (fieldFocused) Accent else Border, RoundedCornerShape(12.dp))
                .padding(horizontal = 16.dp, vertical = 12.dp),
        ) {
            if (url.isEmpty()) {
                Text(stringResource(R.string.server_url_placeholder), color = Color(0xFF55627D), fontSize = 18.sp)
            }
            BasicTextField(
                value = url,
                onValueChange = { url = it },
                singleLine = true,
                textStyle = TextStyle(color = Color.White, fontSize = 18.sp),
                cursorBrush = SolidColor(Accent),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { keyboard?.hide() }),
                modifier = Modifier
                    .onFocusChanged { fieldFocused = it.isFocused }
                    .onPreviewKeyEvent { event ->
                        // Text fields swallow vertical D-pad keys on TV; move focus out explicitly.
                        if (event.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                        when (event.key) {
                            Key.DirectionDown -> focusManager.moveFocus(FocusDirection.Down)
                            Key.DirectionUp -> focusManager.moveFocus(FocusDirection.Up)
                            Key.DirectionCenter, Key.Enter -> {
                                keyboard?.show()
                                true
                            }
                            else -> false
                        }
                    },
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(onClick = {
                vm.prefs.serverUrl = url
                message = saved
            }) { Text(stringResource(R.string.save)) }
            OutlinedButton(onClick = {
                val target = url.trim()
                if (target.isEmpty()) return@OutlinedButton
                message = testing
                scope.launch {
                    val result = vm.testServer(target)
                    message = if (result != null) ok.format(result) else fail
                }
            }) { Text(stringResource(R.string.server_test)) }
        }
        message?.let { Text(it, color = Muted, fontSize = 15.sp) }
    }
}

@Composable
private fun LanguageButton(label: String, selected: Boolean, onClick: () -> Unit) {
    if (selected) {
        Button(onClick = onClick) { Text("✓ $label") }
    } else {
        OutlinedButton(onClick = onClick) { Text(label) }
    }
}
