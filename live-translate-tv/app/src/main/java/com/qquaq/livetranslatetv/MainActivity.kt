package com.qquaq.livetranslatetv

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.os.Bundle
import android.view.KeyEvent
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import com.qquaq.livetranslatetv.ui.AppTheme
import com.qquaq.livetranslatetv.ui.SettingsScreen
import com.qquaq.livetranslatetv.ui.TranslateScreen
import java.util.Locale

class MainActivity : ComponentActivity() {
    private val vm: LiveTranslateViewModel by viewModels()
    private var showSettings by mutableStateOf(false)

    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) vm.startListening() else vm.onPermissionDenied()
    }

    override fun attachBaseContext(newBase: Context) {
        val locale = Locale(Prefs(newBase).uiLanguage)
        Locale.setDefault(locale)
        val config = Configuration(newBase.resources.configuration).apply { setLocale(locale) }
        super.attachBaseContext(newBase.createConfigurationContext(config))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        showSettings = savedInstanceState?.getBoolean(KEY_SETTINGS) ?: false
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContent {
            AppTheme {
                if (showSettings) {
                    BackHandler { showSettings = false }
                    SettingsScreen(
                        vm = vm,
                        onBack = { showSettings = false },
                        onLanguageChanged = { lang ->
                            vm.prefs.uiLanguage = lang
                            recreate()
                        },
                    )
                } else {
                    TranslateScreen(
                        vm = vm,
                        onToggleMic = ::toggleMic,
                        onOpenSettings = { showSettings = true },
                    )
                }
            }
        }
        if (savedInstanceState == null) handleDebugIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleDebugIntent(intent)
    }

    /** Debug builds only: `adb shell am start -n <pkg>/.MainActivity --es debug_text "Hello"` feeds text as if recognised. */
    private fun handleDebugIntent(intent: Intent?) {
        if (!BuildConfig.DEBUG) return
        intent?.getStringExtra("debug_text")?.let(vm::onRecognisedText)
    }

    private fun toggleMic() {
        if (vm.listening) {
            vm.stopListening()
            return
        }
        val granted = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        if (granted) vm.startListening() else micPermission.launch(Manifest.permission.RECORD_AUDIO)
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean {
        // The remote's mic/search key reaches the app as SEARCH (or VOICE_ASSIST on some remotes)
        // when the system assistant does not intercept it.
        if (!showSettings && (keyCode == KeyEvent.KEYCODE_SEARCH || keyCode == KeyEvent.KEYCODE_VOICE_ASSIST)) {
            toggleMic()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putBoolean(KEY_SETTINGS, showSettings)
    }

    override fun onStop() {
        super.onStop()
        if (vm.listening && !isChangingConfigurations) vm.stopListening()
    }

    private companion object {
        const val KEY_SETTINGS = "show_settings"
    }
}
