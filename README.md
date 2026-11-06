# AirScreen

Mirror a Windows desktop to an Android/Google TV over the local network: NVENC H.264 video + Opus system audio,
encrypted, paired by approving on the TV, quality negotiated automatically from what the TV reports.
See `AirScreen_Complete_Development_Blueprint.md` and `shared/protocol/PROTOCOL.md`.

## Sender (Windows)
```
cd sender
python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt
python -m airscreen_sender --preflight --ffmpeg C:\ffmpeg\ffmpeg.exe
python -m airscreen_sender                 # GUI: Find TVs, pick one, Connect
python -m airscreen_sender --discover      # list TVs on the network
python -m airscreen_sender --ip <TV_IP> [--code XXX-XXX]   # pair key shown on the TV, first time only; then approve on the TV
python -m pytest tests
```
Quality is automatic. `--size 1920x1080 --fps 60 --bitrate 20000` switches to manual. `--no-audio`, `--no-cursor`, `--no-reconnect` are available.

## Receiver (TV)
Open `receiver/` in Android Studio (it generates the Gradle wrapper), build, then
`adb connect <TV_IP>` and `adb install -r app/build/outputs/apk/debug/app-debug.apk`. Launch AirScreen on the TV:
it shows its IP, port 5000 and a pair key. On the PC enter the key (or pick the TV), then press Allow on the TV. Back = disconnect, Menu = forget all paired PCs.

## Testing without a TV
`python tools/test_receiver.py logs/out.h264 --state logs/rx_state.json`, then run the sender with `--ip 127.0.0.1 --code <printed code>`.
Test runs, logs and captures go in `logs/` (git-ignored).

## Known limits
- Capture goes DXcam -> pipe -> FFmpeg, which caps raw throughput (~1440p30, 1080p60). A GPU capture path is a later milestone.
- The Android app has not been compiled or run on hardware yet. Plain-TCP transport; WebRTC, HEVC, HDR, multiple receivers are later milestones.
