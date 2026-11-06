package com.airscreen.decoder

/** Last-session facts shown in Settings > Diagnostics. Reported = from the TV itself, measured = from the last stream. */
object StreamStats {
    @Volatile var decoderName: String = ""
    @Volatile var width: Int = 0
    @Volatile var height: Int = 0
    @Volatile var fps: Int = 0
    @Volatile var decodeMs: Double = -1.0
    @Volatile var dropped: Long = 0
}
