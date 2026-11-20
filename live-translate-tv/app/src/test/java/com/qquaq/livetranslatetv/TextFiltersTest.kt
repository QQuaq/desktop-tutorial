package com.qquaq.livetranslatetv

import com.qquaq.livetranslatetv.screen.Frames
import com.qquaq.livetranslatetv.screen.OcrBlock
import com.qquaq.livetranslatetv.screen.ScreenTextTranslator
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TextFiltersTest {
    @Test
    fun englishBlocksAreTranslated() {
        assertTrue(ScreenTextTranslator.looksEnglish("Settings", "en"))
        assertTrue(ScreenTextTranslator.looksEnglish("Continue watching", "und"))
        assertTrue(ScreenTextTranslator.looksEnglish("Press OK to start", ""))
    }

    @Test
    fun turkishNumbersAndOtherLanguagesAreSkipped() {
        assertFalse(ScreenTextTranslator.looksEnglish("Ayarları aç", "und"))
        assertFalse(ScreenTextTranslator.looksEnglish("12:45", "und"))
        assertFalse(ScreenTextTranslator.looksEnglish("A", "en"))
        assertFalse(ScreenTextTranslator.looksEnglish("Einstellungen", "de"))
    }

    @Test
    fun wrappedSentenceSplitIntoTwoBlocksIsMerged() {
        val merged = ScreenTextTranslator.mergeContinuations(
            listOf(
                // Boxes as reported by ML Kit on the emulator (1280x720 capture).
                OcrBlock(56, 452, 766, 477, "Press the button below to start the movie from the", 1, "und"),
                OcrBlock(54, 489, 196, 523, "beginning.", 1, "und"),
                OcrBlock(91, 577, 215, 608, "Play now", 1, "und"),
            ),
        )
        assertEquals(
            listOf("Press the button below to start the movie from the beginning.", "Play now"),
            merged.map { it.text },
        )
        assertEquals(OcrBlock(54, 452, 766, 523, merged[0].text, 2, "und"), merged[0])
    }

    @Test
    fun separateItemsAreNotMerged() {
        val blocks = listOf(
            OcrBlock(100, 100, 400, 130, "Display & Sound", 1, "und"),
            OcrBlock(100, 136, 400, 166, "Network & Internet", 1, "und"),
            OcrBlock(100, 200, 400, 230, "Done.", 1, "und"),
            OcrBlock(100, 236, 400, 266, "then continue", 1, "und"),
            OcrBlock(300, 300, 600, 330, "No colon here", 1, "und"),
            OcrBlock(100, 336, 400, 366, "indented elsewhere", 1, "und"),
            OcrBlock(100, 400, 400, 430, "Far apart", 1, "und"),
            OcrBlock(100, 500, 400, 530, "lowercase but distant", 1, "und"),
        )
        assertEquals(blocks.map { it.text }, ScreenTextTranslator.mergeContinuations(blocks).map { it.text })
    }

    @Test
    fun boxIsStaleOnlyWhereTheScreenChanged() {
        val old = IntArray(96 * 54) { 20 }
        val new = old.copyOf()
        for (y in 0 until 27) for (x in 0 until 48) new[y * 96 + x] = 240
        assertTrue(Frames.regionChanged(old, new, 0.05f, 0.1f, 0.4f, 0.2f, 12))
        assertFalse(Frames.regionChanged(old, new, 0.6f, 0.6f, 0.9f, 0.7f, 12))
        assertFalse(Frames.regionChanged(old, old, 0f, 0f, 1f, 1f, 12))
    }

    @Test
    fun longTextIsChunkedOnWordBoundaries() {
        val text = List(200) { "word$it" }.joinToString(" ")
        val parts = Translator.chunks(text)
        assertTrue(parts.size > 1)
        assertTrue(parts.all { it.length <= 450 })
        assertEquals(text, parts.joinToString(" "))
    }
}
