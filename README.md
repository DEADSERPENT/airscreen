# AirScreen

Mirror a Windows desktop to an Android/Google TV over the local network (Version 1: H.264 via NVENC, manual IP).
See `AirScreen_Complete_Development_Blueprint.md` and `shared/protocol/PROTOCOL.md`.

## Sender (Windows)
```
cd sender
python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt
python -m airscreen_sender --preflight --ffmpeg C:\ffmpeg\ffmpeg.exe
python -m airscreen_sender --ip <TV_IP>      # or run without --ip for the GUI
python -m pytest tests
```
Requires FFmpeg with `h264_nvenc` on PATH (or `--ffmpeg`).

## Receiver (TV)
Open `receiver/` in Android Studio (it generates the Gradle wrapper), build, then
`adb connect <TV_IP>` and `adb install -r app/build/outputs/apk/debug/app-debug.apk`. Launch AirScreen on the TV; it shows its IP and port 5000.

## Testing without a TV
`python tools/test_receiver.py out.h264` then run the sender with `--ip 127.0.0.1`.

## Known V1 limits
Mouse cursor is not captured by DXcam; plain TCP, no pairing/encryption (trusted LAN only); no audio; Android app not yet verified on hardware.
