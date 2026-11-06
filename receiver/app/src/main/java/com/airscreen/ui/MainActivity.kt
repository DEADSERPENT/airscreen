package com.airscreen.ui

import android.app.Activity
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.Surface
import android.view.SurfaceHolder
import android.view.SurfaceView
import android.view.View
import android.view.WindowManager
import android.widget.TextView
import android.widget.Toast
import com.airscreen.R
import com.airscreen.config.Capabilities
import com.airscreen.config.TrustStore
import com.airscreen.decoder.AudioPlayer
import com.airscreen.decoder.VideoDecoder
import com.airscreen.networking.DiscoveryAdvertiser
import com.airscreen.networking.PairingManager
import com.airscreen.networking.StreamServer
import java.io.IOException
import java.net.Inet4Address
import java.net.NetworkInterface

class MainActivity : Activity(), SurfaceHolder.Callback, StreamServer.Listener {

    private val ui = Handler(Looper.getMainLooper())
    private val mediaLock = Any()
    private var decoder: VideoDecoder? = null
    private var audio: AudioPlayer? = null
    private var server: StreamServer? = null
    private var advertiser: DiscoveryAdvertiser? = null
    private lateinit var trust: TrustStore
    private lateinit var pairing: PairingManager
    @Volatile private var surface: Surface? = null

    private lateinit var overlay: View
    private lateinit var headline: TextView
    private lateinit var address: TextView
    private lateinit var status: TextView
    private lateinit var pairingView: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(R.layout.activity_main)
        overlay = findViewById(R.id.overlay)
        headline = findViewById(R.id.headline)
        address = findViewById(R.id.address)
        status = findViewById(R.id.status)
        pairingView = findViewById(R.id.pairing)
        findViewById<SurfaceView>(R.id.video).holder.addCallback(this)
        trust = TrustStore(this)
        pairing = PairingManager { code -> ui.post { showCode(code) } }
    }

    override fun onResume() {
        super.onResume()
        address.text = "Receiver IP: ${localAddresses()}   Port: ${StreamServer.DEFAULT_PORT}"
        showCode(pairing.displayCode())
        server = StreamServer(StreamServer.DEFAULT_PORT, trust, pairing,
            { Capabilities.toJson(applicationContext) }, this).also { it.start() }
        advertiser = DiscoveryAdvertiser(this, StreamServer.DEFAULT_PORT, trust).also { it.register() }
    }

    override fun onPause() {
        super.onPause()
        advertiser?.unregister()
        advertiser = null
        server?.stop()
        server = null
        stopMedia()
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

    override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean {
        if (keyCode == KeyEvent.KEYCODE_MENU) {
            trust.revokeAll()
            server?.disconnectSender()
            pairing.rotate()
            Toast.makeText(this, "All paired PCs forgotten", Toast.LENGTH_SHORT).show()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    // --- SurfaceHolder.Callback ---
    override fun surfaceCreated(holder: SurfaceHolder) {
        surface = holder.surface
    }

    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) = Unit

    override fun surfaceDestroyed(holder: SurfaceHolder) {
        surface = null
        stopMedia()
        server?.disconnectSender()
    }

    // --- StreamServer.Listener (server thread) ---
    override fun onWaiting() = showWaiting("Ready to connect", "Waiting for sender")

    override fun onConnected(remote: String) {
        ui.post {
            headline.text = "Sender connecting"
            status.text = remote
        }
    }

    override fun onPaired() {
        ui.post { Toast.makeText(this, "New PC paired", Toast.LENGTH_SHORT).show() }
    }

    override fun onHello(hello: StreamServer.Hello) {
        val s = surface ?: throw IOException("no display surface")
        synchronized(mediaLock) {
            stopMediaLocked()
            decoder = VideoDecoder(s, hello.width, hello.height) {
                ui.post { overlay.visibility = View.GONE }
            }
            hello.audio?.let { a ->
                try {
                    audio = AudioPlayer(a.head, a.rate, a.channels)
                } catch (e: IOException) {
                    audio = null // video still works without sound
                    ui.post { Toast.makeText(this, "Audio unavailable: ${e.message}", Toast.LENGTH_LONG).show() }
                }
            }
        }
        ui.post {
            Toast.makeText(this, "Streaming ${hello.width}x${hello.height} @ ${hello.fps} fps" +
                if (hello.audio != null) " + audio" else "", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onVideo(data: ByteArray, ptsUs: Long, keyframe: Boolean) {
        synchronized(mediaLock) { decoder }?.queue(data, ptsUs, keyframe)
    }

    override fun onAudio(data: ByteArray, ptsUs: Long) {
        synchronized(mediaLock) { audio }?.queue(data, ptsUs)
    }

    override fun onSessionEnded(reason: String) {
        stopMedia()
        showWaiting("Ready to connect", reason)
    }

    override fun onFatalError(message: String) = showWaiting("Receiver error", message)

    // --- helpers ---
    private fun stopMedia() = synchronized(mediaLock) { stopMediaLocked() }

    private fun stopMediaLocked() {
        decoder?.stop()
        decoder = null
        audio?.stop()
        audio = null
    }

    private fun showCode(code: String) {
        pairingView.text = "Pairing code: $code"
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
