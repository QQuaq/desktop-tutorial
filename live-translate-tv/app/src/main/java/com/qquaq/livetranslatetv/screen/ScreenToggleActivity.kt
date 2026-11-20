package com.qquaq.livetranslatetv.screen

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import com.qquaq.livetranslatetv.MainActivity
import com.qquaq.livetranslatetv.R
import com.qquaq.livetranslatetv.withAppLocale

/**
 * Invisible "quick toggle" with its own home-screen banner: starts the screen translator
 * (asking for capture consent) or stops it if it is already running.
 */
class ScreenToggleActivity : ComponentActivity() {

    private val capture = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val data = result.data
        if (result.resultCode == Activity.RESULT_OK && data != null) {
            ScreenPermissions.startOcr(this, result.resultCode, data)
            Toast.makeText(this, R.string.screen_started_toast, Toast.LENGTH_SHORT).show()
            moveTaskToBack(true)
        }
        finish()
    }

    override fun attachBaseContext(newBase: Context) = super.attachBaseContext(newBase.withAppLocale())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (savedInstanceState != null) return
        when {
            ScreenTranslatorState.status.value.running -> {
                ScreenPermissions.stopAll(this)
                Toast.makeText(this, R.string.screen_stopped_toast, Toast.LENGTH_SHORT).show()
                finish()
            }
            !ScreenPermissions.canDrawOverlays(this) -> {
                startActivity(Intent(this, MainActivity::class.java).putExtra(MainActivity.EXTRA_OPEN_SCREEN_MODE, true))
                finish()
            }
            else -> try {
                capture.launch(ScreenPermissions.captureIntent(this))
            } catch (_: ActivityNotFoundException) {
                Toast.makeText(this, R.string.screen_err_no_consent_dialog, Toast.LENGTH_LONG).show()
                finish()
            }
        }
    }
}
