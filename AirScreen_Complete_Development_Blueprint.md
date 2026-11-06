# AirScreen
## Practical Development Blueprint — From First Connection to Complete Product

**Project:** AirScreen  
**Purpose:** Mirror a Windows 11 laptop's full desktop wirelessly to a Sony BRAVIA 2 S25 Google TV over a local network.  
**Sender:** Windows 11 laptop with NVIDIA GeForce RTX 3060 Laptop GPU  
**Receiver:** Sony BRAVIA 2 S25 Google TV  
**Network:** Wi-Fi, Ethernet, or mixed Wi-Fi/Ethernet on the same reachable LAN

> **Build a working connection first.** Keep the architecture extensible, but do not build commercial-scale infrastructure before the first picture appears on the TV.

---

# 1. Project goal

AirScreen consists of two applications:

1. **AirScreen Sender:** A Windows application that captures the laptop desktop and sends it over the local network.
2. **AirScreen Receiver:** An Android TV application installed on the Sony BRAVIA that receives, decodes, and displays the stream.

The first objective is simple:

**Open AirScreen on Windows, open AirScreen Receiver on the TV, connect them, and see the full Windows desktop on the TV.**

After installation, local streaming must work without a cloud account or internet connection.

## 1.1 Product principles

- No subscription, activation service, or account requirement.
- No mandatory cloud server or advertisements.
- No AirScreen-imposed session timeout or data quota.
- No arbitrary bitrate, resolution, FPS, or receiver-count cap.
- Configurable quality settings.
- Secure pairing and encrypted production media.
- Automatic recovery from ordinary network interruptions.
- Clear diagnostics when hardware or network capability is insufficient.

**Engineering reality:** No artificial software limits does not mean physically unlimited performance. The GPU, TV decoder, display refresh rate, network, operating system, and thermal conditions determine what can actually run. AirScreen must report these constraints honestly.

---

# 2. Build in three versions

Do not implement every advanced feature at once.

## Version 1 — First working desktop mirror

Build only:
- Windows desktop capture.
- H.264 video encoding.
- Local network connection.
- Android TV video receiver.
- Fullscreen display on the Sony TV.
- Manual IP connection.
- Start and stop controls.

Do not add audio, multiple receivers, HDR, remote control, or advanced adaptive streaming yet.

## Version 2 — Make it useful

Add:
- System audio.
- Automatic TV discovery.
- Secure pairing.
- Automatic reconnection.
- Resolution and FPS controls.
- Bitrate controls.
- Better buffering and latency management.
- Diagnostics.

## Version 3 — Make it robust

Add:
- WebRTC production transport.
- Adaptive bitrate.
- HEVC where both devices support it.
- Multiple receivers.
- Improved audio/video synchronization.
- HDR where supported end-to-end.
- Long-duration stability improvements.
- Installer and release packaging.

This staged plan avoids unnecessary complexity before the basic use case works.

---

# 3. Recommended technology stack

Use the simplest technology that proves each part of the system. Keep the media pipeline modular so the prototype can later be upgraded.

## 3.1 Windows sender

| Component | Version 1 | Later improvement |
|---|---|---|
| Language | Python | Native C++ components if profiling justifies them |
| Desktop capture | DXcam | Windows Graphics Capture / Desktop Duplication |
| Video encoding | FFmpeg + NVIDIA NVENC | Direct NVENC integration |
| Codec | H.264 | HEVC when receiver supports it |
| Network prototype | UDP on local network | WebRTC for production |
| User interface | Minimal UI or CLI | Polished desktop UI |
| Configuration | JSON | Versioned configuration schema |

Why start this way:
- Python makes the first sender easier to develop and debug.
- DXcam provides a practical Windows capture prototype.
- FFmpeg can use the RTX 3060's NVENC encoder when the installed build and driver expose it.
- A minimal sender is easier to validate than a large desktop application.

Verify NVENC availability before depending on it. Do not silently fall back to CPU encoding without reporting it.

## 3.2 Sony TV receiver

| Component | Technology |
|---|---|
| Application | Native Android TV app |
| Language | Kotlin |
| Video decoder | Android MediaCodec |
| Rendering | SurfaceView |
| Network | Android sockets for prototype; WebRTC SDK later |
| UI | Simple Android TV interface |
| Build | Android Studio / Gradle |

The Sony TV must run the AirScreen Receiver application. A TV IP address alone cannot receive a custom video stream.

Verify the exact BRAVIA firmware, Android version, supported decoder profiles, and whether custom APK installation is permitted.

## 3.3 Production transport

A basic UDP prototype is acceptable for proving the video path, but raw UDP alone is not a complete production streaming system. Production needs packetization, sequence numbers, timing, loss handling, congestion control, and recovery.

Use WebRTC for production rather than implementing ICE, DTLS-SRTP, RTP, congestion control, and jitter buffering from scratch.

---

# 4. How the connection works

## 4.1 Network topology

Both devices must be on the same reachable local network.

```text
                 Wi-Fi / Ethernet router
                          |
                +---------+---------+
                |                   |
          Windows laptop        Sony BRAVIA
          192.168.1.105         192.168.1.110
          Wi-Fi/Ethernet        Wi-Fi/Ethernet
                |                   |
                +------ Local LAN --+
```

The IP addresses above are examples only.

Supported combinations:
- Laptop Wi-Fi → TV Wi-Fi.
- Laptop Ethernet → TV Ethernet.
- Laptop Wi-Fi → TV Ethernet.
- Laptop Ethernet → TV Wi-Fi.

Mixed connections work if the router bridges both devices and does not isolate wireless clients from wired clients. Internet access is not required after installation.

## 4.2 First connection: manual IP

For the first prototype, use manual IP entry. This avoids building discovery before the video pipeline is proven.

On Sony TV:
1. Open Settings.
2. Open Network & Internet.
3. Select the connected network.
4. Find and record the TV IP address.

On Windows PowerShell:

```powershell
ipconfig
```

Find the active Wi-Fi or Ethernet adapter and its IPv4 address.

Test the TV address:

```powershell
ping <TV_IP_ADDRESS>
```

A successful ping is useful. A failed ping does not necessarily mean the TV is unreachable because some devices block ICMP.

The sender should initially let the user enter the TV IP and connect to the receiver's configured local port.

## 4.3 Later connection: automatic discovery

After manual connection works, add mDNS/DNS-SD discovery.

Suggested service:

```text
_airscreen._tcp.local
```

Discovery metadata may include:
- Receiver name.
- Protocol version.
- Control port.
- Non-secret device identifier.
- High-level capabilities.

Never publish pairing secrets, tokens, or private keys in discovery records. Discovery is not authentication.

---

# 5. Simplified system architecture

## 5.1 Version 1

```text
WINDOWS 11 LAPTOP
+--------------------------------+
| AirScreen Sender               |
|                                |
| Desktop Capture (DXcam)        |
|             |                  |
|             v                  |
| FFmpeg H.264 / NVENC           |
|             |                  |
|             v                  |
| Local Network Sender           |
+-------------|------------------+
              |
         Wi-Fi / Ethernet
              |
+-------------|------------------+
| SONY BRAVIA GOOGLE TV          |
|                                |
| AirScreen Receiver             |
|             |                  |
|             v                  |
| Receive Video                  |
|             |                  |
|             v                  |
| MediaCodec Decoder             |
|             |                  |
|             v                  |
| Fullscreen SurfaceView         |
+--------------------------------+
```

## 5.2 Later production architecture

```text
Windows Capture
      |
      v
GPU Texture Pipeline
      |
      v
NVENC H.264 / HEVC
      |
      v
WebRTC Sender
      |
      | Encrypted local media
      |
      v
WebRTC Receiver
      |
      v
Android MediaCodec
      |
      v
TV Fullscreen Renderer
```

Keep capture, encoder, transport, and receiver as separate modules. This lets the prototype transport be replaced without rewriting desktop capture or TV rendering.

---

# 6. Repository structure

Start with a small monorepo. Do not create folders for features that do not exist yet.

```text
airscreen/
|
+-- sender/
|   +-- airscreen_sender/
|   |   +-- capture/
|   |   +-- encoding/
|   |   +-- networking/
|   |   +-- config/
|   |   +-- diagnostics/
|   |   +-- main.py
|   +-- tests/
|   +-- requirements.txt
|
+-- receiver/
|   +-- app/
|       +-- src/
|           +-- main/
|               +-- java/com/airscreen/
|                   +-- ui/
|                   +-- receiver/
|                   +-- decoder/
|                   +-- networking/
|                   +-- config/
|                   +-- diagnostics/
|
+-- shared/
|   +-- protocol/
|   +-- test-data/
|
+-- docs/
|   +-- ARCHITECTURE.md
|   +-- BUILDING.md
|   +-- NETWORKING.md
|   +-- TV_COMPATIBILITY.md
|   +-- TESTING.md
|   +-- RELEASE.md
|
+-- scripts/
+-- benchmarks/
+-- README.md
+-- LICENSE
+-- THIRD_PARTY_NOTICES.md
+-- .gitignore
```

Add modules only when implementation needs them.

---

# 7. Development environment

## 7.1 Windows

Install:
- Python 3.11 or a version supported by the selected DXcam release.
- Python virtual environment.
- FFmpeg build with NVIDIA NVENC support.
- Compatible NVIDIA driver.
- Git.
- Visual Studio Build Tools only if a dependency requires native compilation.

Create the project:

```powershell
mkdir airscreen
cd airscreen

mkdir sender, receiver, shared, docs, scripts, benchmarks

cd sender
python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
```

Install and pin the DXcam version selected during implementation.

Verify FFmpeg:

```powershell
ffmpeg -version
ffmpeg -hide_banner -encoders | findstr nvenc
```

Expected encoder names normally include:

```text
h264_nvenc
hevc_nvenc
```

If absent, install a suitable FFmpeg build and verify driver compatibility.

Verify the GPU:

```powershell
nvidia-smi
```

## 7.2 Android TV

Install:
- Android Studio.
- Android SDK.
- Android Platform Tools (`adb`).
- Kotlin and Gradle through the Android project.
- Android TV development tools.

Use the actual Sony TV for decoder and performance validation. An emulator cannot confirm the TV's hardware decoder capabilities.

---

# 8. Implementation roadmap

Build and verify one milestone at a time.

## Milestone 0 — Hardware and network preflight

Tasks:
1. Confirm exact Sony model.
2. Record Android release and SDK level.
3. Check whether custom APK installation is permitted.
4. Check TV IP address.
5. Check laptop IP address.
6. Verify local network reachability.
7. Verify RTX 3060 visibility.
8. Verify FFmpeg NVENC availability.
9. Query the TV's H.264 decoder capability.

Windows:

```powershell
nvidia-smi
ipconfig
Get-NetAdapter
```

TV, if authorized ADB debugging is available:

```bash
adb devices
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.sdk
adb shell dumpsys media.codec
```

**Deliverable:** Hardware and network compatibility report.

Do not proceed until the TV can install and run a basic test APK.

## Milestone 1 — Capture the Windows desktop

Tasks:
1. Create a Python sender.
2. Capture one monitor using DXcam.
3. Display or save captured frames locally.
4. Add monitor selection.
5. Handle capture stop/start.
6. Record capture FPS and errors.

**Deliverable:** Stable local desktop capture test.

## Milestone 2 — Encode H.264

Tasks:
1. Send captured frames to FFmpeg.
2. Use `h264_nvenc`.
3. Set a test resolution and frame rate supported by the source.
4. Produce an encoded H.264 stream or test file.
5. Verify playback independently.
6. Record encoder errors and performance.

**Deliverable:** Valid H.264 stream encoded using the RTX 3060.

Do not optimize multiple codecs yet. H.264 is the first compatibility target.

## Milestone 3 — Build the Android TV receiver

Tasks:
1. Create a basic Android TV Kotlin application.
2. Create a simple receiver screen.
3. Add a network receiver component.
4. Add MediaCodec H.264 decoding.
5. Render decoded frames on a SurfaceView.
6. Add a disconnect/stop action.
7. Install and launch the APK on the Sony TV.

**Deliverable:** TV plays a locally supplied H.264 test stream.

This proves that the TV can run our application and decode the selected format.

## Milestone 4 — Connect sender and receiver

Tasks:
1. Let the receiver display its IP address and listening port.
2. Let the Windows sender accept the TV IP.
3. Establish a local socket connection.
4. Define a small versioned packet format.
5. Add frame boundaries, sequence numbers, timestamps, and payload sizes.
6. Add receiver-side buffering.
7. Display received video fullscreen.
8. Add disconnect and error handling.

**Deliverable:** Live desktop video from Windows to Sony TV.

The prototype transport must handle packet loss, out-of-order packets, oversized frames, and malformed messages safely. Do not assume one video frame fits into one UDP datagram. Use appropriate packetization and a tested reassembly strategy.

## Milestone 5 — Improve transport

Once the basic video path works:
1. Benchmark the prototype.
2. Identify latency and packet-loss behavior.
3. Integrate native WebRTC.
4. Add authenticated signalling.
5. Add ICE negotiation.
6. Use encrypted DTLS-SRTP media.
7. Verify direct LAN connectivity without public relay services.
8. Add network statistics.

**Deliverable:** Production-oriented real-time media connection.

Avoid building a custom production media transport unless benchmarking demonstrates a clear need.

## Milestone 6 — Add audio

Tasks:
1. Capture system audio using WASAPI loopback.
2. Encode audio using Opus.
3. Transport audio.
4. Decode audio on Android.
5. Play using AudioTrack.
6. Synchronize audio and video.
7. Add mute and audio enable/disable.

**Deliverable:** Synchronized desktop audio and video.

## Milestone 7 — Improve usability

Add:
- Automatic receiver discovery.
- PIN/QR secure pairing.
- Automatic reconnection.
- Device names.
- Resolution selection.
- FPS selection.
- Bitrate controls.
- Adaptive quality.
- Fullscreen and disconnect controls.
- Logs and diagnostics.

**Deliverable:** Usable application rather than a developer-only prototype.

## Milestone 8 — Advanced capabilities

Only after the main path is stable:
- HEVC if the TV supports it.
- HDR if the entire pipeline supports it.
- Multiple receivers.
- Per-receiver quality.
- Better GPU texture handling.
- Advanced latency controls.
- Remote keyboard/mouse forwarding as explicit opt-in.
- Additional display and audio options.

**Deliverable:** Feature-complete AirScreen release candidate.

## Milestone 9 — Release and maintenance

Tasks:
1. Create Windows installer.
2. Package Android TV APK.
3. Document installation and pairing.
4. Add version compatibility checks.
5. Review dependency licences.
6. Test install, upgrade, rollback, and uninstall.
7. Test offline local operation.
8. Publish release notes and known limitations.

**Deliverable:** Reproducible, installable release packages.

---

# 9. Configuration design

Do not hard-code arbitrary product limits. Expose user settings while validating them against actual capabilities.

Example initial configuration:

```json
{
  "application": {
    "name": "AirScreen",
    "internet_required": false,
    "session_timeout": null,
    "telemetry": false
  },
  "capture": {
    "backend": "dxcam",
    "monitor": "primary",
    "cursor": true
  },
  "video": {
    "codec": "h264",
    "encoder": "nvenc",
    "resolution": "source",
    "frame_rate": "source",
    "bitrate_mode": "manual",
    "bitrate": "auto"
  },
  "audio": {
    "enabled": false,
    "backend": "wasapi",
    "codec": "opus"
  },
  "network": {
    "mode": "local",
    "transport": "prototype",
    "discovery": "manual_ip"
  },
  "security": {
    "pairing_required": true,
    "encrypted_media": true
  }
}
```

This is an illustrative schema, not a claim that all settings are implemented in Version 1.

Validation rules:
- Reject malformed values.
- Detect unsupported codec and resolution combinations.
- Display requested and negotiated values.
- Do not silently clamp settings.
- Keep queues bounded to protect memory.
- Apply backpressure when the sender or receiver cannot keep up.
- Do not confuse “no application cap” with unbounded memory allocation.

---

# 10. Quality and performance targets

These are goals for measurement, not guarantees.

| Metric | Initial goal |
|---|---|
| First video | Stable 1080p H.264 |
| Frame rate | 30 FPS baseline, then 60 FPS if supported |
| Latency | Minimize and measure end-to-end |
| Audio | Add after stable video |
| Session duration | No AirScreen-imposed timeout |
| Data quota | None imposed by AirScreen |
| Bitrate | User configurable, path-dependent |
| Resolution | Capability-dependent |
| Receiver count | Resource-dependent, no arbitrary product cap |

Test higher modes only after confirming the TV decoder, display, encoder, and network can sustain them.

---

# 11. Testing plan

## 11.1 Functional tests

- Sender discovers or connects to the correct TV.
- Incorrect IP gives a clear error.
- Receiver not running gives a clear error.
- Video starts and stops correctly.
- Display selection works.
- Resolution changes are handled.
- TV app restart is handled.
- Wi-Fi interruption is detected.
- Ethernet interruption is detected.
- Mixed Wi-Fi/Ethernet works when the router allows it.
- Unsupported codec is rejected or renegotiated.
- Malformed network data cannot crash the receiver.

## 11.2 Performance tests

Test:
- 1080p 30 FPS.
- 1080p 60 FPS.
- Higher resolutions only where supported.
- Low-motion desktop.
- High-motion video.
- Window movement.
- Multiple monitor layouts.

Measure:
- Capture FPS.
- Encode FPS.
- Decode FPS.
- Render FPS where available.
- Bitrate.
- Packet loss.
- Jitter.
- RTT.
- Estimated end-to-end latency.
- CPU usage.
- GPU encoder usage.
- Memory usage.
- Thermal behavior.

Do not label RTT as end-to-end display latency. Use a physical measurement method if true glass-to-glass latency is required.

## 11.3 Stability tests

- 1-hour continuous streaming.
- 8-hour soak test.
- Repeated connect/disconnect.
- Sender restart.
- TV receiver restart.
- Network cable unplug/replug.
- Wi-Fi disconnect/reconnect.
- Sleep/wake.
- Encoder reinitialization.

Look for memory leaks, unbounded queues, stale sessions, and progressive latency growth.

---

# 12. Security and privacy

Even on a home network, do not trust every device automatically.

Minimum requirements:
- Pairing required before production media sessions.
- Authenticated signalling.
- Encrypted media.
- No hard-coded credentials.
- No secrets in logs.
- Revocable trusted devices.
- Pairing PIN expires and is rate-limited.
- Firewall rules limited to required local network access.
- No public internet listener by default.
- Remote control disabled unless explicitly enabled.

The UDP prototype should be used only on a trusted test LAN. Do not expose it to public networks or treat it as a secure production protocol.

---

# 13. UI design

## Windows sender

Keep the first interface minimal:

```text
+--------------------------------------+
|              AirScreen               |
+--------------------------------------+
|                                      |
|  Receiver IP: [192.168.1.110      ]  |
|                                      |
|  Status: Disconnected                 |
|                                      |
|  Quality: 1080p / 30 FPS              |
|                                      |
|       [ Connect ]  [ Disconnect ]    |
|                                      |
|  Capture: Primary Display             |
|  Encoder: NVIDIA NVENC                |
|                                      |
|  Diagnostics                         |
+--------------------------------------+
```

Later add discovered devices, pairing, quality presets, advanced settings, live metrics, and log export.

## Sony TV receiver

```text
+--------------------------------------+
|              AirScreen               |
|                                      |
|           Ready to connect            |
|                                      |
|  Receiver IP: 192.168.1.110           |
|  Status: Waiting for sender           |
|                                      |
|  [ Settings ]                        |
+--------------------------------------+
```

When connected, hide the interface and render the incoming desktop fullscreen.

---

# 14. Troubleshooting

| Problem | Check |
|---|---|
| TV not reachable | IP address, subnet, router isolation |
| TV not discovered | mDNS/multicast and receiver status |
| APK will not install | Android version, developer options, package compatibility |
| Black screen | Capture, codec negotiation, decoder, surface |
| Stuttering | Network loss, encoder speed, decoder performance |
| Audio out of sync | Timestamp and clock handling |
| Connection drops | Router, firewall, interface changes |
| NVENC unavailable | NVIDIA driver and FFmpeg build |
| TV cannot decode | MediaCodec capabilities and selected H.264 profile |

Windows checks:

```powershell
nvidia-smi
ipconfig
Get-NetAdapter
```

TV checks, if ADB is enabled and authorized:

```bash
adb devices
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.sdk
adb shell dumpsys media.codec
```

---

# 15. Engineering practices

- Use Git from the beginning.
- Commit one working feature at a time.
- Pin dependencies.
- Record build instructions.
- Write tests for packet parsing and session state.
- Keep UI separate from media logic.
- Use structured logs.
- Do not store secrets in Git.
- Record known hardware limitations.
- Review dependency licences.
- Maintain third-party notices.
- Test clean installation and uninstall.

Suggested commits:

```text
feat(sender): add desktop capture
feat(encoder): add H.264 NVENC output
feat(receiver): add Android TV playback
feat(network): add local sender connection
feat(streaming): display live desktop on TV
feat(audio): add system audio streaming
feat(discovery): add automatic receiver discovery
feat(pairing): add trusted device pairing
feat(metrics): add stream diagnostics
test(stability): add reconnect and soak tests
docs(release): document installation and setup
```

---

# 16. Official references

- Windows Graphics Capture: https://learn.microsoft.com/en-us/windows/uwp/audio-video-camera/screen-capture
- Desktop Duplication API: https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/desktop-dup-api
- WASAPI: https://learn.microsoft.com/en-us/windows/win32/coreaudio/wasapi
- NVIDIA Video Codec SDK: https://developer.nvidia.com/video-codec-sdk
- FFmpeg: https://ffmpeg.org/documentation.html
- WebRTC: https://webrtc.org/
- Android TV: https://developer.android.com/tv
- Android MediaCodec: https://developer.android.com/reference/android/media/MediaCodec
- Android AudioTrack: https://developer.android.com/reference/android/media/AudioTrack
- Android NSD: https://developer.android.com/develop/connectivity/wifi/use-nsd
- Sony India Support: https://www.sony.co.in/electronics/support

---

# 17. First actions — start here

Do not start by implementing every feature.

## Step 1 — Create the repository

```powershell
mkdir airscreen
cd airscreen
git init
mkdir sender, receiver, shared, docs, scripts
```

## Step 2 — Verify the laptop

```powershell
nvidia-smi
ffmpeg -hide_banner -encoders | findstr nvenc
ipconfig
```

## Step 3 — Verify the TV

Find the exact model and IP in TV settings.

If ADB is available and authorized:

```bash
adb devices
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.sdk
adb shell dumpsys media.codec
```

## Step 4 — Build a test receiver

Create a minimal Android TV application and install it on the Sony TV. Confirm that it launches and can play a local H.264 test file.

## Step 5 — Build the sender

Capture the Windows desktop and encode H.264 with NVENC. Validate the stream locally before sending it over the network.

## Step 6 — Connect them

Start the receiver, enter its IP address in the sender, establish the local stream, and display the desktop fullscreen.

## Step 7 — Improve after the first successful connection

Add audio, secure pairing, discovery, WebRTC, adaptive quality, reconnection, advanced codecs, and packaging in that order.

---

# 18. Final direction

AirScreen should be a small, reliable product that grows through verified milestones.

**First priority:** Get the Windows desktop displayed on the Sony BRAVIA.

**Second priority:** Make the connection stable, low-latency, and synchronized with audio.

**Third priority:** Add discovery, pairing, quality controls, advanced codecs, multiple receivers, and production packaging.

Keep the long-term design extensible, but keep the first implementation small. Every feature must be tested on the actual RTX 3060 laptop and Sony BRAVIA receiver before being marked complete.

**AirScreen — Your desktop, your TV, your network.**
