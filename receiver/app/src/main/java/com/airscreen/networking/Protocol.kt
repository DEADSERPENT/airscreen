package com.airscreen.networking

import java.nio.ByteBuffer
import java.nio.ByteOrder

/** AirScreen wire protocol v1 - see shared/protocol/PROTOCOL.md. */
object Protocol {
    const val HEADER_SIZE = 24
    const val VERSION = 1
    const val MAX_PAYLOAD = 8 * 1024 * 1024
    const val MAX_HELLO_PAYLOAD = 4096

    const val TYPE_HELLO = 1
    const val TYPE_VIDEO = 2
    const val TYPE_BYE = 3

    const val FLAG_KEYFRAME = 0x01

    private val MAGIC = byteArrayOf('A'.code.toByte(), 'S'.code.toByte(), 'C'.code.toByte(), 'R'.code.toByte())

    class ProtocolException(message: String) : Exception(message)

    data class Header(val type: Int, val flags: Int, val seq: Long, val ptsUs: Long, val length: Int) {
        val keyframe: Boolean get() = flags and FLAG_KEYFRAME != 0
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

        if (version != VERSION) throw ProtocolException("unsupported version $version")
        if (type != TYPE_HELLO && type != TYPE_VIDEO && type != TYPE_BYE) throw ProtocolException("unknown type $type")
        if (ptsUs < 0) throw ProtocolException("bad timestamp")
        if (length < 0 || length > MAX_PAYLOAD) throw ProtocolException("bad payload length $length")
        if (type == TYPE_HELLO && length > MAX_HELLO_PAYLOAD) throw ProtocolException("hello too large")
        if (type == TYPE_BYE && length != 0) throw ProtocolException("bye must be empty")
        return Header(type, flags, seq, ptsUs, length)
    }
}
