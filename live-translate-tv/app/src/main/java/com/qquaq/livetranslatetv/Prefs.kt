package com.qquaq.livetranslatetv

import android.content.Context

class Prefs(context: Context) {
    private val sp = context.applicationContext.getSharedPreferences("live-translate-tv", Context.MODE_PRIVATE)

    var serverUrl: String
        get() = sp.getString("server_url", "") ?: ""
        set(value) = sp.edit().putString("server_url", value.trim()).apply()

    var speakEnabled: Boolean
        get() = sp.getBoolean("speak", false)
        set(value) = sp.edit().putBoolean("speak", value).apply()

    /** "tr" (default) or "en". */
    var uiLanguage: String
        get() = sp.getString("ui_lang", "tr") ?: "tr"
        set(value) = sp.edit().putString("ui_lang", value).apply()
}
