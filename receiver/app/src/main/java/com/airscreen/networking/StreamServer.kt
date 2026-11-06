package com.airscreen.networking

import org.json.JSONException
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.DataInputStream
import java.io.EOFException
import java.io.IOException
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException

/**
 * Listens for one AirScreen sender at a time. All [Listener] callbacks run on the server thread;
 * an exception thrown from [Listener.onHello] / [Listener.onVideo] ends the session safely.
 */
class StreamServer(private val port: Int, private val listener: Listener) {

    interface Listener {
        fun onWaiting()
        fun onConnected(remote: String)
        fun onHello(width: Int, height: Int, fps: Int)
        fun onVideo(data: ByteArray, ptsUs: Long, keyframe: Boolean)
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
            c.soTimeout = READ_TIMEOUT_MS // a silent sender must not hold the receiver forever
            val input = DataInputStream(BufferedInputStream(c.getInputStream(), 64 * 1024))
            listener.onConnected(c.remoteSocketAddress.toString().trimStart('/'))

            val headerBytes = ByteArray(Protocol.HEADER_SIZE)
            var expectedSeq = 0L
            var gotHello = false
            while (running) {
                input.readFully(headerBytes)
                val h = Protocol.parseHeader(headerBytes)
                if (h.seq != expectedSeq) throw Protocol.ProtocolException("sequence gap: expected $expectedSeq got ${h.seq}")
                expectedSeq = (expectedSeq + 1) and 0xFFFFFFFFL

                when (h.type) {
                    Protocol.TYPE_HELLO -> {
                        if (gotHello) throw Protocol.ProtocolException("duplicate hello")
                        val payload = ByteArray(h.length).also { input.readFully(it) }
                        val (w, hgt, fps) = parseHello(payload)
                        gotHello = true
                        listener.onHello(w, hgt, fps)
                    }
                    Protocol.TYPE_VIDEO -> {
                        if (!gotHello) throw Protocol.ProtocolException("video before hello")
                        val payload = ByteArray(h.length).also { input.readFully(it) }
                        listener.onVideo(payload, h.ptsUs, h.keyframe)
                    }
                    Protocol.TYPE_BYE -> return "Sender disconnected"
                }
            }
            return "Stopped"
        } catch (e: Protocol.ProtocolException) {
            return "Rejected sender: ${e.message}"
        } catch (e: SocketTimeoutException) {
            return "Sender stopped responding"
        } catch (e: EOFException) {
            return "Sender closed the connection"
        } catch (e: IOException) {
            return if (running && client != null) "Connection lost" else "Disconnected"
        } catch (e: Exception) {
            return "Error: ${e.message ?: e.javaClass.simpleName}"
        }
    }

    private fun parseHello(payload: ByteArray): Triple<Int, Int, Int> {
        try {
            val o = JSONObject(String(payload, Charsets.UTF_8))
            if (o.getString("codec") != "h264") throw Protocol.ProtocolException("unsupported codec ${o.getString("codec")}")
            val w = o.getInt("width")
            val h = o.getInt("height")
            val fps = o.getInt("fps")
            if (w !in 16..8192 || h !in 16..8192) throw Protocol.ProtocolException("bad resolution ${w}x$h")
            if (fps !in 1..240) throw Protocol.ProtocolException("bad fps $fps")
            return Triple(w, h, fps)
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
        private const val READ_TIMEOUT_MS = 5000
    }
}
