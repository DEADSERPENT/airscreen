# AirScreen

Mirror your Windows screen to an Android TV / Google TV over your own network. Low-latency H.264 (NVIDIA NVENC) video,
Opus system audio, AES-256-GCM encryption, and pairing that you approve on the TV. No account, no cloud, no telemetry.

By **Deadserpent** · MIT licensed

## Get it
Download from the [Releases](../../releases) page:
- **AirScreen-Setup-x.y.z.exe** - Windows installer (appears in Apps & features, uninstallable).
- **AirScreen-TV.apk** - install on the TV (`adb connect <TV_IP>` then `adb install -r AirScreen-TV.apk`).

## Use it
1. Open AirScreen on the TV. It shows a **pair key**.
2. Open AirScreen on the PC, choose the TV (or type the key), press **Start streaming**.
3. First time only: confirm the same 4-digit number on both screens and press **Allow** on the TV. Next time it just connects.

## Requirements
- **PC:** Windows 10 (1809+) or Windows 11, 64-bit. Any GPU: NVIDIA (NVENC), AMD (AMF) or Intel (QSV) is used automatically; with none, AirScreen encodes on the CPU and tells you. The installer includes FFmpeg and sets up the WebView2 runtime if it is missing.
- **TV:** Android TV / Google TV, Android 8+, H.264 hardware decoder, on the same network (5 GHz Wi-Fi or Ethernet recommended).

## Build from source
```
# Windows app
cd sender && python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt pyinstaller
python -m pytest tests
python -m airscreen_sender                 # run
cd .. && pyinstaller scripts/AirScreen.spec --noconfirm
iscc scripts\AirScreen.iss                 # installer -> installer\ (needs Inno Setup 6 and an ffmpeg.exe)
powershell -File scriptsuild-msix.ps1 -FFmpeg C:fmpegfmpeg.exe   # Microsoft Store .msix (needs the Windows SDK)

# TV app
cd receiver && gradlew assembleDebug testDebugUnitTest
```
Headless sender: `python -m airscreen_sender --ip <TV_IP> [--code XXX-XXX]`, `--discover`, `--preflight`.

## How it works
DXcam capture → FFmpeg (NVENC H.264, WASAPI loopback → Opus) → encrypted TCP → Android MediaCodec. Wire protocol:
`shared/protocol/PROTOCOL.md`. Security model and open items: `SECURITY.md`, `docs/SECURITY_NOTES.md`.

## Known limits (be honest with users)
- Windows x64 only (no ARM64 build yet); AMD/Intel encoders are implemented but untested on real hardware; CPU encoding uses noticeably more CPU. No macOS/Linux sender.
- Plain TCP transport, 1080p30-class quality over typical Wi-Fi; no live resolution adaptation yet.
- The TV APK is debug-signed (sideload). The Windows installer is not code-signed, so SmartScreen may warn.
- Tested on one TV (Sony BRAVIA VU31) and one PC; please report hardware results in Issues.

## Contributing / security
See `CONTRIBUTING.md` and `SECURITY.md`. Third-party licenses: `THIRD_PARTY_NOTICES.md`.
