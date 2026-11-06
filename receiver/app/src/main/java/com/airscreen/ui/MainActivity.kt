package com.airscreen.ui

import android.animation.ValueAnimator
import android.app.Activity
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.Surface
import android.view.SurfaceHolder
import android.graphics.SurfaceTexture
import android.view.SurfaceView
import android.view.TextureView
import android.view.View
import android.view.WindowManager
import android.view.animation.PathInterpolator
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import com.airscreen.R
import com.airscreen.config.Capabilities
import com.airscreen.config.TrustStore
import com.airscreen.decoder.AudioPlayer
import com.airscreen.decoder.VideoDecoder
import com.airscreen.networking.DiscoveryAdvertiser
import com.airscreen.networking.PairingManager
import com.airscreen.networking.Protocol
import com.airscreen.networking.StreamServer
import java.io.IOException
import java.net.Inet4Address
import java.net.NetworkInterface
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/** TV receiver UI. One activity, layered screens; all state transitions run on the main thread. */
class MainActivity : Activity(), SurfaceHolder.Callback, StreamServer.Listener {

    private enum class Layer { READY, PAIR, STREAMING, STOP, SETTINGS }

    private val ui = Handler(Looper.getMainLooper())
    private val mediaLock = Any()
    private var decoder: VideoDecoder? = null
    private var audio: AudioPlayer? = null
    private var server: StreamServer? = null
    private var advertiser: DiscoveryAdvertiser? = null
    private lateinit var trust: TrustStore
    private lateinit var pairing: PairingManager
    @Volatile private var surface: Surface? = null
    @Volatile private var pairDecision: ((Boolean) -> Unit)? = null

    private var layer = Layer.READY
    private var pendingHello: StreamServer.Hello? = null
    private var renderMode = "texture"            // debug: --es render texture|surface
    private var decoderOverride: String? = null   // debug: adb shell am start ... --es decoder <codec name>
    private var streamInfo = ""
    private var audioMuted = false
    private val hideHud = Runnable {
        findViewById<View>(R.id.hud).animate().alpha(0f).setDuration(200).withEndAction { findViewById<View>(R.id.hud).visibility = View.GONE }.start()
    }

    private lateinit var overlay: View
    private lateinit var pairLayer: View
    private lateinit var stopLayer: View
    private lateinit var settingsLayer: View
    private lateinit var headline: TextView
    private lateinit var address: TextView
    private lateinit var status: TextView
    private lateinit var codeTiles: List<TextView>
    private lateinit var hud: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        decoderOverride = intent?.getStringExtra("decoder")
        renderMode = intent?.getStringExtra("render") ?: "texture"
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(R.layout.activity_main)
        overlay = findViewById(R.id.overlay)
        pairLayer = findViewById(R.id.pairLayer)
        stopLayer = findViewById(R.id.stopLayer)
        settingsLayer = findViewById(R.id.settingsLayer)
        headline = findViewById(R.id.headline)
        address = findViewById(R.id.address)
        status = findViewById(R.id.status)
        codeTiles = listOf(R.id.code1, R.id.code2, R.id.code3, R.id.code4).map { findViewById<TextView>(it) }
        hud = findViewById(R.id.hud)
        if (renderMode == "texture") {
            findViewById<SurfaceView>(R.id.video).visibility = View.GONE
            val tv = findViewById<TextureView>(R.id.videoTex)
            tv.visibility = View.VISIBLE
            tv.surfaceTextureListener = object : TextureView.SurfaceTextureListener {
                override fun onSurfaceTextureAvailable(st: SurfaceTexture, w: Int, h: Int) { surface = Surface(st) }
                override fun onSurfaceTextureSizeChanged(st: SurfaceTexture, w: Int, h: Int) = Unit
                override fun onSurfaceTextureDestroyed(st: SurfaceTexture): Boolean {
                    surface = null; stopMedia(); server?.disconnectSender(); return true
                }
                override fun onSurfaceTextureUpdated(st: SurfaceTexture) = Unit
            }
        } else {
            findViewById<SurfaceView>(R.id.video).holder.addCallback(this)
        }
        trust = TrustStore(this)
        pairing = PairingManager { code -> ui.post { showCode(code) } }

        // pairing approval
        findViewById<Button>(R.id.allowBtn).setOnClickListener { pairDecision?.invoke(true) }
        findViewById<Button>(R.id.denyBtn).setOnClickListener { pairDecision?.invoke(false) }
        // stop confirmation
        findViewById<Button>(R.id.stopBtn).setOnClickListener { server?.disconnectSender(); show(Layer.READY) }
        findViewById<Button>(R.id.keepBtn).setOnClickListener { show(Layer.STREAMING) }
        // settings
        findViewById<Button>(R.id.settingsBtn).setOnClickListener { show(Layer.SETTINGS) }
        findViewById<Button>(R.id.settingsClose).setOnClickListener { show(Layer.READY) }
        findViewById<View>(R.id.rowPaired).setOnClickListener {
            trust.revokeAll(); pairing.rotate()
            Toast.makeText(this, "All paired PCs forgotten", Toast.LENGTH_SHORT).show()
            refreshSettings()
        }
        listOf(R.id.settingsBtn, R.id.denyBtn, R.id.allowBtn, R.id.stopBtn, R.id.keepBtn, R.id.settingsClose)
            .forEach { attachFocusScale(findViewById(it)) }
        listOf(R.id.rowPaired, R.id.rowAbout, R.id.rowDiag).forEach { attachFocusScale(findViewById(it), 1.02f) }
        refreshSettings()
        show(Layer.READY)
    }

    override fun onResume() {
        super.onResume()
        address.text = "${localAddresses()}  ·  Port ${StreamServer.DEFAULT_PORT}  ·  ${trust.name}"
        showCode(pairing.displayCode())
        server = StreamServer(StreamServer.DEFAULT_PORT, trust, pairing,
            { Capabilities.toJson(applicationContext) }, this).also { it.start() }
        advertiser = DiscoveryAdvertiser(this, StreamServer.DEFAULT_PORT, trust).also { it.register() }
    }

    override fun onPause() {
        super.onPause()
        advertiser?.unregister(); advertiser = null
        server?.stop(); server = null
        pairDecision?.invoke(false)
        stopMedia()
    }

    // ---- layer / focus management (focus enters deliberately and returns after dialogs) ----
    private val ease = PathInterpolator(0.2f, 0f, 0f, 1f)           // design system: standard easing
    private fun dp(v: Float) = v * resources.displayMetrics.density
    private fun motionOn() = ValueAnimator.areAnimatorsEnabled()

    private fun show(l: Layer) {
        val previous = layer
        layer = l
        val views = mapOf(Layer.READY to overlay, Layer.PAIR to pairLayer, Layer.STOP to stopLayer, Layer.SETTINGS to settingsLayer)
        for ((k, v) in views) if (k == l) enter(v, k) else exit(v)
        if (l != Layer.STREAMING) { ui.removeCallbacks(hideHud); hud.animate().cancel(); hud.visibility = View.GONE }
        when (l) {
            Layer.READY -> findViewById<View>(R.id.settingsBtn).requestFocus()
            Layer.PAIR -> findViewById<View>(R.id.denyBtn).requestFocus()       // safest default; Allow needs a deliberate move
            Layer.STOP -> findViewById<View>(R.id.keepBtn).requestFocus()
            Layer.SETTINGS -> findViewById<View>(R.id.rowPaired).requestFocus()
            Layer.STREAMING -> Unit
        }
    }

    private fun enter(v: View, which: Layer) {
        v.animate().cancel()
        if (v.visibility == View.VISIBLE && v.alpha == 1f) return
        v.visibility = View.VISIBLE
        if (!motionOn() || layer == Layer.STREAMING) { v.alpha = 1f; return }
        v.alpha = 0f
        v.animate().alpha(1f).setDuration(if (which == Layer.READY || which == Layer.SETTINGS) 280L else 200L).setInterpolator(ease).start()
        when (which) {
            Layer.PAIR -> popIn(findViewById(R.id.pairPanel))
            Layer.STOP -> popIn(findViewById(R.id.stopPanel))
            Layer.READY -> reveal(listOf(R.id.logo, R.id.headline, R.id.status, R.id.stepsRow, R.id.codeSection, R.id.address, R.id.settingsBtn))
            Layer.SETTINGS -> reveal(listOf(R.id.settingsTitle, R.id.rowPaired, R.id.rowAbout, R.id.rowDiag, R.id.settingsClose))
            else -> Unit
        }
    }

    private fun exit(v: View) {
        if (v.visibility != View.VISIBLE) return
        v.animate().cancel()
        if (!motionOn()) { v.visibility = View.GONE; return }
        v.animate().alpha(0f).setDuration(160).setInterpolator(ease).withEndAction {
            if (!(v === overlay && layer == Layer.READY) && !(v === settingsLayer && layer == Layer.SETTINGS) &&
                !(v === pairLayer && layer == Layer.PAIR) && !(v === stopLayer && layer == Layer.STOP)) v.visibility = View.GONE
        }.start()
    }

    /** Dialog panel: scale .96 -> 1 with the fade (design system 5.6). */
    private fun popIn(panel: View) {
        panel.animate().cancel()
        panel.scaleX = 0.96f; panel.scaleY = 0.96f
        panel.animate().scaleX(1f).scaleY(1f).setDuration(220).setInterpolator(ease).start()
    }

    /** Staggered rise: each element fades up 14 dp, 55 ms after the previous one. */
    private fun reveal(ids: List<Int>) {
        ids.forEachIndexed { i, id ->
            val v = findViewById<View>(id)
            v.animate().cancel()
            v.alpha = 0f; v.translationY = dp(14f)
            v.animate().alpha(1f).translationY(0f).setStartDelay(i * 55L).setDuration(320).setInterpolator(ease).start()
        }
    }

    @Deprecated("Back is deliberate: confirm before ending a stream")
    override fun onBackPressed() {
        when (layer) {
            Layer.PAIR -> pairDecision?.invoke(false)
            Layer.STOP -> show(Layer.STREAMING)
            Layer.STREAMING -> show(Layer.STOP)
            Layer.SETTINGS -> show(Layer.READY)
            Layer.READY -> @Suppress("DEPRECATION") super.onBackPressed()
        }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean {
        if (layer == Layer.STREAMING && keyCode != KeyEvent.KEYCODE_BACK) {
            if (keyCode == KeyEvent.KEYCODE_DPAD_CENTER || keyCode == KeyEvent.KEYCODE_ENTER) {
                audioMuted = !audioMuted
                synchronized(mediaLock) { audio }?.muted = audioMuted
            }
            showHud()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    private fun showHud() {
        hud.text = "$streamInfo  ·  Audio ${if (audioMuted) "muted" else "on"}  ·  OK toggles audio"
        hud.animate().cancel()
        if (hud.visibility != View.VISIBLE) { hud.alpha = 0f; hud.visibility = View.VISIBLE }
        hud.animate().alpha(1f).setDuration(160).setInterpolator(ease).start()
        ui.removeCallbacks(hideHud)
        ui.postDelayed(hideHud, 3000)
    }

    /** TV focus (5.5): scale 1.05 + white outline (from the drawable) in ~180 ms; a brief press dip on OK. */
    private fun attachFocusScale(v: View, focusScale: Float = 1.05f) {
        v.setOnFocusChangeListener { view, hasFocus ->
            val sc = if (hasFocus) focusScale else 1f
            val lift = if (hasFocus) dp(14f) else 0f          // glow level: elevation 14 dp in the brand colour
            if (android.os.Build.VERSION.SDK_INT >= 28) { view.outlineSpotShadowColor = 0xFF8057FF.toInt(); view.outlineAmbientShadowColor = 0xFF8057FF.toInt() }
            if (motionOn()) view.animate().scaleX(sc).scaleY(sc).translationZ(lift).setDuration(if (hasFocus) 180 else 140).setInterpolator(ease).start()
            else { view.scaleX = sc; view.scaleY = sc; view.translationZ = lift }
        }
        v.setOnKeyListener { view, keyCode, event ->
            if (keyCode == KeyEvent.KEYCODE_DPAD_CENTER || keyCode == KeyEvent.KEYCODE_ENTER) {
                val sc = if (event.action == KeyEvent.ACTION_DOWN) 0.98f else focusScale
                if (motionOn()) view.animate().scaleX(sc).scaleY(sc).setDuration(80).start()
            }
            false   // let the click proceed
        }
    }

    private fun refreshSettings() {
        val n = trust.trustedCount()
        findViewById<TextView>(R.id.rowPairedSub).text = if (n == 0) "No PCs paired yet" else "$n paired · select to forget all"
        val version = try { packageManager.getPackageInfo(packageName, 0).versionName } catch (e: Exception) { "?" }
        findViewById<TextView>(R.id.rowAboutSub).text = "AirScreen $version · protocol v${Protocol.VERSION} · Android ${Build.VERSION.RELEASE}"
        findViewById<TextView>(R.id.rowDiagSub).text = diagnosticsText()
    }

    private fun diagnosticsText(): String = try {
        val c = Capabilities.toJson(applicationContext)
        val m = c.getJSONObject("video").getJSONArray("modes")
        val best = if (m.length() > 0) m.getJSONObject(0) else null
        val net = c.getJSONObject("net")
        val dec = if (best != null) "H.264 up to ${best.getInt("w")}×${best.getInt("h")} @ ${best.getInt("fps")} fps (reported)" else "H.264 limits not reported"
        val link = if (net.has("link_mbps")) "${net.getString("type")} ${net.getInt("link_mbps")} Mbit/s" else net.getString("type")
        "$dec · $link"
    } catch (e: Exception) { "Not available" }

    // ---- SurfaceHolder.Callback ----
    override fun surfaceCreated(holder: SurfaceHolder) { surface = holder.surface }
    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) = Unit
    override fun surfaceDestroyed(holder: SurfaceHolder) {
        surface = null
        stopMedia()
        server?.disconnectSender()
    }

    // ---- StreamServer.Listener (server thread) ----
    override fun onWaiting() = showWaiting("Ready to connect", "Choose “${trust.name}” on your PC")

    override fun onConnected(remote: String) {
        ui.post { headline.text = "Connecting"; status.text = "A PC is connecting…" }
    }

    override fun onPairRequest(senderName: String): Boolean {
        val latch = CountDownLatch(1)
        val allowed = AtomicBoolean(false)
        pairDecision = { ok -> allowed.set(ok); latch.countDown() }
        ui.post {
            findViewById<TextView>(R.id.pairTitle).text = "Allow $senderName to cast?"
            show(Layer.PAIR)
        }
        val answered = latch.await(30, TimeUnit.SECONDS)   // timeout = deny
        pairDecision = null
        ui.post { if (layer == Layer.PAIR) show(Layer.READY) }
        return answered && allowed.get()
    }

    override fun onPaired() {
        ui.post { Toast.makeText(this, "PC paired", Toast.LENGTH_SHORT).show(); refreshSettings() }
    }

    override fun onHello(hello: StreamServer.Hello) {
        if (surface == null) throw IOException("no display surface")
        synchronized(mediaLock) {
            stopMediaLocked()
            pendingHello = hello          // the decoder is created on the first keyframe, once SPS/PPS are known
            audioMuted = false
            hello.audio?.let { a ->
                try { audio = AudioPlayer(a.head, a.rate, a.channels) } catch (e: IOException) {
                    audio = null
                    ui.post { Toast.makeText(this, "Audio unavailable", Toast.LENGTH_LONG).show() }
                }
            }
        }
        streamInfo = "${hello.width}×${hello.height} · ${hello.fps} fps"
    }

    override fun onVideo(data: ByteArray, ptsUs: Long, keyframe: Boolean) {
        synchronized(mediaLock) {
            if (decoder == null && keyframe) {
                val h = pendingHello ?: return
                val s = surface ?: throw IOException("no display surface")
                val (sps, pps) = VideoDecoder.parameterSets(data)
                decoder = VideoDecoder(s, h.width, h.height, sps, pps, decoderOverride) {
                    // the first decoded frame is on screen: only now is it truthful to say "streaming"
                    ui.post { show(Layer.STREAMING); showHud() }
                }
            }
            decoder
        }?.queue(data, ptsUs, keyframe)
    }

    override fun onAudio(data: ByteArray, ptsUs: Long) {
        synchronized(mediaLock) { audio }?.queue(data, ptsUs)
    }

    override fun onSessionEnded(reason: String) {
        stopMedia()
        showWaiting("Ready to connect", friendly(reason))
    }

    override fun onFatalError(message: String) = showWaiting("Receiver problem", message)

    // ---- helpers ----
    private fun friendly(reason: String) = when {
        reason.startsWith("Sender disconnected") -> "Your PC stopped streaming."
        reason.contains("did not approve") -> "The connection was denied."
        reason.contains("not paired") || reason.contains("authentication failed") -> "Pairing didn’t work. Check the code and try again."
        reason.contains("timed out") || reason.contains("stopped responding") -> "Connection interrupted. Waiting for your PC."
        else -> reason
    }

    private fun stopMedia() = synchronized(mediaLock) { stopMediaLocked() }

    private fun stopMediaLocked() {
        decoder?.stop(); decoder = null
        audio?.stop(); audio = null
    }

    private fun showCode(code: String) {
        val groups = code.split("-")
        codeTiles.forEachIndexed { i, tile ->
            val g = groups.getOrNull(i) ?: "····"
            if (tile.text.toString() != g) {
                tile.text = g
                if (motionOn() && layer != Layer.STREAMING) { tile.alpha = 0.25f; tile.animate().alpha(1f).setDuration(200).setInterpolator(ease).start() }
            }
        }
    }

    private fun showWaiting(headlineText: String, statusText: String) {
        ui.post {
            headline.text = headlineText
            status.text = statusText
            if (layer != Layer.SETTINGS && layer != Layer.PAIR) show(Layer.READY)
        }
    }

    private fun localAddresses(): String {
        val found = try {
            NetworkInterface.getNetworkInterfaces().toList()
                .filter { it.isUp && !it.isLoopback }
                .flatMap { it.inetAddresses.toList() }
                .filterIsInstance<Inet4Address>()
                .map { it.hostAddress }
        } catch (e: Exception) { emptyList() }
        return if (found.isEmpty()) "no network" else found.joinToString(", ")
    }
}
