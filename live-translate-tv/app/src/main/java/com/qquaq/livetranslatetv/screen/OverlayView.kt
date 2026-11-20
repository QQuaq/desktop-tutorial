package com.qquaq.livetranslatetv.screen

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import android.view.View

/** Overlay box in screen pixels. */
data class OverlayBox(
    val rect: RectF,
    val text: String,
    val lines: Int,
    val background: Int,
    val foreground: Int,
)

/** Full-screen, non-interactive view that paints each translation over the English it replaces. */
class OverlayView(context: Context) : View(context) {
    private val bgPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val textPaint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply { typeface = Typeface.DEFAULT_BOLD }
    private val minTextPx = 10f * resources.displayMetrics.density
    private var boxes: List<OverlayBox> = emptyList()

    val hasBoxes: Boolean get() = boxes.isNotEmpty()

    fun setBoxes(newBoxes: List<OverlayBox>) {
        boxes = newBoxes
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        for (box in boxes) {
            val pad = box.rect.height() * 0.08f + 2f
            val area = RectF(box.rect.left - pad, box.rect.top - pad, box.rect.right + pad, box.rect.bottom + pad)
            bgPaint.color = box.background
            canvas.drawRoundRect(area, pad, pad, bgPaint)

            textPaint.color = box.foreground
            val width = area.width().toInt().coerceAtLeast(1)
            val layout = fitText(box, width, area.height())
            canvas.save()
            canvas.translate(area.left, area.top + ((area.height() - layout.height) / 2f).coerceAtLeast(0f))
            if (layout.height > area.height()) {
                // Longer than the English: grow downward on an opaque strip rather than clipping.
                canvas.drawRoundRect(RectF(0f, 0f, area.width(), layout.height.toFloat()), pad, pad, bgPaint)
            }
            layout.draw(canvas)
            canvas.restore()
        }
    }

    private fun fitText(box: OverlayBox, width: Int, height: Float): StaticLayout {
        var size = (box.rect.height() / box.lines) * 0.78f
        var layout = makeLayout(box.text, width, size)
        while (layout.height > height && size > minTextPx) {
            size *= 0.9f
            layout = makeLayout(box.text, width, size)
        }
        return layout
    }

    @Suppress("DEPRECATION")
    private fun makeLayout(text: String, width: Int, size: Float): StaticLayout {
        textPaint.textSize = size
        return StaticLayout(text, textPaint, width, Layout.Alignment.ALIGN_NORMAL, 1.0f, 0f, false)
    }
}
