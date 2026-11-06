package com.airscreen.networking

/**
 * Holds the current pairing code shown on the TV. The code expires, rotates after a successful pairing
 * and after too many failed attempts (rate limiting), so it cannot be guessed online.
 */
class PairingManager(private val onChanged: (String) -> Unit = {}) {
    @Volatile private var code = Crypto.newPairingCode()
    private var issuedAt = System.currentTimeMillis()
    private var failures = 0
    private var lockedUntil = 0L

    @Synchronized
    fun displayCode(): String {
        rotateIfExpired()
        return Crypto.formatCode(code)
    }

    /** Secret to authenticate a pairing attempt, or null while locked out. */
    @Synchronized
    fun secretForAttempt(): ByteArray? {
        rotateIfExpired()
        return if (System.currentTimeMillis() < lockedUntil) null else code.toByteArray()
    }

    @Synchronized
    fun registerFailure() {
        failures++
        if (failures >= MAX_FAILURES) {
            lockedUntil = System.currentTimeMillis() + LOCKOUT_MS
            rotate()
        }
    }

    @Synchronized
    fun rotate() {
        code = Crypto.newPairingCode()
        issuedAt = System.currentTimeMillis()
        failures = 0
        onChanged(Crypto.formatCode(code))
    }

    private fun rotateIfExpired() {
        if (System.currentTimeMillis() - issuedAt > EXPIRY_MS) rotate()
    }

    private companion object {
        const val MAX_FAILURES = 5
        const val LOCKOUT_MS = 30_000L
        const val EXPIRY_MS = 10 * 60_000L
    }
}
