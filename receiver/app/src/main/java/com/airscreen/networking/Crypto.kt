package com.airscreen.networking

import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.Mac
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/** Mirror of sender/airscreen_sender/networking/crypto.py - verified against shared/test-data/crypto_vectors.json. */
object Crypto {
    const val CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    const val CODE_LENGTH = 16
    const val TAG_BITS = 128

    private val random = SecureRandom()

    fun newPairingCode(): String =
        buildString { repeat(CODE_LENGTH) { append(CODE_ALPHABET[random.nextInt(CODE_ALPHABET.length)]) } }

    fun formatCode(code: String): String = code.chunked(4).joinToString("-")

    fun randomBytes(n: Int): ByteArray = ByteArray(n).also { random.nextBytes(it) }

    private fun hmac(key: ByteArray, vararg parts: ByteArray): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        parts.forEach { mac.update(it) }
        return mac.doFinal()
    }

    /** HKDF-SHA256, single 32-byte block (all our outputs are 32 bytes). */
    fun hkdf(ikm: ByteArray, salt: ByteArray, info: ByteArray): ByteArray {
        val prk = hmac(salt, ikm)
        return hmac(prk, info, byteArrayOf(1))
    }

    fun clientProof(key: ByteArray, ns: ByteArray, nr: ByteArray, deviceId: String): ByteArray =
        hmac(key, "AirScreen-client".toByteArray(), ns, nr, deviceId.toByteArray())

    fun serverProof(key: ByteArray, ns: ByteArray, nr: ByteArray): ByteArray =
        hmac(key, "AirScreen-server".toByteArray(), ns, nr)

    fun deviceKey(secret: ByteArray, ns: ByteArray, nr: ByteArray): ByteArray =
        hkdf(secret, ns + nr, "AirScreen-device-key".toByteArray())

    fun sessionKey(key: ByteArray, ns: ByteArray, nr: ByteArray): ByteArray =
        hkdf(key, ns + nr, "AirScreen-session".toByteArray())

    fun hex(b: ByteArray): String = b.joinToString("") { "%02x".format(it) }

    fun unhex(s: String): ByteArray {
        require(s.length % 2 == 0) { "odd hex length" }
        return ByteArray(s.length / 2) { s.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
    }

    /** AES-256-GCM; nonce = 8 zero bytes + seq (big-endian u32). The session key is unique per connection. */
    class MediaCipher(key: ByteArray) {
        private val keySpec = SecretKeySpec(key, "AES")

        private fun nonce(seq: Long): ByteArray {
            val n = ByteArray(12)
            for (i in 0 until 4) n[11 - i] = ((seq shr (8 * i)) and 0xFF).toByte()
            return n
        }

        /** Throws [javax.crypto.AEADBadTagException] if the data was tampered with. */
        fun open(seq: Long, ciphertext: ByteArray, aad: ByteArray): ByteArray {
            val c = Cipher.getInstance("AES/GCM/NoPadding")
            c.init(Cipher.DECRYPT_MODE, keySpec, GCMParameterSpec(TAG_BITS, nonce(seq)))
            c.updateAAD(aad)
            return c.doFinal(ciphertext)
        }

        fun seal(seq: Long, plaintext: ByteArray, aad: ByteArray): ByteArray {
            val c = Cipher.getInstance("AES/GCM/NoPadding")
            c.init(Cipher.ENCRYPT_MODE, keySpec, GCMParameterSpec(TAG_BITS, nonce(seq)))
            c.updateAAD(aad)
            return c.doFinal(plaintext)
        }
    }
}
