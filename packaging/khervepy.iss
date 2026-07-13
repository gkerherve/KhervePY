; Inno Setup script for KhervePY.
;
; Builds a Windows installer from the PyInstaller one-folder output in
; dist\KhervePY. The version is passed in by build.py:
;
;     iscc /DMyAppVersion=0.7.0 packaging\khervepy.iss
;
; Copyright (C) 2026 Gwilherm Kerherve - GNU GPL v3 or later.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName "KhervePY"
#define MyAppPublisher "Gwilherm Kerherve"
#define MyAppExeName "KhervePY.exe"

[Setup]
AppId={{B9F1C2A4-4E7D-4A2B-9C31-1A2B3C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\Output
OutputBaseFilename=KhervePY-Setup-{#MyAppVersion}
SetupIconFile=khervepy.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The entire PyInstaller one-folder distribution.
Source: "..\dist\KhervePY\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
