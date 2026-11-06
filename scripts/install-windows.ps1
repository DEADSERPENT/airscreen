<#
  Installs AirScreen for the current user (no admin rights needed):
    - copies the built app to %LOCALAPPDATA%\Programs\AirScreen
    - copies ffmpeg.exe next to it (used for NVENC encoding)
    - creates Start Menu and Desktop shortcuts
  Build first:  see README ("Build the Windows app").  Run:  powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
#>
param(
  [string]$Source = (Join-Path $PSScriptRoot "..\dist\AirScreen"),
  [string]$FFmpeg = ""
)
$ErrorActionPreference = "Stop"
$Source = (Resolve-Path $Source).Path
if (-not (Test-Path (Join-Path $Source "AirScreen.exe"))) { throw "AirScreen.exe not found in $Source - build the app first." }

$dest = Join-Path $env:LOCALAPPDATA "Programs\AirScreen"
Get-Process AirScreen -ErrorAction SilentlyContinue | Stop-Process -Force
if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
New-Item -ItemType Directory -Force $dest | Out-Null
Copy-Item "$Source\*" $dest -Recurse -Force

# FFmpeg: explicit path, else PATH, else common location
if (-not $FFmpeg) { $c = Get-Command ffmpeg -ErrorAction SilentlyContinue; if ($c) { $FFmpeg = $c.Source } elseif (Test-Path "C:\ffmpeg\ffmpeg.exe") { $FFmpeg = "C:\ffmpeg\ffmpeg.exe" } }
if ($FFmpeg -and (Test-Path $FFmpeg)) { Copy-Item $FFmpeg (Join-Path $dest "ffmpeg.exe") -Force; Write-Host "ffmpeg: $FFmpeg" }
else { Write-Warning "ffmpeg.exe not found. Put it next to AirScreen.exe or on PATH (needs h264_nvenc and libopus)." }

$exe = Join-Path $dest "AirScreen.exe"
$shell = New-Object -ComObject WScript.Shell
foreach ($dir in @([Environment]::GetFolderPath("Programs"), [Environment]::GetFolderPath("Desktop"))) {
  $lnk = $shell.CreateShortcut((Join-Path $dir "AirScreen.lnk"))
  $lnk.TargetPath = $exe; $lnk.WorkingDirectory = $dest; $lnk.IconLocation = "$exe,0"
  $lnk.Description = "Mirror your screen to your TV"; $lnk.Save()
}
Write-Host "Installed to $dest"
Write-Host "Start it from the Start menu or the Desktop shortcut: AirScreen"
