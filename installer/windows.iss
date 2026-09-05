; SPDX-License-Identifier: AGPL-3.0-or-later
; Copyright (C) 2026 Daniel Lares

; Private Windows installer for FS PDF Compressor. Values are supplied only by
; build_windows.py; this script never uploads or publishes the generated EXE.

#ifndef SourceDir
  #error SourceDir must point at the PyInstaller application directory
#endif
#ifndef OutputDir
  #error OutputDir must point at the private candidate directory
#endif
#ifndef AppVersion
  #error AppVersion must be supplied by the build script
#endif
#ifndef OutputName
  #define OutputName "FS-PDF-Compressor-private-windows-x86_64-setup"
#endif

[Setup]
AppId={{C22CD44C-71E5-488D-9D17-28F06EAD1D1A}
AppName=FS PDF Compressor
AppVersion={#AppVersion}
AppPublisher=Daniel Lares
AppPublisherURL=https://github.com/gitlares/fs-pdf-compressor
AppSupportURL=https://github.com/gitlares/fs-pdf-compressor/issues
DefaultDirName={autopf}\FS PDF Compressor
DefaultGroupName=FS PDF Compressor
DisableProgramGroupPage=yes
LicenseFile={#SourceDir}\_internal\licenses\FS-PDF-Compressor-AGPL-3.0.txt
OutputDir={#OutputDir}
OutputBaseFilename={#OutputName}
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\FS PDF Compressor.exe
WizardStyle=modern

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\FS PDF Compressor"; Filename: "{app}\FS PDF Compressor.exe"
Name: "{autodesktop}\FS PDF Compressor"; Filename: "{app}\FS PDF Compressor.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\FS PDF Compressor.exe"; Description: "Launch FS PDF Compressor"; Flags: nowait postinstall skipifsilent
