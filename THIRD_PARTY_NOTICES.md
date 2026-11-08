# Third-party notices

AirScreen's own code is MIT-licensed (see `LICENSE`). It uses or ships these components under their own licenses.

| Component | Use | License |
|---|---|---|
| FFmpeg (`ffmpeg.exe`, GPL build with NVENC + libopus) | H.264 / Opus encoding, run as a separate unmodified program | GPL v3 - https://ffmpeg.org , builds: https://github.com/BtbN/FFmpeg-Builds |
| DXcam | Desktop capture | MIT |
| pywebview | Native window hosting the UI | BSD-3-Clause |
| python-zeroconf | mDNS discovery | LGPL-2.1 |
| cryptography | AES-GCM, P-256 ECDH | Apache-2.0 / BSD |
| PyAudioWPatch, pycaw, comtypes | WASAPI loopback, speaker mute | MIT |
| Inter typeface | UI font | SIL OFL 1.1 |
| AndroidX / Kotlin | TV app | Apache-2.0 |

The Windows installer bundles an unmodified FFmpeg build; its source and license are available from the links above.
