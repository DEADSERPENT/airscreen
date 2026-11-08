; AirScreen Windows installer (Inno Setup 6). Build:  ISCC scripts\AirScreen.iss
; Registers in Apps & features / Control Panel > Programs and Features, with an uninstaller.
#define AppName "AirScreen"
#define AppVersion "2.0.0"
#define Publisher "Deadserpent Corporation"
#ifndef SrcDir
  #define SrcDir "..\dist\AirScreen"
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
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs
Source: "{#FFmpegExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\AirScreen.exe"; Comment: "Mirror your screen to your TV"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\AirScreen.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AirScreen.exe"; Description: "Launch AirScreen"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM AirScreen.exe"; Flags: runhidden; RunOnceId: "KillAirScreen"
