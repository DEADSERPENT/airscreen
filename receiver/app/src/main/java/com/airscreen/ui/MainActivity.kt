package com.airscreen.ui

import android.app.Activity
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Surface
import android.view.SurfaceHolder
import android.view.SurfaceView
import android.view.View
import android.view.WindowManager
import android.widget.TextView
import com.airscreen.R
import com.airscreen.decoder.VideoDecoder
import com.airscreen.networking.StreamServer
import java.io.IOException
import java.net.Inet4Address
import java.net.NetworkInterface

class MainActivity : Activity(), SurfaceHolder.Callback, StreamServer.Listener {

    private val ui = Handler(Looper.getMainLooper())
    private val decoderLock = Any()
    private var decoder: VideoDecoder? = null
    private var server: StreamServer? = null
    @Volatile private var surface: Surface? = null

    private lateinit var overlay: View
    private lateinit var headline: TextView
    private lateinit var address: TextView
    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(R.layout.activity_main)
        overlay = findViewById(R.id.overlay)
        headline = findViewById(R.id.headline)
        address = findViewById(R.id.address)
        status = findViewById(R.id.status)
        findViewById<SurfaceView>(R.id.video).holder.addCallback(this)
    }

    override fun onResume() {
        super.onResume()
        address.text = "Receiver IP: ${localAddresses()}   Port: ${StreamServer.DEFAULT_PORT}"
        server = StreamServer(StreamServer.DEFAULT_PORT, this).also { it.start() }
    }

    override fun onPause() {
        super.onPause()
        server?.stop()
        server = null
        stopDecoder()
    }

    @Deprecated("Back disconnects the sender first, then exits")
    override fun onBackPressed() {
        if (overlay.visibility != View.VISIBLE) {
            server?.disconnectSender() // session end callback restores the waiting screen
        } else {
            @Suppress("DEPRECATION")
            super.onBackPressed()
        }
    }

    // --- SurfaceHolder.Callback ---
    override fun surfaceCreated(holder: SurfaceHolder) {
        surface = holder.surface
    }

    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) = Unit

    override fun surfaceDestroyed(holder: SurfaceHolder) {
        surface = null
        stopDecoder()
        server?.disconnectSender()
    }

    // --- StreamServer.Listener (server thread) ---
    override fun onWaiting() = showWaiting("Ready to connect", "Waiting for sender")

    override fun onConnected(remote: String) = ui.post {
        headline.text = "Sender connecting"
        status.text = remote
    }.let { }

    override fun onHello(width: Int, height: Int, fps: Int) {
        val s = surface ?: throw IOException("no display surface")
        synchronized(decoderLock) {
            decoder?.stop()
            decoder = VideoDecoder(s, width, height) {
                ui.post { overlay.visibility = View.GONE }
            }
        }
    }

    override fun onVideo(data: ByteArray, ptsUs: Long, keyframe: Boolean) {
        synchronized(decoderLock) { decoder }?.queue(data, ptsUs, keyframe)
    }

    override fun onSessionEnded(reason: String) {
        stopDecoder()
        showWaiting("Ready to connect", reason)
    }

    override fun onFatalError(message: String) = showWaiting("Receiver error", message)

    // --- helpers ---
    private fun stopDecoder() {
        synchronized(decoderLock) {
            decoder?.stop()
            decoder = null
        }
    }

    private fun showWaiting(headlineText: String, statusText: String) {
        ui.post {
            overlay.visibility = View.VISIBLE
            headline.text = headlineText
            status.text = statusText
        }
    }

    private fun localAddresses(): String {
        val found = try {
            NetworkInterface.getNetworkInterfaces().toList()
                .filter { it.isUp && !it.isLoopback }
                .flatMap { it.inetAddresses.toList() }
                .filterIsInstance<Inet4Address>()
                .map { it.hostAddress }
        } catch (e: Exception) {
            emptyList()
        }
        return if (found.isEmpty()) "not connected to a network" else found.joinToString(", ")
    }
}
