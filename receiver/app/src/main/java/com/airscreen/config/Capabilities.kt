package com.airscreen.config

import android.content.Context
import android.media.MediaCodecList
import android.media.MediaFormat
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.view.WindowManager
import org.json.JSONArray
import org.json.JSONObject

/**
 * What this TV can actually do, reported to the sender so it can choose the best stream.
 * Format matches sender/airscreen_sender/negotiate.py.
 */
object Capabilities {
    private val CANDIDATE_SIZES = listOf(3840 to 2160, 2560 to 1440, 1920 to 1080, 1280 to 720)

    fun toJson(context: Context): JSONObject = JSONObject().apply {
        put("video", JSONObject().put("modes", decoderModes()))
        put("display", displayInfo(context))
        put("net", networkInfo(context))
        put("audio", JSONObject().put("max_channels", 2).put("rates", JSONArray(listOf(48000))))
    }

    /** Largest-first list of {w,h,fps} the hardware H.264 decoder reports it can sustain. */
    private fun decoderModes(): JSONArray {
        val modes = JSONArray()
        try {
            val infos = MediaCodecList(MediaCodecList.REGULAR_CODECS).codecInfos
                .filter { !it.isEncoder && it.supportedTypes.any { t -> t.equals(MediaFormat.MIMETYPE_VIDEO_AVC, true) } }
            // Prefer hardware decoders; software ones cannot sustain high resolutions.
            val info = infos.firstOrNull { !it.name.startsWith("OMX.google.") && !it.name.startsWith("c2.android.") }
                ?: infos.firstOrNull()
            val caps = info?.getCapabilitiesForType(MediaFormat.MIMETYPE_VIDEO_AVC)?.videoCapabilities
            if (caps != null) {
                for ((w, h) in CANDIDATE_SIZES) {
                    if (!caps.isSizeSupported(w, h)) continue
                    val fps = try {
                        caps.getSupportedFrameRatesFor(w, h).upper.toInt()
                    } catch (e: IllegalArgumentException) {
                        continue
                    }
                    if (fps >= 24) modes.put(JSONObject().put("w", w).put("h", h).put("fps", minOf(fps, 120)))
                }
            }
        } catch (_: Exception) {
            // fall through: an empty list makes the sender assume 1080p30
        }
        return modes
    }

    @Suppress("DEPRECATION")
    private fun displayInfo(context: Context): JSONObject {
        val o = JSONObject()
        try {
            val wm = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
            val mode = wm.defaultDisplay.mode
            o.put("w", mode.physicalWidth).put("h", mode.physicalHeight).put("refresh", Math.round(mode.refreshRate))
        } catch (_: Exception) {
        }
        return o
    }

    @Suppress("DEPRECATION")
    private fun networkInfo(context: Context): JSONObject {
        val o = JSONObject().put("type", "unknown")
        try {
            val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val nc = cm.getNetworkCapabilities(cm.activeNetwork) ?: return o
            when {
                nc.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> {
                    o.put("type", "ethernet")
                    o.put("link_mbps", maxOf(100, nc.linkDownstreamBandwidthKbps / 1000))
                }
                nc.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> {
                    o.put("type", "wifi")
                    val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
                    val speed = wifi.connectionInfo?.linkSpeed ?: -1 // negotiated PHY rate in Mbit/s
                    if (speed > 0) o.put("link_mbps", speed)
                }
            }
        } catch (_: Exception) {
        }
        return o
    }
}
