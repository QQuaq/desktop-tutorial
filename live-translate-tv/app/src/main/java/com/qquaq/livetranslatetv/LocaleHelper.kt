package com.qquaq.livetranslatetv

import android.content.Context
import android.content.res.Configuration
import java.util.Locale

/** Applies the in-app UI language (Turkish by default) instead of the device language. */
fun Context.withAppLocale(): Context {
    val locale = Locale(Prefs(this).uiLanguage)
    Locale.setDefault(locale)
    val config = Configuration(resources.configuration).apply { setLocale(locale) }
    return createConfigurationContext(config)
}
