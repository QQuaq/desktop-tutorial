package com.qquaq.livetranslatetv

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
    fun longTextIsChunkedOnWordBoundaries() {
        val text = List(200) { "word$it" }.joinToString(" ")
        val parts = Translator.chunks(text)
        assertTrue(parts.size > 1)
        assertTrue(parts.all { it.length <= 450 })
        assertEquals(text, parts.joinToString(" "))
    }
}
