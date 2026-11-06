package com.airscreen.networking

import java.nio.ByteBuffer
import java.nio.ByteOrder

/** AirScreen wire protocol v2 - see shared/protocol/PROTOCOL.md. */
object Protocol {
    const val HEADER_SIZE = 24
    const val VERSION = 2
    const val MAX_PAYLOAD = 8 * 1024 * 1024
    const val MAX_CONTROL_PAYLOAD = 4096

    const val TYPE_HELLO = 1
    const val TYPE_VIDEO = 2
    const val TYPE_BYE = 3
    const val TYPE_AUDIO = 4
    const val TYPE_AUTH_REQUEST = 5
    const val TYPE_AUTH_CHALLENGE = 6
    const val TYPE_AUTH_PROOF = 7
    const val TYPE_AUTH_OK = 8
    const val TYPE_AUTH_FAIL = 9

    const val FLAG_KEYFRAME = 0x01

    private val MAGIC = byteArrayOf('A'.code.toByte(), 'S'.code.toByte(), 'C'.code.toByte(), 'R'.code.toByte())

    class ProtocolException(message: String) : Exception(message)

    data class Header(val type: Int, val flags: Int, val seq: Long, val ptsUs: Long, val length: Int) {
        val keyframe: Boolean get() = flags and FLAG_KEYFRAME != 0
    }

    fun buildHeader(type: Int, seq: Long, ptsUs: Long, length: Int, flags: Int = 0): ByteArray {
        val buf = ByteBuffer.allocate(HEADER_SIZE).order(ByteOrder.BIG_ENDIAN)
        buf.put(MAGIC).put(VERSION.toByte()).put(type.toByte()).put(flags.toByte()).put(0)
        buf.putInt((seq and 0xFFFFFFFFL).toInt()).putLong(ptsUs).putInt(length)
        return buf.array()
    }

    /** Parses and validates a header. Throws [ProtocolException] on anything malformed. */
    fun parseHeader(data: ByteArray): Header {
        if (data.size != HEADER_SIZE) throw ProtocolException("short header")
        for (i in 0 until 4) if (data[i] != MAGIC[i]) throw ProtocolException("bad magic")
        val buf = ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN)
        val version = buf.get(4).toInt() and 0xFF
        val type = buf.get(5).toInt() and 0xFF
        val flags = buf.get(6).toInt() and 0xFF
        val seq = buf.getInt(8).toLong() and 0xFFFFFFFFL
        val ptsUs = buf.getLong(12)
        val length = buf.getInt(20)

        if (version != VERSION) throw ProtocolException("unsupported version $version (update AirScreen on both devices)")
        if (type !in TYPE_HELLO..TYPE_AUTH_FAIL) throw ProtocolException("unknown type $type")
        if (ptsUs < 0) throw ProtocolException("bad timestamp")
        if (length < 0 || length > MAX_PAYLOAD) throw ProtocolException("bad payload length $length")
        if (type >= TYPE_AUTH_REQUEST && length > MAX_CONTROL_PAYLOAD) throw ProtocolException("control payload too large")
        return Header(type, flags, seq, ptsUs, length)
    }
}
