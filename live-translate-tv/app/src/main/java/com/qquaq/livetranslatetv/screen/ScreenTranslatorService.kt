package com.qquaq.livetranslatetv.screen

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
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
import org.json.JSONObject
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlin.math.abs

/**
 * Draws Turkish text over the TV picture on a TYPE_APPLICATION_OVERLAY window. Two independent sources:
 *  - OCR: mirrors the display via MediaProjection, OCRs English text on-device and translates it.
 *  - Network: [RemoteOverlayServer] accepts already-translated boxes from another device on the LAN
 *    (for content the TV cannot capture, e.g. an HDMI input).
 */
class ScreenTranslatorService : Service() {

    private val main = Handler(Looper.getMainLooper())
    private lateinit var windowManager: WindowManager
    private val metrics = DisplayMetrics()
    private var overlay: OverlayView? = null

    // OCR source
    private var worker: HandlerThread? = null
    private var workerHandler: Handler? = null
    private var projection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var reader: ImageReader? = null
    private var textTranslator: ScreenTextTranslator? = null
    @Volatile private var ocrRunning = false
    private var scale = 1f
    private var lastVisible: Bitmap? = null
    private var lastSignature: IntArray? = null
    private var lastCleanAt = 0L
    private var recheckAfterOcr = false

    // Network source
    private var server: RemoteOverlayServer? = null
    private var remoteGeneration = 0

    override fun attachBaseContext(newBase: Context) = super.attachBaseContext(newBase.withAppLocale())

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        @Suppress("DEPRECATION")
        windowManager.defaultDisplay.getRealMetrics(metrics)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> stopSelf()
            ACTION_STOP_OCR -> {
                stopOcr()
                stopIfIdle()
            }
            ACTION_START_NETWORK -> {
                enterForeground(withProjection = ocrRunning)
                if (ensureOverlay()) startNetwork()
                stopIfIdle()
            }
            ACTION_STOP_NETWORK -> {
                stopNetwork()
                stopIfIdle()
            }
            else -> {
                // Android 14: startForeground(type=mediaProjection) must precede getMediaProjection.
                enterForeground(withProjection = true)
                @Suppress("DEPRECATION")
                val data = intent?.getParcelableExtra<Intent>(EXTRA_RESULT_DATA)
                val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
                if (data == null || projection != null) {
                    if (data == null) report(getString(R.string.screen_err_permissions))
                } else if (ensureOverlay()) {
                    try {
                        startOcr(resultCode, data)
                    } catch (e: Exception) {
                        Log.e(TAG, "OCR start failed", e)
                        stopOcr()
                        report(e.message ?: e.javaClass.simpleName)
                    }
                }
                stopIfIdle()
            }
        }
        return START_NOT_STICKY
    }

    private fun ensureOverlay(): Boolean {
        if (overlay != null) return true
        if (!ScreenPermissions.canDrawOverlays(this)) {
            report(getString(R.string.screen_err_overlay))
            return false
        }
        val view = OverlayView(this)
        @Suppress("DEPRECATION")
        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            WindowManager.LayoutParams.TYPE_PHONE
        }
        // Android 12+ caps a NOT_TOUCHABLE overlay at 80% opacity, so the English would show through the
        // boxes. Remote keys still reach the app below via NOT_FOCUSABLE; only touch/mouse would be blocked,
        // which TVs do not use, so the cap is avoided there.
        val opaque = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S &&
            packageManager.hasSystemFeature(PackageManager.FEATURE_LEANBACK)
        var flags = WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
            WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
            WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
        if (!opaque) flags = flags or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
        val params = WindowManager.LayoutParams(
            metrics.widthPixels, metrics.heightPixels, type, flags, PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            title = "ScreenTranslatorOverlay"
        }
        return try {
            windowManager.addView(view, params)
            overlay = view
            true
        } catch (e: Exception) {
            report(e.message ?: e.javaClass.simpleName)
            false
        }
    }

    // ---- Network source ----

    private fun startNetwork() {
        if (server != null) return
        val prefs = Prefs(this)
        val s = RemoteOverlayServer(
            port = RemoteOverlayServer.PORT,
            token = prefs.remoteToken,
            screenSize = { metrics.widthPixels to metrics.heightPixels },
            onFrame = { frame -> main.post { showRemote(frame) } },
            onClear = { main.post { showRemote(RemoteFrame(emptyList(), 0)) } },
            status = {
                val st = ScreenTranslatorState.status.value
                JSONObject().put("ocr", st.ocr).put("ocrBoxes", st.boxes).put("remoteBoxes", st.remoteBoxes)
            },
        )
        try {
            s.start()
        } catch (e: Exception) {
            report(getString(R.string.screen_err_port, RemoteOverlayServer.PORT, e.message ?: ""))
            return
        }
        server = s
        val urls = RemoteOverlayServer.lanAddresses().map { "http://$it:${RemoteOverlayServer.PORT}" }
        ScreenTranslatorState.update { it.copy(network = true, networkUrls = urls, lastError = null) }
    }

    private fun showRemote(frame: RemoteFrame) {
        val view = overlay ?: return
        val w = metrics.widthPixels.toFloat()
        val h = metrics.heightPixels.toFloat()
        view.setRemoteBoxes(frame.boxes.map {
            OverlayBox(RectF(it.x * w, it.y * h, (it.x + it.w) * w, (it.y + it.h) * h), it.text, it.lines, it.background, it.foreground)
        })
        val generation = ++remoteGeneration
        if (frame.ttlMs > 0 && frame.boxes.isNotEmpty()) {
            main.postDelayed({
                if (generation == remoteGeneration) {
                    overlay?.setRemoteBoxes(emptyList())
                    ScreenTranslatorState.update { it.copy(remoteBoxes = 0) }
                }
            }, frame.ttlMs)
        }
        ScreenTranslatorState.update { it.copy(remoteBoxes = frame.boxes.size) }
    }

    private fun stopNetwork() {
        server?.stop()
        server = null
        remoteGeneration++
        overlay?.setRemoteBoxes(emptyList())
        ScreenTranslatorState.update { it.copy(network = false, networkUrls = emptyList(), remoteBoxes = 0) }
    }

    // ---- OCR source ----

    private fun startOcr(resultCode: Int, data: Intent) {
        val mpm = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        val mp = mpm.getMediaProjection(resultCode, data) ?: error("MediaProjection denied")
        projection = mp
        // Must be registered before createVirtualDisplay on Android 14+.
        mp.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() {
                main.post {
                    stopOcr()
                    stopIfIdle()
                }
            }
        }, main)

        val thread = HandlerThread("screen-translator").apply { start() }
        val handler = Handler(thread.looper)
        worker = thread
        workerHandler = handler

        scale = minOf(1f, CAPTURE_MAX_WIDTH.toFloat() / metrics.widthPixels)
        val capW = ((metrics.widthPixels * scale).toInt() / 2) * 2
        val capH = ((metrics.heightPixels * scale).toInt() / 2) * 2
        scale = capW.toFloat() / metrics.widthPixels

        val imageReader = ImageReader.newInstance(capW, capH, PixelFormat.RGBA_8888, 3)
        reader = imageReader
        virtualDisplay = mp.createVirtualDisplay(
            "screen-translator", capW, capH, metrics.densityDpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, imageReader.surface, null, handler,
        )

        val prefs = Prefs(this)
        textTranslator = ScreenTextTranslator { prefs.serverUrl }.also { t ->
            t.downloadModel { status -> ScreenTranslatorState.update { it.copy(model = status) } }
        }
        lastSignature = null
        lastCleanAt = 0L
        recheckAfterOcr = false
        ocrRunning = true
        ScreenTranslatorState.update { it.copy(ocr = true, boxes = 0, frames = 0, ocrRuns = 0, lastError = null) }
        handler.postDelayed(::tick, INTERVAL_MS)
    }

    private fun stopOcr() {
        ocrRunning = false
        worker?.quitSafely()
        worker = null
        workerHandler = null
        virtualDisplay?.release()
        virtualDisplay = null
        reader?.close()
        reader = null
        projection?.stop()
        projection = null
        textTranslator?.close()
        textTranslator = null
        overlay?.setOcrBoxes(emptyList())
        ScreenTranslatorState.update { it.copy(ocr = false, boxes = 0) }
        if (server != null) enterForeground(withProjection = false)
    }

    private fun tick() {
        if (!ocrRunning) return
        try {
            step()
        } catch (e: Exception) {
            Log.w(TAG, "frame failed", e)
            ScreenTranslatorState.update { it.copy(lastError = e.message ?: e.javaClass.simpleName) }
        }
        if (ocrRunning) workerHandler?.postDelayed(::tick, INTERVAL_MS)
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
        // With boxes shown, a refresh means hiding them (a visible blink). A static screen sends no frames,
        // so only re-check once after an OCR run, in case the screen changed while it was running.
        if (image == null && hasBoxes && !recheckAfterOcr) return
        val clean = if (hasBoxes) captureWithoutOverlay() else lastVisible?.copy(Bitmap.Config.ARGB_8888, false)
        clean ?: return
        lastCleanAt = now
        recheckAfterOcr = false

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
        if (!ocrRunning) return
        onMain { overlay?.setOcrBoxes(boxes) }
        settleAndDrain()
        recheckAfterOcr = true
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

    /**
     * Takes the frames produced by our own overlay changes so they do not trigger an immediate OCR run.
     * They are kept as [lastVisible]: the screen underneath may have changed meanwhile (e.g. while OCR ran),
     * and a static screen sends no further frames, so the periodic refresh must compare against this one.
     */
    private fun settleAndDrain() {
        SystemClock.sleep(OWN_SETTLE_MS)
        val image = reader?.acquireLatestImage() ?: return
        val bmp = Frames.toBitmap(image)
        image.close()
        lastVisible?.recycle()
        lastVisible = bmp
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

    // ---- Lifecycle ----

    private fun enterForeground(withProjection: Boolean) {
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
        val open = PendingIntent.getActivity(
            this, 2,
            Intent(this, MainActivity::class.java).putExtra(MainActivity.EXTRA_OPEN_SCREEN_MODE, true),
            immutable,
        )
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(getString(R.string.screen_notification_title))
            .setContentText(getString(R.string.screen_notification_text))
            .setContentIntent(open)
            .addAction(0, getString(R.string.screen_stop_all), stop)
            .setOngoing(true)
            .build()
        when {
            Build.VERSION.SDK_INT >= 34 -> {
                var type = ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
                if (withProjection) type = type or ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION
                startForeground(NOTIFICATION_ID, notification, type)
            }
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && withProjection ->
                startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
            else -> startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun stopIfIdle() {
        if (projection == null && server == null) stopSelf()
    }

    private fun report(message: String) {
        ScreenTranslatorState.update { it.copy(lastError = message) }
    }

    override fun onDestroy() {
        stopNetwork()
        stopOcr()
        overlay?.let { runCatching { windowManager.removeView(it) } }
        overlay = null
        lastVisible?.recycle()
        lastVisible = null
        super.onDestroy()
    }

    companion object {
        const val ACTION_STOP = "com.qquaq.livetranslatetv.screen.STOP"
        const val ACTION_STOP_OCR = "com.qquaq.livetranslatetv.screen.STOP_OCR"
        const val ACTION_START_NETWORK = "com.qquaq.livetranslatetv.screen.START_NETWORK"
        const val ACTION_STOP_NETWORK = "com.qquaq.livetranslatetv.screen.STOP_NETWORK"
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
