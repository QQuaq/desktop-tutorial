package com.qquaq.livetranslatetv

import android.Manifest
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
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
import com.qquaq.livetranslatetv.screen.ScreenPermissions
import com.qquaq.livetranslatetv.ui.AppTheme
import com.qquaq.livetranslatetv.ui.ScreenModeScreen
import com.qquaq.livetranslatetv.ui.SettingsScreen
import com.qquaq.livetranslatetv.ui.TranslateScreen

class MainActivity : ComponentActivity() {
    private enum class Page { SUBTITLES, SETTINGS, SCREEN }

    private val vm: LiveTranslateViewModel by viewModels()
    private var page by mutableStateOf(Page.SUBTITLES)
    private var overlayGranted by mutableStateOf(false)
    private var overlayHint by mutableStateOf<String?>(null)

    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) vm.startListening() else vm.onPermissionDenied()
    }

    private val screenCapture = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val data = result.data
        if (result.resultCode == Activity.RESULT_OK && data != null) {
            ScreenPermissions.startOcr(this, result.resultCode, data)
        }
    }

    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) {
        launchCaptureConsent()
    }

    private fun launchCaptureConsent() {
        try {
            screenCapture.launch(ScreenPermissions.captureIntent(this))
        } catch (_: ActivityNotFoundException) {
            overlayHint = getString(R.string.screen_err_no_consent_dialog)
        }
    }

    override fun attachBaseContext(newBase: Context) = super.attachBaseContext(newBase.withAppLocale())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        page = savedInstanceState?.getString(KEY_PAGE)?.let(Page::valueOf)
            ?: if (intent.getBooleanExtra(EXTRA_OPEN_SCREEN_MODE, false)) Page.SCREEN else Page.SUBTITLES
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContent {
            AppTheme {
                when (page) {
                    Page.SETTINGS -> {
                        BackHandler { page = Page.SUBTITLES }
                        SettingsScreen(
                            vm = vm,
                            onBack = { page = Page.SUBTITLES },
                            onLanguageChanged = { lang ->
                                vm.prefs.uiLanguage = lang
                                recreate()
                            },
                        )
                    }
                    Page.SCREEN -> {
                        BackHandler { page = Page.SUBTITLES }
                        ScreenModeScreen(
                            overlayGranted = overlayGranted,
                            overlayHint = overlayHint,
                            remoteToken = vm.prefs.remoteToken,
                            onStart = ::startScreenTranslator,
                            onStop = { ScreenPermissions.stopOcr(this) },
                            onStartNetwork = ::startNetworkReceiver,
                            onStopNetwork = { ScreenPermissions.stopNetwork(this) },
                            onOpenOverlaySettings = {
                                overlayHint = if (ScreenPermissions.openOverlaySettings(this)) null
                                else getString(R.string.screen_overlay_settings_missing)
                            },
                            onBack = { page = Page.SUBTITLES },
                        )
                    }
                    Page.SUBTITLES -> TranslateScreen(
                        vm = vm,
                        onToggleMic = ::toggleMic,
                        onOpenSettings = { page = Page.SETTINGS },
                        onOpenScreenMode = { page = Page.SCREEN },
                    )
                }
            }
        }
        if (savedInstanceState == null) handleDebugIntent(intent)
    }

    override fun onResume() {
        super.onResume()
        overlayGranted = ScreenPermissions.canDrawOverlays(this)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (intent.getBooleanExtra(EXTRA_OPEN_SCREEN_MODE, false)) page = Page.SCREEN
        handleDebugIntent(intent)
    }

    /** Debug builds only: `adb shell am start -n <pkg>/.MainActivity --es debug_text "Hello"` feeds text as if recognised. */
    private fun handleDebugIntent(intent: Intent?) {
        if (!BuildConfig.DEBUG) return
        intent?.getStringExtra("debug_text")?.let(vm::onRecognisedText)
    }

    private fun startScreenTranslator() {
        overlayGranted = ScreenPermissions.canDrawOverlays(this)
        if (!overlayGranted) {
            overlayHint = getString(R.string.screen_err_overlay)
            return
        }
        overlayHint = null
        val needsNotificationPermission = android.os.Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        if (needsNotificationPermission) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            launchCaptureConsent()
        }
    }

    private fun startNetworkReceiver() {
        overlayGranted = ScreenPermissions.canDrawOverlays(this)
        if (!overlayGranted) {
            overlayHint = getString(R.string.screen_err_overlay)
            return
        }
        overlayHint = null
        ScreenPermissions.startNetwork(this)
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
        if (page == Page.SUBTITLES && (keyCode == KeyEvent.KEYCODE_SEARCH || keyCode == KeyEvent.KEYCODE_VOICE_ASSIST)) {
            toggleMic()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putString(KEY_PAGE, page.name)
    }

    override fun onStop() {
        super.onStop()
        if (vm.listening && !isChangingConfigurations) vm.stopListening()
    }

    companion object {
        const val EXTRA_OPEN_SCREEN_MODE = "open_screen_mode"
        private const val KEY_PAGE = "page"
    }
}
