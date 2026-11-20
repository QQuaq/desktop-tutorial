package com.qquaq.livetranslatetv.screen

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.graphics.RectF
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import android.util.DisplayMetrics
import android.util.Log
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import androidx.core.app.NotificationCompat
import com.qquaq.livetranslatetv.MainActivity
import com.qquaq.livetranslatetv.Prefs
import com.qquaq.livetranslatetv.R
import com.qquaq.livetranslatetv.withAppLocale
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlin.math.abs

/**
 * Background screen translator: mirrors the display into an ImageReader via MediaProjection,
 * OCRs English text and draws Turkish boxes on a TYPE_APPLICATION_OVERLAY window.
 */
class ScreenTranslatorService : Service() {

    private val main = Handler(Looper.getMainLooper())
    private lateinit var worker: HandlerThread
    private lateinit var workerHandler: Handler
    private lateinit var windowManager: WindowManager

    private var projection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var reader: ImageReader? = null
    private var overlay: OverlayView? = null
    private var textTranslator: ScreenTextTranslator? = null

    @Volatile private var running = false
    private var scale = 1f
    private var lastVisible: Bitmap? = null
    private var lastSignature: IntArray? = null
    private var lastCleanAt = 0L

    override fun attachBaseContext(newBase: Context) = super.attachBaseContext(newBase.withAppLocale())

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (projection != null) return START_NOT_STICKY

        startInForeground()
        val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
        @Suppress("DEPRECATION")
        val data = intent?.getParcelableExtra<Intent>(EXTRA_RESULT_DATA)
        if (data == null || !ScreenPermissions.canDrawOverlays(this)) {
            fail(getString(R.string.screen_err_permissions))
            return START_NOT_STICKY
        }
        try {
            start(resultCode, data)
        } catch (e: Exception) {
            Log.e(TAG, "start failed", e)
            fail(e.message ?: e.javaClass.simpleName)
        }
        return START_NOT_STICKY
    }

    private fun start(resultCode: Int, data: Intent) {
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        val mpm = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        val mp = mpm.getMediaProjection(resultCode, data) ?: error("MediaProjection denied")
        projection = mp
        // Must be registered before createVirtualDisplay on Android 14+.
        mp.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() {
                main.post { stopSelf() }
            }
        }, main)

        worker = HandlerThread("screen-translator").apply { start() }
        workerHandler = Handler(worker.looper)

        val metrics = DisplayMetrics()
        @Suppress("DEPRECATION")
        windowManager.defaultDisplay.getRealMetrics(metrics)
        scale = minOf(1f, CAPTURE_MAX_WIDTH.toFloat() / metrics.widthPixels)
        val capW = ((metrics.widthPixels * scale).toInt() / 2) * 2
        val capH = ((metrics.heightPixels * scale).toInt() / 2) * 2
        scale = capW.toFloat() / metrics.widthPixels

        addOverlay(metrics.widthPixels, metrics.heightPixels)

        val imageReader = ImageReader.newInstance(capW, capH, PixelFormat.RGBA_8888, 3)
        reader = imageReader
        virtualDisplay = mp.createVirtualDisplay(
            "screen-translator", capW, capH, metrics.densityDpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, imageReader.surface, null, workerHandler,
        )

        val prefs = Prefs(this)
        textTranslator = ScreenTextTranslator { prefs.serverUrl }.also { t ->
            t.downloadModel { status -> ScreenTranslatorState.update { it.copy(model = status) } }
        }
        running = true
        ScreenTranslatorState.update { ScreenTranslatorStatus(running = true, model = it.model) }
        workerHandler.postDelayed(::tick, INTERVAL_MS)
    }

    private fun addOverlay(width: Int, height: Int) {
        val view = OverlayView(this)
        @Suppress("DEPRECATION")
        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            WindowManager.LayoutParams.TYPE_PHONE
        }
        val params = WindowManager.LayoutParams(
            width, height, type,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = 0
            y = 0
            title = "ScreenTranslatorOverlay"
        }
        windowManager.addView(view, params)
        overlay = view
    }

    private fun tick() {
        if (!running) return
        try {
            step()
        } catch (e: Exception) {
            Log.w(TAG, "frame failed", e)
            ScreenTranslatorState.update { it.copy(lastError = e.message ?: e.javaClass.simpleName) }
        }
        if (running) workerHandler.postDelayed(::tick, INTERVAL_MS)
    }

    private fun step() {
        val imageReader = reader ?: return
        val image = imageReader.acquireLatestImage()
        if (image != null) {
            val bmp = Frames.toBitmap(image)
            image.close()
            lastVisible?.recycle()
            lastVisible = bmp
            ScreenTranslatorState.update { it.copy(frames = it.frames + 1) }
        }
        val now = SystemClock.uptimeMillis()
        if (image == null && now - lastCleanAt < REFRESH_MS) return

        val hasBoxes = onMain { overlay?.hasBoxes == true }
        val clean = if (hasBoxes) captureWithoutOverlay() else lastVisible?.copy(Bitmap.Config.ARGB_8888, false)
        clean ?: return
        lastCleanAt = now

        val signature = Frames.signature(clean)
        if (!changed(lastSignature, signature)) {
            clean.recycle()
            return
        }
        lastSignature = signature

        val blocks = textTranslator?.process(clean).orEmpty()
        clean.recycle()
        val boxes = blocks.map {
            OverlayBox(
                RectF(it.rect.left / scale, it.rect.top / scale, it.rect.right / scale, it.rect.bottom / scale),
                it.text, it.lines, it.background, it.foreground,
            )
        }
        if (!running) return
        onMain { overlay?.setBoxes(boxes) }
        settleAndDrain()
        ScreenTranslatorState.update { it.copy(boxes = boxes.size, ocrRuns = it.ocrRuns + 1, lastError = null) }
    }

    /** Hides our overlay for one frame so OCR never sees (and re-translates) our own Turkish boxes. */
    private fun captureWithoutOverlay(): Bitmap? {
        onMain { overlay?.visibility = View.INVISIBLE }
        SystemClock.sleep(HIDE_SETTLE_MS)
        val image = reader?.acquireLatestImage()
        onMain { overlay?.visibility = View.VISIBLE }
        val bmp = image?.let { Frames.toBitmap(it).also { _ -> it.close() } }
        settleAndDrain()
        return bmp
    }

    /** Drops the frames produced by our own overlay changes so they do not count as screen changes. */
    private fun settleAndDrain() {
        SystemClock.sleep(OWN_SETTLE_MS)
        reader?.acquireLatestImage()?.close()
    }

    private fun changed(old: IntArray?, new: IntArray): Boolean {
        if (old == null || old.size != new.size) return true
        var cells = 0
        for (i in old.indices) if (abs(old[i] - new[i]) > CELL_THRESHOLD && ++cells >= MIN_CHANGED_CELLS) return true
        return false
    }

    private fun <T> onMain(block: () -> T): T {
        if (Looper.myLooper() == Looper.getMainLooper()) return block()
        var result: Result<T>? = null
        val latch = CountDownLatch(1)
        main.post {
            result = runCatching(block)
            latch.countDown()
        }
        if (!latch.await(2, TimeUnit.SECONDS)) error("main thread timeout")
        return result!!.getOrThrow()
    }

    private fun startInForeground() {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            nm.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, getString(R.string.screen_mode_title), NotificationManager.IMPORTANCE_LOW),
            )
        }
        val immutable = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0
        val stop = PendingIntent.getService(
            this, 1, Intent(this, ScreenTranslatorService::class.java).setAction(ACTION_STOP), immutable,
        )
        val open = PendingIntent.getActivity(this, 2, Intent(this, MainActivity::class.java), immutable)
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(getString(R.string.screen_notification_title))
            .setContentText(getString(R.string.screen_notification_text))
            .setContentIntent(open)
            .addAction(0, getString(R.string.screen_stop), stop)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun fail(message: String) {
        ScreenTranslatorState.update { it.copy(running = false, lastError = message) }
        stopSelf()
    }

    override fun onDestroy() {
        running = false
        if (::worker.isInitialized) worker.quitSafely()
        virtualDisplay?.release()
        reader?.close()
        projection?.stop()
        overlay?.let { runCatching { windowManager.removeView(it) } }
        textTranslator?.close()
        lastVisible?.recycle()
        projection = null
        ScreenTranslatorState.update { it.copy(running = false, boxes = 0) }
        super.onDestroy()
    }

    companion object {
        const val ACTION_STOP = "com.qquaq.livetranslatetv.screen.STOP"
        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"
        private const val TAG = "ScreenTranslator"
        private const val CHANNEL_ID = "screen-translator"
        private const val NOTIFICATION_ID = 42
        private const val CAPTURE_MAX_WIDTH = 1280
        private const val INTERVAL_MS = 800L
        private const val REFRESH_MS = 3000L
        private const val HIDE_SETTLE_MS = 120L
        private const val OWN_SETTLE_MS = 150L
        private const val CELL_THRESHOLD = 12
        private const val MIN_CHANGED_CELLS = 2
    }
}
