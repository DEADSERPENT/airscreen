package com.airscreen.networking

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProtocolTest {
    @Test fun roundTrip() {
        val h = Protocol.parseHeader(Protocol.buildHeader(Protocol.TYPE_VIDEO, 7, 123456L, 99, Protocol.FLAG_KEYFRAME))
        assertEquals(Protocol.TYPE_VIDEO, h.type)
        assertEquals(7L, h.seq)
        assertEquals(123456L, h.ptsUs)
        assertEquals(99, h.length)
        assertTrue(h.keyframe)
    }

    private fun bad(mutate: (ByteArray) -> Unit) {
        val b = Protocol.buildHeader(Protocol.TYPE_VIDEO, 0, 0, 0, 0)
        mutate(b)
        try {
            Protocol.parseHeader(b)
            throw AssertionError("expected ProtocolException")
        } catch (_: Protocol.ProtocolException) {
        }
    }

    @Test fun badMagic() = bad { it[0] = 'X'.code.toByte() }
    @Test fun badVersion() = bad { it[4] = 9 }
    @Test fun unknownType() = bad { it[5] = 99 }
    @Test fun oversizedLength() = bad { it[20] = 0x7F }
    @Test fun negativeLength() = bad { it[20] = 0xFF.toByte() }
}
