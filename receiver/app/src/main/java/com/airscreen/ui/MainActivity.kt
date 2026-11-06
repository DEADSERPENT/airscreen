package com.airscreen.ui

import android.animation.ObjectAnimator
import android.animation.ValueAnimator
import android.app.Activity
import android.graphics.SurfaceTexture
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.SpannableStringBuilder
import android.text.style.ForegroundColorSpan
import android.text.style.RelativeSizeSpan
import android.view.KeyEvent
import android.view.Surface
import android.view.SurfaceHolder
import android.view.SurfaceView
import android.view.TextureView
import android.view.View
import android.view.WindowManager
import android.view.animation.PathInterpolator
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import com.airscreen.R
import com.airscreen.config.Capabilities
import com.airscreen.config.TrustStore
import com.airscreen.decoder.AudioPlayer
import com.airscreen.decoder.StreamStats
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

/**
 * AirScreen TV: spatial, monochrome, cinematic. One activity, layered screens; every state change runs on the main thread.
 * Screens: Ready, Connecting, Pairing approval, Streaming (video only), Stop confirmation, Settings/Diagnostics.
 */
class MainActivity : Activity(), SurfaceHolder.Callback, StreamServer.Listener {

    private enum class Layer { READY, CONNECTING, PAIR, STREAMING, STOP, SETTINGS }

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
    private var pairBack: View? = null
    private var pendingHello: StreamServer.Hello? = null
    private var renderMode = "texture"                       // debug: --es render texture|surface
    private var decoderOverride: String? = null              // debug: --es decoder <codec name>
    private var streamInfo = ""
    private var audioMuted = false
    private var progress: ObjectAnimator? = null
    private val wanted = HashSet<View>()
    private val hideHud = Runnable {
        hud.animate().alpha(0f).setDuration(200).withEndAction { hud.visibility = View.GONE }.start()
    }

    private lateinit var overlay: View
    private lateinit var connectLayer: View
    private lateinit var pairLayer: View
    private lateinit var stopLayer: View
    private lateinit var settingsLayer: View
    private lateinit var headline: TextView
    private lateinit var address: TextView
    private lateinit var status: TextView
    private lateinit var codeTiles: List<TextView>
    private lateinit var connectSub: TextView
    private lateinit var connectBar: View
    private lateinit var hud: View
    private lateinit var hudText: TextView
    private lateinit var hudIcon: ImageView
    private lateinit var detailTitle: TextView
    private lateinit var detailBody: TextView
    private lateinit var detailBody2: TextView
    private lateinit var detailHint: TextView

    private val ease = PathInterpolator(0.2f, 0f, 0f, 1f)    // design system: standard easing
    private fun dp(v: Float) = v * resources.displayMetrics.density
    private fun motionOn() = ValueAnimator.areAnimatorsEnabled()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        decoderOverride = intent?.getStringExtra("decoder")
        renderMode = intent?.getStringExtra("render") ?: "texture"
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(R.layout.activity_main)
        overlay = findViewById(R.id.overlay)
        connectLayer = findViewById(R.id.connectLayer)
        pairLayer = findViewById(R.id.pairLayer)
        stopLayer = findViewById(R.id.stopLayer)
        settingsLayer = findViewById(R.id.settingsLayer)
        headline = findViewById(R.id.headline)
        address = findViewById(R.id.address)
        status = findViewById(R.id.status)
        connectSub = findViewById(R.id.connectSub)
        connectBar = findViewById(R.id.connectBar)
        hud = findViewById(R.id.hud)
        hudText = findViewById(R.id.hudText)
        hudIcon = findViewById(R.id.hudIcon)
        detailTitle = findViewById(R.id.detailTitle)
        detailBody = findViewById(R.id.detailBody)
        detailBody2 = findViewById(R.id.detailBody2)
        detailHint = findViewById(R.id.detailHint)
        codeTiles = listOf(R.id.code1, R.id.code2, R.id.code3, R.id.code4).map { findViewById<TextView>(it) }

        if (renderMode == "texture") {
            // The Realtek hardware decoder renders correctly through a GPU texture, not the direct video plane.
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

        findViewById<View>(R.id.allowBtn).setOnClickListener { pairDecision?.invoke(true) }
        findViewById<View>(R.id.denyBtn).setOnClickListener { pairDecision?.invoke(false) }
        findViewById<View>(R.id.stopBtn).setOnClickListener { server?.disconnectSender(); show(Layer.READY) }
        findViewById<View>(R.id.keepBtn).setOnClickListener { show(Layer.STREAMING) }
        findViewById<View>(R.id.settingsBtn).setOnClickListener { show(Layer.SETTINGS) }
        findViewById<View>(R.id.settingsClose).setOnClickListener { show(Layer.READY) }
        findViewById<View>(R.id.cardPaired).setOnClickListener {
            trust.revokeAll(); pairing.rotate()
            Toast.makeText(this, "All paired PCs forgotten", Toast.LENGTH_SHORT).show()
            refreshSettings(); showDetail(0)
        }

        listOf(R.id.denyBtn, R.id.allowBtn, R.id.stopBtn, R.id.keepBtn, R.id.settingsClose)
            .forEach { attachFocus(findViewById(it), 1.05f) }
        attachFocus(findViewById(R.id.settingsBtn), 1.06f)
        val shelf = listOf(R.id.cardPaired, R.id.cardDiag, R.id.cardAbout).map { findViewById<View>(it) }
        fun dimOthers(selected: View) = shelf.forEach { c ->
            val a = if (c === selected) 1f else 0.55f
            if (motionOn()) c.animate().alpha(a).setDuration(180).setInterpolator(ease).start() else c.alpha = a
        }
        attachFocus(shelf[0], 1.07f) { if (it) { showDetail(0); dimOthers(shelf[0]) } }
        attachFocus(shelf[1], 1.07f) { if (it) { showDetail(1); dimOthers(shelf[1]) } }
        attachFocus(shelf[2], 1.07f) { if (it) { showDetail(2); dimOthers(shelf[2]) } }
        refreshSettings()
        show(Layer.READY)
    }

    override fun onResume() {
        super.onResume()
        address.text = "${trust.name}\n${localAddresses()}  ·  Port ${StreamServer.DEFAULT_PORT}"
        showCode(pairing.displayCode())
        status.text = "Choose “${trust.name}” on your PC"
        server = StreamServer(StreamServer.DEFAULT_PORT, trust, pairing,
            { Capabilities.toJson(applicationContext) }, this).also { it.start() }
        advertiser = DiscoveryAdvertiser(this, StreamServer.DEFAULT_PORT, trust).also { it.register() }
    }

    override fun onPause() {
        super.onPause()
        advertiser?.unregister(); advertiser = null
        server?.stop(); server = null
        pairDecision?.invoke(false)
        stopProgress()
        stopMedia()
    }

    // =============================== layers (spatial depth) ===============================
    private fun show(l: Layer) {
        val prev = layer
        layer = l
        wanted.clear()
        var recedeBack: View? = null
        when (l) {
            Layer.READY -> wanted += overlay
            Layer.CONNECTING -> wanted += connectLayer
            Layer.PAIR -> {
                // the screen behind recedes: smaller and dim, so the dialog reads as floating in front
                pairBack = if (prev == Layer.CONNECTING) connectLayer else if (prev == Layer.PAIR) pairBack else overlay
                recedeBack = pairBack
                wanted += pairBack!!; wanted += pairLayer
            }
            Layer.STOP -> wanted += stopLayer
            Layer.SETTINGS -> wanted += settingsLayer
            Layer.STREAMING -> Unit
        }
        for (v in listOf(overlay, connectLayer, pairLayer, stopLayer, settingsLayer)) {
            val shown = v in wanted
            val receded = v === recedeBack
            present(v, shown, if (receded) 0.28f else 1f, if (receded) 0.95f else 1f)
        }
        if (l == Layer.CONNECTING) startProgress() else stopProgress()
        if (l != Layer.STREAMING) { ui.removeCallbacks(hideHud); hud.animate().cancel(); hud.visibility = View.GONE }
        if (prev != l) when (l) {
            Layer.READY -> reveal(listOf(R.id.brandRow, R.id.hero, R.id.headline, R.id.status, R.id.codeSection, R.id.stepsRow))
            Layer.SETTINGS -> reveal(listOf(R.id.settingsTitle, R.id.settingsClose, R.id.cardPaired, R.id.cardDiag, R.id.cardAbout, R.id.detailPanel))
            Layer.PAIR -> popIn(findViewById(R.id.pairPanel))
            Layer.STOP -> popIn(findViewById(R.id.stopPanel))
            else -> Unit
        }
        when (l) {
            Layer.READY -> findViewById<View>(R.id.settingsBtn).requestFocus()
            Layer.PAIR -> findViewById<View>(R.id.denyBtn).requestFocus()        // safest default: Allow needs a deliberate move
            Layer.STOP -> findViewById<View>(R.id.keepBtn).requestFocus()
            Layer.SETTINGS -> findViewById<View>(R.id.cardPaired).requestFocus()
            else -> Unit
        }
    }

    private fun present(v: View, visible: Boolean, alpha: Float, scale: Float) {
        v.animate().cancel()
        if (visible) {
            if (v.visibility != View.VISIBLE) { v.alpha = 0f; v.scaleX = 0.98f; v.scaleY = 0.98f; v.visibility = View.VISIBLE }
            if (motionOn() && layer != Layer.STREAMING) v.animate().alpha(alpha).scaleX(scale).scaleY(scale).setDuration(300).setInterpolator(ease).start()
            else { v.alpha = alpha; v.scaleX = scale; v.scaleY = scale }
        } else if (v.visibility == View.VISIBLE) {
            if (motionOn()) v.animate().alpha(0f).setDuration(160).setInterpolator(ease).withEndAction { if (v !in wanted) v.visibility = View.GONE }.start()
            else v.visibility = View.GONE
        }
    }

    /** Dialog panel floats in: scale .95 -> 1 together with the fade. */
    private fun popIn(panel: View) {
        panel.animate().cancel()
        panel.scaleX = 0.95f; panel.scaleY = 0.95f
        if (motionOn()) panel.animate().scaleX(1f).scaleY(1f).setDuration(260).setInterpolator(ease).start()
        else { panel.scaleX = 1f; panel.scaleY = 1f }
    }

    /** Elements rise into place one after another (55 ms apart). */
    private fun reveal(ids: List<Int>) {
        if (!motionOn()) return
        ids.forEachIndexed { i, id ->
            val v = findViewById<View>(id)
            v.animate().cancel()
            v.alpha = 0f; v.translationY = dp(14f)
            v.animate().alpha(1f).translationY(0f).setStartDelay(i * 55L).setDuration(340).setInterpolator(ease).start()
        }
    }

    private fun startProgress() {
        stopProgress()
        connectBar.translationX = 0f
        if (!motionOn()) return
        val track = findViewById<View>(R.id.connectTrack)
        track.post {
            val travel = (track.width - connectBar.width).toFloat().coerceAtLeast(0f)
            progress = ObjectAnimator.ofFloat(connectBar, "translationX", 0f, travel).apply {
                duration = 1500; repeatMode = ValueAnimator.REVERSE; repeatCount = ValueAnimator.INFINITE; interpolator = ease; start()
            }
        }
    }

    private fun stopProgress() { progress?.cancel(); progress = null }

    // =============================== input ===============================
    @Deprecated("Back is deliberate: confirm before ending a stream")
    override fun onBackPressed() {
        when (layer) {
            Layer.PAIR -> pairDecision?.invoke(false)
            Layer.STOP -> show(Layer.STREAMING)
            Layer.STREAMING -> show(Layer.STOP)
            Layer.SETTINGS -> show(Layer.READY)
            Layer.CONNECTING -> { server?.disconnectSender(); show(Layer.READY) }
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
        hudText.text = "$streamInfo  ·  Audio ${if (audioMuted) "muted" else "on"}  ·  OK toggles audio"
        hudIcon.setImageResource(if (audioMuted) R.drawable.ic3d_audio_mute else R.drawable.ic3d_audio_volume)
        hud.animate().cancel()
        if (hud.visibility != View.VISIBLE) { hud.alpha = 0f; hud.visibility = View.VISIBLE }
        hud.animate().alpha(1f).setDuration(160).setInterpolator(ease).start()
        ui.removeCallbacks(hideHud)
        ui.postDelayed(hideHud, 3000)
    }

    /**
     * Spatial focus: the element lifts toward you (scale + glow elevation), brightens and gets a white edge (drawable).
     * Pressing OK dips it briefly. Respects the system "remove animations" setting.
     */
    private fun attachFocus(v: View, focusScale: Float, onFocus: ((Boolean) -> Unit)? = null) {
        v.setOnFocusChangeListener { view, hasFocus ->
            val sc = if (hasFocus) focusScale else 1f
            val lift = if (hasFocus) dp(12f) else 0f
            if (Build.VERSION.SDK_INT >= 28) { view.outlineSpotShadowColor = 0xFFFFFFFF.toInt(); view.outlineAmbientShadowColor = 0xFFFFFFFF.toInt() }
            if (motionOn()) view.animate().scaleX(sc).scaleY(sc).translationZ(lift).setDuration(if (hasFocus) 200 else 150).setInterpolator(ease).start()
            else { view.scaleX = sc; view.scaleY = sc; view.translationZ = lift }
            onFocus?.invoke(hasFocus)
        }
        v.setOnKeyListener { view, keyCode, event ->
            if (keyCode == KeyEvent.KEYCODE_DPAD_CENTER || keyCode == KeyEvent.KEYCODE_ENTER) {
                val sc = if (event.action == KeyEvent.ACTION_DOWN) focusScale - 0.04f else focusScale
                if (motionOn()) view.animate().scaleX(sc).scaleY(sc).setDuration(80).start()
            }
            false
        }
    }

    // =============================== settings / diagnostics ===============================
    private fun refreshSettings() {
        val n = trust.trustedCount()
        findViewById<TextView>(R.id.cardPairedSub).text = if (n == 0) "None yet" else "$n paired"
        findViewById<TextView>(R.id.cardAboutSub).text = "AirScreen ${versionName()}"
    }

    private fun versionName(): String = try { packageManager.getPackageInfo(packageName, 0).versionName ?: "?" } catch (e: Exception) { "?" }

    /** One fact per line: dim label, then the value. */
    private fun kv(rows: List<Pair<String, String>>): CharSequence {
        val sb = SpannableStringBuilder()
        rows.forEachIndexed { i, (k, v) ->
            val s = sb.length
            sb.append(k)
            sb.setSpan(ForegroundColorSpan(0xFF93939A.toInt()), s, sb.length, 0)
            sb.append("   ").append(v)
            if (i < rows.size - 1) sb.append("\n")
        }
        return sb
    }

    private fun setDetail(title: String, rows: List<Pair<String, String>>, hint: String) {
        detailTitle.text = title
        val half = (rows.size + 1) / 2
        detailBody.text = kv(rows.take(half))
        detailBody2.text = if (rows.size > half) kv(rows.drop(half)) else ""
        detailHint.text = hint
    }

    private fun showDetail(which: Int) {
        when (which) {
            0 -> {
                val n = trust.trustedCount()
                setDetail("Paired PCs", listOf("Paired PCs" to (if (n == 0) "None yet" else "$n"), "Encryption" to "AES-256-GCM, a new key for every connection"),
                    if (n == 0) "A PC appears here after you pair it." else "Press OK to forget all paired PCs.")
            }
            1 -> setDetail("Diagnostics", diagRows(), "“Reported” comes from this TV. “Measured” comes from your last stream.")
            else -> setDetail("About", listOf("Version" to "AirScreen ${versionName()}", "Protocol" to "v${Protocol.VERSION}",
                "Device" to "${Build.MANUFACTURER} ${Build.MODEL}", "Android" to "${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})"),
                "No account, no cloud, no telemetry.")
        }
    }

    private fun diagRows(): List<Pair<String, String>> = try {
        val c = Capabilities.toJson(applicationContext)
        val modes = c.getJSONObject("video").getJSONArray("modes")
        val best = if (modes.length() > 0) modes.getJSONObject(0) else null
        val disp = c.getJSONObject("display")
        val net = c.getJSONObject("net")
        val dec = StreamStats.decoderName.ifEmpty { "Not used yet" }
        val kind = if (dec.startsWith("c2.android") || dec.startsWith("OMX.google")) "software" else "hardware"
        listOf(
            "Decoder" to (if (StreamStats.decoderName.isEmpty()) dec else "$dec ($kind)"),
            "H.264 limit (reported)" to (if (best != null) "${best.getInt("w")}×${best.getInt("h")} at ${best.getInt("fps")} fps" else "Not reported"),
            "Display (reported)" to (if (disp.has("w")) "${disp.getInt("w")}×${disp.getInt("h")} at ${disp.optInt("refresh")} Hz" else "Not reported"),
            "Network (reported)" to (if (net.has("link_mbps")) "${net.getString("type")}, ${net.getInt("link_mbps")} Mbit/s link" else net.getString("type")),
            "Last stream" to (if (StreamStats.width > 0) "${StreamStats.width}×${StreamStats.height} at ${StreamStats.fps} fps" else "No stream yet"),
            "Decode delay (measured)" to (if (StreamStats.decodeMs >= 0) "${StreamStats.decodeMs.toInt()} ms" else "Not measured yet"),
            "Dropped frames (measured)" to (if (StreamStats.width > 0) "${StreamStats.dropped}" else "—"),
        )
    } catch (e: Exception) { listOf("Diagnostics" to "Not available") }

    // =============================== SurfaceHolder.Callback (debug surface mode) ===============================
    override fun surfaceCreated(holder: SurfaceHolder) { surface = holder.surface }
    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) = Unit
    override fun surfaceDestroyed(holder: SurfaceHolder) {
        surface = null; stopMedia(); server?.disconnectSender()
    }

    // =============================== StreamServer.Listener (server thread) ===============================
    override fun onWaiting() = showWaiting("Ready to connect", "Choose “${trust.name}” on your PC")

    override fun onConnected(remote: String) {
        ui.post {
            connectSub.text = "Securing the connection"
            if (layer != Layer.SETTINGS) show(Layer.CONNECTING)
        }
    }

    override fun onPairRequest(senderName: String): Boolean {
        val latch = CountDownLatch(1)
        val allowed = AtomicBoolean(false)
        pairDecision = { ok -> allowed.set(ok); latch.countDown() }
        ui.post {
            findViewById<TextView>(R.id.pairTitle).text = senderName
            show(Layer.PAIR)
        }
        val answered = latch.await(30, TimeUnit.SECONDS)           // timeout = deny
        pairDecision = null
        val ok = answered && allowed.get()
        ui.post {
            if (layer == Layer.PAIR) {
                if (ok) { connectSub.text = "Starting your screen"; show(Layer.CONNECTING) } else show(Layer.READY)
            }
        }
        return ok
    }

    override fun onPaired() {
        ui.post { Toast.makeText(this, "PC paired", Toast.LENGTH_SHORT).show(); refreshSettings() }
    }

    override fun onHello(hello: StreamServer.Hello) {
        if (surface == null) throw IOException("no display surface")
        synchronized(mediaLock) {
            stopMediaLocked()
            pendingHello = hello           // the decoder is created on the first keyframe, once SPS/PPS are known
            audioMuted = false
            hello.audio?.let { a ->
                try { audio = AudioPlayer(a.head, a.rate, a.channels) } catch (e: IOException) {
                    audio = null
                    ui.post { Toast.makeText(this, "Audio unavailable", Toast.LENGTH_LONG).show() }
                }
            }
        }
        streamInfo = "${hello.width}×${hello.height} · ${hello.fps} fps"
        StreamStats.width = hello.width; StreamStats.height = hello.height; StreamStats.fps = hello.fps
        StreamStats.decodeMs = -1.0; StreamStats.dropped = 0
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

    // =============================== helpers ===============================
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
