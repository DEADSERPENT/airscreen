<#
  Builds a Microsoft Store package (.msix) from the PyInstaller output (dist\AirScreen) and an ffmpeg.exe.
  Needs the Windows 10/11 SDK (makeappx.exe, signtool.exe). Run from anywhere:
    powershell -File scripts\build-msix.ps1 -FFmpeg C:\ffmpeg\ffmpeg.exe `
      -IdentityName "12345Deadserpent.AirScreen" -Publisher "CN=XXXXXXXX-XXXX-..." -PublisherDisplay "Deadserpent"
  Identity values: Partner Center > your app > Product management > Product identity.
  Upload the unsigned .msix to Partner Center (the Store signs it). For a local test install pass -PfxPath/-PfxPassword
  (certificate Subject must equal -Publisher) and trust that cert first.
#>
param(
  [Parameter(Mandatory)][string]$FFmpeg,
  [string]$IdentityName = "Deadserpent.AirScreen",
  [string]$Publisher = "CN=Deadserpent",
  [string]$PublisherDisplay = "Deadserpent",
  [string]$Version = "2.0.0.0",              # four parts; the Store requires the last to be 0
  [string]$Source = (Join-Path $PSScriptRoot "..\dist\AirScreen"),
  [string]$Out = (Join-Path $PSScriptRoot "..\installer"),
  [string]$PfxPath = "", [string]$PfxPassword = ""
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Source = (Resolve-Path $Source).Path
if (-not (Test-Path "$Source\AirScreen.exe")) { throw "AirScreen.exe not found in $Source - run pyinstaller first." }

function Find-SdkTool($name) {
  $c = Get-Command $name -ErrorAction SilentlyContinue; if ($c) { return $c.Source }
  $hit = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\$name" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
  if (-not $hit) { throw "$name not found - install the Windows 10/11 SDK." }
  $hit.FullName
}
$makeappx = Find-SdkTool "makeappx.exe"

$stage = Join-Path ([IO.Path]::GetTempPath()) ("airscreen-msix-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory "$stage\AirScreen", "$stage\Assets" | Out-Null
Copy-Item "$Source\*" "$stage\AirScreen" -Recurse
Copy-Item $FFmpeg "$stage\AirScreen\ffmpeg.exe"
Copy-Item "$root\LICENSE", "$root\THIRD_PARTY_NOTICES.md" "$stage\AirScreen"

# Tile/logo assets rendered from the brand logo, centred on a transparent canvas.
$logo = [System.Drawing.Image]::FromFile("$root\assets\branding\airscreen-logo-1024.png")
function New-Asset($file, $w, $h) {
  $bmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.InterpolationMode = "HighQualityBicubic"; $g.SmoothingMode = "HighQuality"
  $side = [int]([Math]::Min($w, $h) * 0.8)
  $g.DrawImage($logo, [int](($w - $side) / 2), [int](($h - $side) / 2), $side, $side)
  $g.Dispose(); $bmp.Save("$stage\Assets\$file", [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
}
New-Asset "StoreLogo.png" 50 50;  New-Asset "Square44x44Logo.png" 44 44
New-Asset "Square150x150Logo.png" 150 150; New-Asset "Wide310x150Logo.png" 310 150
$logo.Dispose()

(Get-Content "$PSScriptRoot\msix\AppxManifest.xml" -Raw).
  Replace("@IDENTITY_NAME@", $IdentityName).Replace("@PUBLISHER@", $Publisher).
  Replace("@PUBLISHER_DISPLAY@", $PublisherDisplay).Replace("@VERSION@", $Version) |
  Set-Content "$stage\AppxManifest.xml" -Encoding utf8

New-Item -ItemType Directory -Force $Out | Out-Null
$msix = Join-Path (Resolve-Path $Out) "AirScreen-$Version.msix"
if (Test-Path $msix) { Remove-Item $msix }
& $makeappx pack /d $stage /p $msix /o
if ($LASTEXITCODE -ne 0) { throw "makeappx failed" }
if ($PfxPath) {
  & (Find-SdkTool "signtool.exe") sign /fd SHA256 /f $PfxPath /p $PfxPassword $msix
  if ($LASTEXITCODE -ne 0) { throw "signtool failed" }
}
Remove-Item $stage -Recurse -Force
Write-Host "Built $msix"
