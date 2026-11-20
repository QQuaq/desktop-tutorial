package com.qquaq.livetranslatetv.screen

import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Rect
import android.media.Image

object Frames {
    private const val SIG_W = 96
    private const val SIG_H = 54

    fun toBitmap(image: Image): Bitmap {
        val plane = image.planes[0]
        val pixelStride = plane.pixelStride
        val rowPadding = plane.rowStride - pixelStride * image.width
        val padded = Bitmap.createBitmap(image.width + rowPadding / pixelStride, image.height, Bitmap.Config.ARGB_8888)
        padded.copyPixelsFromBuffer(plane.buffer.rewind())
        if (padded.width == image.width) return padded
        return Bitmap.createBitmap(padded, 0, 0, image.width, image.height).also { padded.recycle() }
    }

    /** Coarse luminance thumbnail used to skip OCR when the screen did not really change. */
    fun signature(bitmap: Bitmap): IntArray {
        val small = Bitmap.createScaledBitmap(bitmap, SIG_W, SIG_H, true)
        val px = IntArray(SIG_W * SIG_H)
        small.getPixels(px, 0, SIG_W, 0, 0, SIG_W, SIG_H)
        if (small !== bitmap) small.recycle()
        return IntArray(px.size) { luminance(px[it]) }
    }

    /** Average colour of a thin ring just outside [rect], i.e. the background the text sits on. */
    fun backgroundColor(bitmap: Bitmap, rect: Rect): Int {
        val pad = 3
        val left = (rect.left - pad).coerceIn(0, bitmap.width - 1)
        val right = (rect.right + pad).coerceIn(0, bitmap.width - 1)
        val top = (rect.top - pad).coerceIn(0, bitmap.height - 1)
        val bottom = (rect.bottom + pad).coerceIn(0, bitmap.height - 1)
        var r = 0L; var g = 0L; var b = 0L; var n = 0
        fun add(x: Int, y: Int) {
            val c = bitmap.getPixel(x, y)
            r += Color.red(c); g += Color.green(c); b += Color.blue(c); n++
        }
        val stepX = maxOf(1, (right - left) / 24)
        val stepY = maxOf(1, (bottom - top) / 8)
        for (x in left..right step stepX) { add(x, top); add(x, bottom) }
        for (y in top..bottom step stepY) { add(left, y); add(right, y) }
        if (n == 0) return Color.BLACK
        return Color.rgb((r / n).toInt(), (g / n).toInt(), (b / n).toInt())
    }

    fun luminance(c: Int): Int = (Color.red(c) * 299 + Color.green(c) * 587 + Color.blue(c) * 114) / 1000
}
