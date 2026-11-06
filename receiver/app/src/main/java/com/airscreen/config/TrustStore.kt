package com.airscreen.config

import android.content.Context
import android.os.Build
import com.airscreen.networking.Crypto

/** Receiver identity + paired senders (device id -> long-term key), kept in private app storage. */
class TrustStore(context: Context) {
    private val prefs = context.getSharedPreferences("airscreen_trust", Context.MODE_PRIVATE)

    val receiverId: String = prefs.getString("receiver_id", null) ?: Crypto.hex(Crypto.randomBytes(8)).also {
        prefs.edit().putString("receiver_id", it).apply()
    }

    val name: String = "AirScreen " + (Build.MODEL ?: "TV")

    @Synchronized
    fun getKey(deviceId: String): ByteArray? = prefs.getString("dev_$deviceId", null)?.let { Crypto.unhex(it) }

    @Synchronized
    fun trust(deviceId: String, key: ByteArray) {
        prefs.edit().putString("dev_$deviceId", Crypto.hex(key)).apply()
    }

    @Synchronized
    fun revoke(deviceId: String) {
        prefs.edit().remove("dev_$deviceId").apply()
    }

    @Synchronized
    fun revokeAll() {
        val e = prefs.edit()
        prefs.all.keys.filter { it.startsWith("dev_") }.forEach { e.remove(it) }
        e.apply()
    }

    @Synchronized
    fun trustedCount(): Int = prefs.all.keys.count { it.startsWith("dev_") }
}
