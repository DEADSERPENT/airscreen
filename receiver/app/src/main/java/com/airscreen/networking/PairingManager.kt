package com.airscreen.networking

/**
 * Holds the current pairing code shown on the TV. The code expires, rotates after a successful pairing
 * and after too many failed attempts (rate limiting), so it cannot be guessed online.
 */
class PairingManager(private val onChanged: (String) -> Unit = {}) {
    @Volatile private var code = Crypto.newPairKey()
    private var issuedAt = System.currentTimeMillis()

    @Synchronized
    fun displayCode(): String {
        rotateIfExpired()
        return Crypto.formatKey(code)
    }

    private class Peer { var failures = 0; var lockedUntil = 0L; var locks = 0 }
    private val peers = HashMap<String, Peer>()
    private val lockEvents = ArrayDeque<Long>()

    /** Secret to authenticate a pairing attempt, or null while THIS host is locked out (other hosts are unaffected). */
    @Synchronized
    fun secretForAttempt(ip: String): ByteArray? {
        rotateIfExpired()
        val p = peers[ip]
        return if (p != null && System.currentTimeMillis() < p.lockedUntil) null else code.toByteArray()
    }

    /** 5 wrong tries lock that host for 60 s (doubling to 15 min). The key only rotates when several hosts get locked out. */
    @Synchronized
    fun registerFailure(ip: String) {
        val now = System.currentTimeMillis()
        if (peers.size > 256) peers.clear()
        val p = peers.getOrPut(ip) { Peer() }
        p.failures++
        if (p.failures >= MAX_FAILURES) {
            p.failures = 0
            p.locks++
            p.lockedUntil = now + minOf(LOCKOUT_MS shl (p.locks - 1).coerceAtMost(4), MAX_LOCKOUT_MS)
            lockEvents.addLast(now)
            while (lockEvents.isNotEmpty() && now - lockEvents.first() > 10 * 60_000L) lockEvents.removeFirst()
            if (lockEvents.size >= 3) { lockEvents.clear(); rotate() }       // distributed guessing: the key must not stay valid
        }
    }

    @Synchronized
    fun rotate() {
        code = Crypto.newPairKey()
        issuedAt = System.currentTimeMillis()
        onChanged(Crypto.formatKey(code))
    }

    private fun rotateIfExpired() {
        if (System.currentTimeMillis() - issuedAt > EXPIRY_MS) rotate()
    }

    private companion object {
        const val MAX_FAILURES = 5
        const val LOCKOUT_MS = 60_000L
        const val MAX_LOCKOUT_MS = 15 * 60_000L
        const val EXPIRY_MS = 10 * 60_000L
    }
}
