; AirScreen Windows installer (Inno Setup 6). Build:  ISCC scripts\AirScreen.iss
; Registers in Apps & features / Control Panel > Programs and Features, with an uninstaller.
#define AppName "AirScreen"
#define AppVersion "2.0.0"
#define Publisher "Deadserpent"
#ifndef SrcDir
  #define SrcDir "..\dist\AirScreen"
#endif
#ifndef WebView2Setup
  ; path to MicrosoftEdgeWebview2Setup.exe (the release build downloads it); empty = skip
  #define WebView2Setup ""
#endif
#ifndef FFmpegExe
  #define FFmpegExe "C:\ffmpeg\ffmpeg.exe"
#endif

[Setup]
AppId={{6F1D2C7A-3B54-4E0C-9A8D-AE5C2D0B7E41}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#Publisher}
AppCopyright=(c) 2026 {#Publisher}
VersionInfoCompany={#Publisher}
VersionInfoDescription=AirScreen Setup
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\AirScreen.exe
UninstallDisplayName={#AppName}
SetupIconFile=..\assets\branding\AirScreen.ico
OutputDir=..\installer
OutputBaseFilename=AirScreen-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Windows 10 1809 or newer (Windows 11 included)
MinVersion=10.0.17763

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs
Source: "{#FFmpegExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

#if WebView2Setup != ""
Source: "{#WebView2Setup}"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebView2
#endif

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\AirScreen.exe"; Comment: "Mirror your screen to your TV"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\AirScreen.exe"; Tasks: desktopicon

[Run]
#if WebView2Setup != ""
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft Edge WebView2 Runtime..."; Check: NeedsWebView2; Flags: waituntilterminated
#endif
Filename: "{app}\AirScreen.exe"; Description: "Launch AirScreen"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM AirScreen.exe"; Flags: runhidden; RunOnceId: "KillAirScreen"

[Code]
// AirScreen's window is Microsoft Edge WebView2. It ships with Windows 11 and current Windows 10; install it if missing.
function NeedsWebView2: Boolean;
var v: String;
begin
  Result := not (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v)
              or RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v)
              or RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v));
  if not Result then Result := (v = '') or (v = '0.0.0.0');
end;
