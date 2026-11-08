package com.airscreen.decoder

import android.media.MediaCodec
import android.media.MediaCodecList
import android.media.MediaFormat
import android.os.Build
import android.util.Log
import java.nio.ByteBuffer
import android.view.Surface
import java.io.IOException

/**
 * H.264 decoder rendering straight to a [Surface] via MediaCodec.
 * Latency policy: if the decoder cannot keep up, drop and wait for the next keyframe rather than queueing.
 */
class VideoDecoder(
    surface: Surface,
    width: Int,
    height: Int,
    sps: ByteArray?,
    pps: ByteArray?,
    codecName: String? = null,
    private val onFirstFrame: () -> Unit,
    private val onFailure: (String) -> Unit = {},
) {
    private val codec: MediaCodec
    private val outputThread: Thread
    @Volatile private var running = true
    private var waitingForKeyframe = true
    @Volatile private var firstFrameShown = false

    // latency instrumentation: time from handing a frame to the decoder until it is released for display
    private val queuedAt = java.util.concurrent.ConcurrentHashMap<Long, Long>()
    private var latSumNs = 0L
    private var latMaxNs = 0L
    private var latCount = 0
    private var latWindowStart = System.nanoTime()

    var framesDecoded = 0L
        private set
    var framesDropped = 0L
        private set

    init {
        // Different TVs ship very different H.264 decoders. Try the best decoder for this stream first, then the others
        // (hardware before software), each with progressively plainer settings, until one configures and starts.
        fun makeFormat(level: Int): MediaFormat {
            val f = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, width, height)
            if (level <= 0) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) f.setInteger(MediaFormat.KEY_LOW_LATENCY, 1)
                f.setInteger(MediaFormat.KEY_PRIORITY, 0)
                f.setInteger(MediaFormat.KEY_OPERATING_RATE, 120)
            }
            if (level <= 1) f.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 2 * 1024 * 1024)
            if (level <= 2) {
                if (sps != null) f.setByteBuffer("csd-0", ByteBuffer.wrap(sps))
                if (pps != null) f.setByteBuffer("csd-1", ByteBuffer.wrap(pps))
            }
            return f
        }

        val names = LinkedHashSet<String>()
        if (!codecName.isNullOrEmpty()) names += codecName
        try { MediaCodecList(MediaCodecList.REGULAR_CODECS).findDecoderForFormat(makeFormat(2))?.let { names += it } } catch (_: Exception) {}
        val infos = try {
            MediaCodecList(MediaCodecList.REGULAR_CODECS).codecInfos
                .filter { !it.isEncoder && it.supportedTypes.any { t -> t.equals(MediaFormat.MIMETYPE_VIDEO_AVC, true) } && !it.name.endsWith(".secure") }
        } catch (_: Exception) { emptyList() }
        infos.filter { isHardware(it) }.forEach { names += it.name }
        infos.filter { !isHardware(it) }.forEach { names += it.name }
        val usable = names.filter { it !in badDecoders }.ifEmpty { badDecoders.clear(); names.toList() }

        var created: MediaCodec? = null
        var lastError: Exception? = null
        loop@ for (name in usable) {
            for (level in 0..3) {
                var c: MediaCodec? = null
                try {
                    c = MediaCodec.createByCodecName(name)
                    c.configure(makeFormat(level), surface, null, 0)
                    c.start()
                    created = c
                    Log.i(TAG, "decoder in use: $name (settings level $level) ${width}x$height csd0=${sps?.size} csd1=${pps?.size}")
                    break@loop
                } catch (e: Exception) {
                    lastError = e
                    Log.w(TAG, "decoder $name level $level failed: ${e.message}")
                    try { c?.release() } catch (_: Exception) {}
                }
            }
        }
        codec = created ?: throw IOException("No H.264 decoder on this TV could start: ${lastError?.message}", lastError)
        StreamStats.decoderName = codec.name
        outputThread = Thread({ drainOutput() }, "airscreen-decoder-out").also { it.start() }
    }

    /** Feed one Annex B access unit. Safe to call from the network thread. */
    fun queue(data: ByteArray, ptsUs: Long, keyframe: Boolean) {
        if (!running) return
        if (waitingForKeyframe) {
            if (!keyframe) {
                framesDropped++
                return
            }
            waitingForKeyframe = false
        }
        try {
            val index = codec.dequeueInputBuffer(INPUT_TIMEOUT_US)
            if (index < 0) {
                dropUntilKeyframe()
                return
            }
            val buf = codec.getInputBuffer(index)
            if (buf == null || buf.capacity() < data.size) {
                codec.queueInputBuffer(index, 0, 0, ptsUs, 0) // return the buffer unused
                dropUntilKeyframe()
                return
            }
            (buf as java.nio.Buffer).clear() // Buffer cast: avoids NoSuchMethodError on Android < 13
            buf.put(data)
            queuedAt[ptsUs] = System.nanoTime()
            if (queuedAt.size > 256) queuedAt.clear()   // bounded: never leak if frames are dropped
            codec.queueInputBuffer(index, 0, data.size, ptsUs, 0)
        } catch (e: IllegalStateException) {
            fail("decoder stopped (${e.message})")
        }
    }

    /** The codec died underneath us (not a normal stop): tell the owner so it can recreate the decoder on the next keyframe. */
    private fun fail(reason: String) {
        if (!running) return
        running = false
        Log.w(TAG, "decoder failed: $reason")
        recordFailure(codec.name)
        try { onFailure(reason) } catch (_: Exception) {}
    }

    private fun dropUntilKeyframe() {
        framesDropped++
        waitingForKeyframe = true
    }

    private fun drainOutput() {
        val info = MediaCodec.BufferInfo()
        while (running) {
            try {
                val index = codec.dequeueOutputBuffer(info, OUTPUT_TIMEOUT_US)
                if (index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    Log.i(TAG, "output format: ${codec.outputFormat}")   // stride / crop / size as the decoder really uses them
                }
                if (index >= 0) {
                    val q = queuedAt.remove(info.presentationTimeUs)
                    codec.releaseOutputBuffer(index, true) // render immediately
                    if (q != null) recordLatency(System.nanoTime() - q)
                    framesDecoded++
                    if (!firstFrameShown) {
                        firstFrameShown = true
                        onFirstFrame()
                    }
                }
            } catch (e: IllegalStateException) {
                if (running) fail("decoder output failed (${e.message})")
                break
            }
        }
    }

    private fun recordLatency(ns: Long) {
        latSumNs += ns; latCount++; if (ns > latMaxNs) latMaxNs = ns
        val now = System.nanoTime()
        if (now - latWindowStart >= 2_000_000_000L && latCount > 0) {
            StreamStats.decodeMs = latSumNs / latCount / 1e6
            StreamStats.dropped = framesDropped
            Log.i("AirScreenStats", "decode latency avg=%.1f ms max=%.1f ms frames=%d dropped=%d".format(
                latSumNs / latCount / 1e6, latMaxNs / 1e6, latCount, framesDropped))
            latSumNs = 0; latMaxNs = 0; latCount = 0; latWindowStart = now
        }
    }

    fun stop() {
        running = false
        outputThread.join(1000)
        try {
            codec.stop()
        } catch (_: IllegalStateException) {
        }
        codec.release()
    }

    companion object {
        private const val TAG = "AirScreenDecoder"
        private val badDecoders = java.util.concurrent.CopyOnWriteArraySet<String>()
        private val failureTimes = java.util.concurrent.ConcurrentHashMap<String, MutableList<Long>>()

        private fun isHardware(info: android.media.MediaCodecInfo): Boolean =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) info.isHardwareAccelerated
            else !(info.name.startsWith("OMX.google.") || info.name.startsWith("c2.android."))

        /** Two failures of the same decoder within 30 s: stop picking it first, so another decoder gets a turn. */
        private fun recordFailure(name: String) {
            val now = System.currentTimeMillis()
            val list = failureTimes.getOrPut(name) { mutableListOf() }
            synchronized(list) {
                list.removeAll { now - it > 30_000 }
                list += now
                if (list.size >= 2) badDecoders += name
            }
        }

        /** Pulls the SPS (NAL 7) and PPS (NAL 8) out of an Annex B access unit, each with a 4-byte start code. */
        fun parameterSets(au: ByteArray): Pair<ByteArray?, ByteArray?> {
            var sps: ByteArray? = null
            var pps: ByteArray? = null
            var i = 0
            val starts = ArrayList<Int>()      // index of the first byte after each start code
            while (i + 3 < au.size) {
                if (au[i].toInt() == 0 && au[i + 1].toInt() == 0 && au[i + 2].toInt() == 1) { starts.add(i + 3); i += 3 } else i++
            }
            for ((k, st) in starts.withIndex()) {
                var end = if (k + 1 < starts.size) starts[k + 1] - 3 else au.size
                while (end > st && au[end - 1].toInt() == 0) end--          // trailing zero of a following 4-byte start code
                val nal = au.copyOfRange(st, end)
                val withCode = byteArrayOf(0, 0, 0, 1) + nal
                when (nal[0].toInt() and 0x1F) { 7 -> sps = withCode; 8 -> pps = withCode }
            }
            return sps to pps
        }

        private const val INPUT_TIMEOUT_US = 10_000L
        private const val OUTPUT_TIMEOUT_US = 10_000L
    }
}
