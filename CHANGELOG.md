# Changelog

## Unreleased
- Runs on any Windows 10 1809+/11 x64 PC: CPU (x264) encoding when no GPU encoder works, WebView2 runtime installed on demand, generic preflight checks.
- Microsoft Store package (`scripts/build-msix.ps1`, built by the release workflow).

## 2.0.0
- Pair by key with approval on the TV, trusted-device reconnects, AES-256-GCM media, Opus audio, mDNS discovery.
- Windows installer (listed in Apps & features), new logo, crash/hang diagnostics, safer shutdown.
- A failed authentication no longer deletes a paired device key; the TV enforces an overall handshake deadline.
