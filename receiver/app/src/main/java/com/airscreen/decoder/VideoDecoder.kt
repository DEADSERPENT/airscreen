package com.airscreen.decoder

import android.media.MediaCodec
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
        val format = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, width, height)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) format.setInteger(MediaFormat.KEY_LOW_LATENCY, 1)
        format.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 2 * 1024 * 1024)
        // Hardware decoders (this TV's Realtek one) want the parameter sets up front, not only inline.
        if (sps != null) format.setByteBuffer("csd-0", ByteBuffer.wrap(sps))
        if (pps != null) format.setByteBuffer("csd-1", ByteBuffer.wrap(pps))
        Log.i(TAG, "configure ${width}x$height csd0=${sps?.size} csd1=${pps?.size}")
        try {
            codec = if (codecName.isNullOrEmpty()) MediaCodec.createDecoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
                    else MediaCodec.createByCodecName(codecName)
            Log.i(TAG, "decoder in use: ${codec.name}")
            codec.configure(format, surface, null, 0)
            codec.start()
        } catch (e: Exception) {
            throw IOException("H.264 decoder unavailable: ${e.message}", e)
        }
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
            // Codec stopped underneath us (session ended / surface lost).
            running = false
        }
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
                break
            }
        }
    }

    private fun recordLatency(ns: Long) {
        latSumNs += ns; latCount++; if (ns > latMaxNs) latMaxNs = ns
        val now = System.nanoTime()
        if (now - latWindowStart >= 2_000_000_000L && latCount > 0) {
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
