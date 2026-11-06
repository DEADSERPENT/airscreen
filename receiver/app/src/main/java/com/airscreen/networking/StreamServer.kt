package com.airscreen.networking

import android.util.Base64
import com.airscreen.config.TrustStore
import org.json.JSONException
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.DataInputStream
import java.io.EOFException
import java.io.IOException
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException
import java.security.MessageDigest
import javax.crypto.AEADBadTagException

/**
 * Listens for one AirScreen sender at a time. Every sender must authenticate (pairing code once,
 * then its stored device key) before any media is accepted; media is AES-GCM encrypted.
 * All [Listener] callbacks run on the server thread; an exception thrown from a callback ends the session.
 */
class StreamServer(
    private val port: Int,
    private val trust: TrustStore,
    private val pairing: PairingManager,
    private val capabilities: () -> JSONObject,
    private val listener: Listener,
) {
    data class AudioInfo(val head: ByteArray, val rate: Int, val channels: Int)
    data class Hello(val width: Int, val height: Int, val fps: Int, val audio: AudioInfo?)

    interface Listener {
        fun onWaiting()
        fun onConnected(remote: String)
        /** Blocks the server thread until the person at the TV answers (or ~30 s pass). Must return false on timeout. */
        fun onPairRequest(senderName: String, verify: String?): Boolean
        fun onPaired()
        fun onHello(hello: Hello)
        fun onVideo(data: ByteArray, ptsUs: Long, keyframe: Boolean)
        fun onAudio(data: ByteArray, ptsUs: Long)
        fun onSessionEnded(reason: String)
        fun onFatalError(message: String)
    }

    @Volatile private var running = false
    @Volatile private var server: ServerSocket? = null
    @Volatile private var client: Socket? = null
    private var thread: Thread? = null

    fun start() {
        if (running) return
        running = true
        thread = Thread({ run() }, "airscreen-server").also { it.start() }
    }

    fun stop() {
        running = false
        closeQuietly(client)
        closeQuietly(server)
        thread?.join(2000)
        thread = null
    }

    /** Drops the current sender but keeps listening. */
    fun disconnectSender() = closeQuietly(client)

    private fun run() {
        val s = try {
            ServerSocket().apply {
                reuseAddress = true
                bind(InetSocketAddress(port))
            }
        } catch (e: IOException) {
            if (running) listener.onFatalError("Cannot listen on port $port: ${e.message}")
            return
        }
        server = s
        while (running) {
            listener.onWaiting()
            val c = try {
                s.accept()
            } catch (e: IOException) {
                break // server socket closed by stop()
            }
            client = c
            val reason = serve(c)
            closeQuietly(c)
            client = null
            if (running) listener.onSessionEnded(reason)
        }
        closeQuietly(s)
    }

    private fun serve(c: Socket): String {
        try {
            c.tcpNoDelay = true
            c.soTimeout = HANDSHAKE_TIMEOUT_MS
            val input = DataInputStream(BufferedInputStream(c.getInputStream(), 64 * 1024))
            val out = c.getOutputStream()
            listener.onConnected(c.remoteSocketAddress.toString().trimStart('/'))

            val headerBytes = ByteArray(Protocol.HEADER_SIZE)
            val cipher = authenticate(input, out, headerBytes)
            c.soTimeout = READ_TIMEOUT_MS // a silent sender must not hold the receiver forever

            var expectedSeq = 0L
            var gotHello = false
            while (running) {
                input.readFully(headerBytes)
                val h = Protocol.parseHeader(headerBytes)
                if (h.seq != expectedSeq) throw Protocol.ProtocolException("sequence gap: expected $expectedSeq got ${h.seq}")
                expectedSeq = (expectedSeq + 1) and 0xFFFFFFFFL
                if (h.type >= Protocol.TYPE_AUTH_REQUEST) throw Protocol.ProtocolException("unexpected auth message")
                if (h.length < TAG_BYTES) throw Protocol.ProtocolException("payload shorter than auth tag")

                val sealed = ByteArray(h.length).also { input.readFully(it) }
                val payload = cipher.open(h.seq, sealed, headerBytes) // AEADBadTagException if tampered

                when (h.type) {
                    Protocol.TYPE_HELLO -> {
                        if (gotHello) throw Protocol.ProtocolException("duplicate hello")
                        if (payload.size > Protocol.MAX_CONTROL_PAYLOAD) throw Protocol.ProtocolException("hello too large")
                        gotHello = true
                        listener.onHello(parseHello(payload))
                    }
                    Protocol.TYPE_VIDEO -> {
                        if (!gotHello) throw Protocol.ProtocolException("video before hello")
                        listener.onVideo(payload, h.ptsUs, h.keyframe)
                    }
                    Protocol.TYPE_AUDIO -> {
                        if (!gotHello) throw Protocol.ProtocolException("audio before hello")
                        listener.onAudio(payload, h.ptsUs)
                    }
                    Protocol.TYPE_BYE -> return "Sender disconnected"
                }
            }
            return "Stopped"
        } catch (e: Protocol.ProtocolException) {
            return "Rejected sender: ${e.message}"
        } catch (e: AEADBadTagException) {
            return "Rejected sender: corrupted or forged data"
        } catch (e: SocketTimeoutException) {
            return "Sender stopped responding"
        } catch (e: EOFException) {
            return "Sender closed the connection"
        } catch (e: IOException) {
            return if (running && client != null) "Connection lost" else "Disconnected"
        } catch (e: JSONException) {
            return "Rejected sender: malformed message"
        } catch (e: Exception) {
            return "Error: ${e.message ?: e.javaClass.simpleName}"
        }
    }

    // --- authentication (mirrors networking/tcp_sender.py: handshake) ---
    private fun authenticate(input: DataInputStream, out: OutputStream, headerBytes: ByteArray): Crypto.MediaCipher {
        input.readFully(headerBytes)
        val h1 = Protocol.parseHeader(headerBytes)
        if (h1.type != Protocol.TYPE_AUTH_REQUEST) throw Protocol.ProtocolException("expected authentication first")
        val req = JSONObject(String(ByteArray(h1.length).also { input.readFully(it) }, Charsets.UTF_8))
        val deviceId = req.getString("device_id")
        if (!DEVICE_ID_REGEX.matches(deviceId)) throw Protocol.ProtocolException("bad device id")
        val ns = Crypto.unhex(req.getString("ns"))
        if (ns.size != 16) throw Protocol.ProtocolException("bad nonce")

        val nr = Crypto.randomBytes(16)
        val trustedKey = trust.getKey(deviceId)
        val eph = try { Crypto.newKeyPair() } catch (e: Exception) { null }       // P-256: supported on every Android version
        val challenge = JSONObject()
            .put("nr", Crypto.hex(nr)).put("receiver_id", trust.receiverId).put("name", trust.name)
            .put("trusted", trustedKey != null).put("caps", capabilities())
        if (eph != null) challenge.put("rpub", Crypto.hex(eph.second))
        send(out, Protocol.TYPE_AUTH_CHALLENGE, 0, challenge)

        input.readFully(headerBytes)
        val h2 = Protocol.parseHeader(headerBytes)
        if (h2.type != Protocol.TYPE_AUTH_PROOF) throw Protocol.ProtocolException("expected proof")
        val proof = JSONObject(String(ByteArray(h2.length).also { input.readFully(it) }, Charsets.UTF_8))
        val mode = proof.getString("mode")

        if (mode == "request") {
            // New PC: it must show the pair key from this screen, then a person approves here. Never silent.
            val e = eph ?: fail(out, "this TV cannot pair by approval")
            val keyBytes = pairing.secretForAttempt() ?: fail(out, "pairing is locked, try again shortly")
            val given = proof.optString("key", "").uppercase().toByteArray()
            if (!MessageDigest.isEqual(keyBytes, given)) {
                pairing.registerFailure()
                fail(out, "wrong pair key")
            }
            val peer = Crypto.unhex(proof.getString("pub"))
            if (peer.size != 65) throw Protocol.ProtocolException("bad key")
            val shared = Crypto.ecdh(e.first, peer)
            val verify = Crypto.sas(shared, ns, nr)                    // the PC shows the same number: a mismatch means someone is in the middle
            if (!listener.onPairRequest(sanitizeName(req.optString("name", "PC")), verify)) {
                fail(out, "The TV did not approve this request")
            }
            send(out, Protocol.TYPE_AUTH_OK, 1, JSONObject().put("proof", Crypto.hex(Crypto.serverProof(shared, ns, nr))))
            trust.trust(deviceId, Crypto.deviceKey(shared, ns, nr))
            pairing.rotate()                                           // a pair key is single-use
            listener.onPaired()
            return Crypto.MediaCipher(Crypto.sessionKey(shared, ns, nr))
        }

        val secret = trustedKey ?: fail(out, "this device is not paired")
        val expected = Crypto.clientProof(secret, ns, nr, deviceId)
        if (!MessageDigest.isEqual(expected, Crypto.unhex(proof.getString("proof")))) {
            trust.revoke(deviceId)
            fail(out, "authentication failed")
        }
        send(out, Protocol.TYPE_AUTH_OK, 1, JSONObject().put("proof", Crypto.hex(Crypto.serverProof(secret, ns, nr))))
        return Crypto.MediaCipher(Crypto.sessionKey(secret, ns, nr))
    }

    /** The sender's display name is untrusted input shown on the TV: strip control characters, cap the length. */
    private fun sanitizeName(raw: String): String {
        val cleaned = raw.filter { it >= ' ' && it != '\u007f' }.trim().take(40)
        return cleaned.ifEmpty { "A PC" }
    }

    private fun fail(out: OutputStream, reason: String): Nothing {
        try {
            send(out, Protocol.TYPE_AUTH_FAIL, 1, JSONObject().put("reason", reason))
        } catch (_: IOException) {
        }
        throw Protocol.ProtocolException(reason)
    }

    private fun send(out: OutputStream, type: Int, seq: Long, body: JSONObject) {
        val payload = body.toString().toByteArray(Charsets.UTF_8)
        out.write(Protocol.buildHeader(type, seq, 0, payload.size) + payload)
        out.flush()
    }

    private fun parseHello(payload: ByteArray): Hello {
        try {
            val o = JSONObject(String(payload, Charsets.UTF_8))
            val codec = o.getString("codec")
            if (codec != "h264") throw Protocol.ProtocolException("unsupported codec $codec")
            val w = o.getInt("width")
            val h = o.getInt("height")
            val fps = o.getInt("fps")
            if (w !in 16..8192 || h !in 16..8192) throw Protocol.ProtocolException("bad resolution ${w}x$h")
            if (fps !in 1..240) throw Protocol.ProtocolException("bad fps $fps")
            var audio: AudioInfo? = null
            o.optJSONObject("audio")?.let { a ->
                if (a.getString("codec") != "opus") throw Protocol.ProtocolException("unsupported audio codec")
                val head = Base64.decode(a.getString("head"), Base64.DEFAULT)
                val rate = a.getInt("rate")
                val ch = a.getInt("channels")
                if (head.size !in 19..64 || String(head, 0, 8, Charsets.US_ASCII) != "OpusHead") throw Protocol.ProtocolException("bad OpusHead")
                if (rate != 48000 || ch !in 1..2) throw Protocol.ProtocolException("unsupported audio format")
                audio = AudioInfo(head, rate, ch)
            }
            return Hello(w, h, fps, audio)
        } catch (e: JSONException) {
            throw Protocol.ProtocolException("bad hello: ${e.message}")
        }
    }

    private fun closeQuietly(c: java.io.Closeable?) {
        try {
            c?.close()
        } catch (_: IOException) {
        }
    }

    companion object {
        const val DEFAULT_PORT = 5000
        private const val HANDSHAKE_TIMEOUT_MS = 10_000
        private const val READ_TIMEOUT_MS = 5000
        private const val TAG_BYTES = 16
        private val DEVICE_ID_REGEX = Regex("^[A-Za-z0-9]{1,64}$")
    }
}
