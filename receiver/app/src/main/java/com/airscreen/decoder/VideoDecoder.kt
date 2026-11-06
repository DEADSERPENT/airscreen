package com.airscreen.decoder

import android.media.MediaCodec
import android.media.MediaFormat
import android.os.Build
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
    private val onFirstFrame: () -> Unit,
) {
    private val codec: MediaCodec
    private val outputThread: Thread
    @Volatile private var running = true
    private var waitingForKeyframe = true
    @Volatile private var firstFrameShown = false

    var framesDecoded = 0L
        private set
    var framesDropped = 0L
        private set

    init {
        val format = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, width, height)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) format.setInteger(MediaFormat.KEY_LOW_LATENCY, 1)
        format.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 2 * 1024 * 1024)
        try {
            codec = MediaCodec.createDecoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
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
                if (index >= 0) {
                    codec.releaseOutputBuffer(index, true) // render immediately
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

    fun stop() {
        running = false
        outputThread.join(1000)
        try {
            codec.stop()
        } catch (_: IllegalStateException) {
        }
        codec.release()
    }

    private companion object {
        const val INPUT_TIMEOUT_US = 10_000L
        const val OUTPUT_TIMEOUT_US = 10_000L
    }
}
