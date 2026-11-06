package com.airscreen.networking

import java.math.BigInteger
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.interfaces.ECPublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECParameterSpec
import java.security.spec.ECPoint
import java.security.spec.ECPublicKeySpec
import java.security.KeyPairGenerator
import java.security.PrivateKey
import java.security.SecureRandom
import javax.crypto.KeyAgreement
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

    // ---- approval pairing: short pair key, X25519 key exchange, 4-digit number both screens show ----
    const val KEY_LENGTH = 6
    private val ecSpec: ECParameterSpec by lazy {
        val ap = AlgorithmParameters.getInstance("EC")
        ap.init(ECGenParameterSpec("secp256r1"))
        ap.getParameterSpec(ECParameterSpec::class.java)
    }

    fun newPairKey(): String = buildString { repeat(KEY_LENGTH) { append(CODE_ALPHABET[random.nextInt(CODE_ALPHABET.length)]) } }
    fun formatKey(key: String): String = key.chunked(3).joinToString("-")

    private fun fixed32(v: BigInteger): ByteArray {
        val b = v.toByteArray()
        return when {
            b.size == 32 -> b
            b.size > 32 -> b.copyOfRange(b.size - 32, b.size)
            else -> ByteArray(32 - b.size) + b
        }
    }

    /** (private key, 65-byte uncompressed P-256 public point). P-256 works on every Android version. */
    fun newKeyPair(): Pair<PrivateKey, ByteArray> {
        val g = KeyPairGenerator.getInstance("EC")
        g.initialize(ECGenParameterSpec("secp256r1"))
        val kp = g.generateKeyPair()
        val w = (kp.public as ECPublicKey).w
        return kp.private to (byteArrayOf(4) + fixed32(w.affineX) + fixed32(w.affineY))
    }

    fun ecdh(priv: PrivateKey, peerRaw: ByteArray): ByteArray {
        require(peerRaw.size == 65 && peerRaw[0] == 4.toByte()) { "bad public key" }
        val x = BigInteger(1, peerRaw.copyOfRange(1, 33))
        val y = BigInteger(1, peerRaw.copyOfRange(33, 65))
        val pub = KeyFactory.getInstance("EC").generatePublic(ECPublicKeySpec(ECPoint(x, y), ecSpec))   // rejects points off the curve
        val ka = KeyAgreement.getInstance("ECDH")
        ka.init(priv)
        ka.doPhase(pub, true)
        return ka.generateSecret()
    }

    fun sas(shared: ByteArray, ns: ByteArray, nr: ByteArray): String {
        val h = hmac(shared, "AirScreen-verify".toByteArray(), ns, nr)
        val n = ((h[0].toLong() and 0xFF) shl 24) or ((h[1].toLong() and 0xFF) shl 16) or ((h[2].toLong() and 0xFF) shl 8) or (h[3].toLong() and 0xFF)
        return "%04d".format(n % 10000)
    }

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
