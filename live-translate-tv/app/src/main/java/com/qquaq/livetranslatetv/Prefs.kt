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

    /** Shared secret a PC/phone must send to push overlay text over the LAN; generated once. */
    val remoteToken: String
        get() = sp.getString("remote_token", null) ?: newToken().also {
            sp.edit().putString("remote_token", it).apply()
        }

    fun resetRemoteToken() = sp.edit().putString("remote_token", newToken()).apply()

    private fun newToken(): String {
        val alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
        val random = java.security.SecureRandom()
        return (1..8).map { alphabet[random.nextInt(alphabet.length)] }.joinToString("")
    }

    /** "tr" (default) or "en". */
    var uiLanguage: String
        get() = sp.getString("ui_lang", "tr") ?: "tr"
        set(value) = sp.edit().putString("ui_lang", value).apply()
}
