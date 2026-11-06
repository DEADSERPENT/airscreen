package com.airscreen.decoder

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.media.MediaCodec
import android.media.MediaFormat
import android.os.Build
import java.io.IOException
import java.nio.ByteBuffer

/** Opus -> MediaCodec -> AudioTrack (low-latency). Fed one 20 ms Opus packet at a time. */
class AudioPlayer(opusHead: ByteArray, private val sampleRate: Int, private val channels: Int) {
    private val codec: MediaCodec
    private val track: AudioTrack
    private val outThread: Thread
    @Volatile private var running = true
    @Volatile var muted = false

    init {
        val format = MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_OPUS, sampleRate, channels)
        val preSkip = (opusHead[10].toInt() and 0xFF) or ((opusHead[11].toInt() and 0xFF) shl 8)
        val preSkipNs = preSkip.toLong() * 1_000_000_000L / 48_000L
        format.setByteBuffer("csd-0", ByteBuffer.wrap(opusHead))
        format.setByteBuffer("csd-1", ByteBuffer.wrap(leLong(preSkipNs)))
        format.setByteBuffer("csd-2", ByteBuffer.wrap(leLong(80_000_000L))) // seek pre-roll: 80 ms

        val channelMask = if (channels == 1) AudioFormat.CHANNEL_OUT_MONO else AudioFormat.CHANNEL_OUT_STEREO
        val minBuf = AudioTrack.getMinBufferSize(sampleRate, channelMask, AudioFormat.ENCODING_PCM_16BIT)
        val builder = AudioTrack.Builder()
            .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_MOVIE).build())
            .setAudioFormat(AudioFormat.Builder().setSampleRate(sampleRate).setChannelMask(channelMask)
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
            .setBufferSizeInBytes(maxOf(minBuf, sampleRate * channels * 2 / 10)) // >= 100 ms: survives jitter
            .setTransferMode(AudioTrack.MODE_STREAM)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) builder.setPerformanceMode(AudioTrack.PERFORMANCE_MODE_LOW_LATENCY)
        track = builder.build()

        try {
            codec = MediaCodec.createDecoderByType(MediaFormat.MIMETYPE_AUDIO_OPUS)
            codec.configure(format, null, null, 0)
            codec.start()
        } catch (e: Exception) {
            track.release()
            throw IOException("Opus decoder unavailable: ${e.message}", e)
        }
        track.play()
        outThread = Thread({ drain() }, "airscreen-audio-out").also { it.start() }
    }

    fun queue(packet: ByteArray, ptsUs: Long) {
        if (!running) return
        try {
            val index = codec.dequeueInputBuffer(5_000)
            if (index < 0) return // decoder busy: dropping 20 ms is inaudible compared with growing latency
            val buf = codec.getInputBuffer(index) ?: return
            (buf as java.nio.Buffer).clear() // Buffer cast: avoids NoSuchMethodError on Android < 13
            buf.put(packet)
            codec.queueInputBuffer(index, 0, packet.size, ptsUs, 0)
        } catch (_: IllegalStateException) {
            running = false
        }
    }

    private fun drain() {
        val info = MediaCodec.BufferInfo()
        while (running) {
            try {
                val index = codec.dequeueOutputBuffer(info, 10_000)
                if (index >= 0) {
                    val out = codec.getOutputBuffer(index)
                    if (out != null && info.size > 0 && !muted) {
                        (out as java.nio.Buffer).position(info.offset)
                        (out as java.nio.Buffer).limit(info.offset + info.size)
                        track.write(out, info.size, AudioTrack.WRITE_NON_BLOCKING)
                    }
                    codec.releaseOutputBuffer(index, false)
                }
            } catch (_: IllegalStateException) {
                break
            }
        }
    }

    private fun leLong(v: Long): ByteArray = ByteArray(8) { ((v shr (8 * it)) and 0xFF).toByte() }

    fun stop() {
        running = false
        outThread.join(1000)
        try {
            track.stop()
        } catch (_: IllegalStateException) {
        }
        track.release()
        try {
            codec.stop()
        } catch (_: IllegalStateException) {
        }
        codec.release()
    }
}
