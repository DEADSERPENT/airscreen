package com.airscreen.config

import android.content.Context
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import com.airscreen.networking.Crypto
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Device keys at rest: AES-GCM under a key that never leaves the Android Keystore. Falls back to plain hex only if the Keystore fails. */
private object KeyBox {
    private const val ALIAS = "airscreen_trust_v1"

    private fun key(): SecretKey? = try {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey(ALIAS, null) as? SecretKey) ?: KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build())
            generateKey()
        }
    } catch (e: Exception) { null }

    fun seal(plain: ByteArray): String {
        val k = key() ?: return Crypto.hex(plain)
        return try {
            val c = Cipher.getInstance("AES/GCM/NoPadding")
            c.init(Cipher.ENCRYPT_MODE, k)
            "ks:" + Base64.encodeToString(c.iv + c.doFinal(plain), Base64.NO_WRAP)
        } catch (e: Exception) { Crypto.hex(plain) }
    }

    /** null = could not be decrypted (treated as "not paired", the PC will simply pair again). */
    fun open(stored: String): ByteArray? {
        if (!stored.startsWith("ks:")) return Crypto.unhex(stored)          // written by an older version
        val k = key() ?: return null
        return try {
            val raw = Base64.decode(stored.substring(3), Base64.NO_WRAP)
            val c = Cipher.getInstance("AES/GCM/NoPadding")
            c.init(Cipher.DECRYPT_MODE, k, GCMParameterSpec(128, raw, 0, 12))
            c.doFinal(raw, 12, raw.size - 12)
        } catch (e: Exception) { null }
    }
}

/** Receiver identity + paired senders (device id -> long-term key), kept in private app storage. */
class TrustStore(context: Context) {
    private val prefs = context.getSharedPreferences("airscreen_trust", Context.MODE_PRIVATE)

    val receiverId: String = prefs.getString("receiver_id", null) ?: Crypto.hex(Crypto.randomBytes(8)).also {
        prefs.edit().putString("receiver_id", it).apply()
    }

    val name: String = "AirScreen " + (Build.MODEL ?: "TV")

    @Synchronized
    fun getKey(deviceId: String): ByteArray? {
        val stored = prefs.getString("dev_$deviceId", null) ?: return null
        val key = KeyBox.open(stored) ?: return null
        if (!stored.startsWith("ks:")) {                                      // migrate an old plaintext entry
            val sealed = KeyBox.seal(key)
            if (sealed.startsWith("ks:")) prefs.edit().putString("dev_$deviceId", sealed).apply()
        }
        return key
    }

    @Synchronized
    fun trust(deviceId: String, key: ByteArray) {
        prefs.edit().putString("dev_$deviceId", KeyBox.seal(key)).apply()
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
