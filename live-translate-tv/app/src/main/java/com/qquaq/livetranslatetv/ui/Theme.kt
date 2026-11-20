package com.qquaq.livetranslatetv.ui

import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.darkColorScheme

val Background = Color(0xFF0B1020)
val Stage = Color(0xFF111A30)
val Border = Color(0xFF243049)
val Muted = Color(0xFF8FA0BF)
val Accent = Color(0xFF3B82F6)
val Live = Color(0xFFEF4444)
val Ok = Color(0xFF34D399)
val Error = Color(0xFFF87171)

@Composable
fun AppTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Accent,
            onPrimary = Color.White,
            background = Background,
            surface = Stage,
            onSurface = Color(0xFFE6ECF7),
            border = Border,
        ),
        content = content,
    )
}
