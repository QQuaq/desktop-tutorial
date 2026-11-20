package com.qquaq.livetranslatetv.screen

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.ContextCompat

object ScreenPermissions {
    fun adbOverlayCommand(context: Context) =
        "adb shell appops set ${context.packageName} SYSTEM_ALERT_WINDOW allow"

    fun canDrawOverlays(context: Context): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.M || Settings.canDrawOverlays(context)

    /** Google TV ships without this settings page; returns false when it cannot be opened. */
    fun openOverlaySettings(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return false
        val intents = listOf(
            Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:${context.packageName}")),
            Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION),
        )
        for (intent in intents) {
            if (intent.resolveActivity(context.packageManager) == null) continue
            try {
                context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                return true
            } catch (_: ActivityNotFoundException) {
            } catch (_: SecurityException) {
            }
        }
        return false
    }

    fun captureIntent(context: Context): Intent =
        (context.getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager)
            .createScreenCaptureIntent()

    fun startOcr(context: Context, resultCode: Int, data: Intent) {
        val intent = Intent(context, ScreenTranslatorService::class.java)
            .putExtra(ScreenTranslatorService.EXTRA_RESULT_CODE, resultCode)
            .putExtra(ScreenTranslatorService.EXTRA_RESULT_DATA, data)
        ContextCompat.startForegroundService(context, intent)
    }

    fun startNetwork(context: Context) = ContextCompat.startForegroundService(
        context, Intent(context, ScreenTranslatorService::class.java).setAction(ScreenTranslatorService.ACTION_START_NETWORK),
    )

    fun stopOcr(context: Context) = send(context, ScreenTranslatorService.ACTION_STOP_OCR)

    fun stopNetwork(context: Context) = send(context, ScreenTranslatorService.ACTION_STOP_NETWORK)

    fun stopAll(context: Context) = send(context, ScreenTranslatorService.ACTION_STOP)

    private fun send(context: Context, action: String) {
        if (!ScreenTranslatorState.status.value.running) return
        context.startService(Intent(context, ScreenTranslatorService::class.java).setAction(action))
    }
}
