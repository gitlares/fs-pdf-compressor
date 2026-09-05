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
UninstallDisplayIcon={app}\_internal\PDFCompresor.ico
SetupIconFile={#SourceDir}\_internal\PDFCompresor.ico
WizardStyle=modern

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\FS PDF Compressor"; Filename: "{app}\FS PDF Compressor.exe"; IconFilename: "{app}\_internal\PDFCompresor.ico"
Name: "{autodesktop}\FS PDF Compressor"; Filename: "{app}\FS PDF Compressor.exe"; IconFilename: "{app}\_internal\PDFCompresor.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Registry]
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\CompressWithFSPDFCompressor"; ValueType: string; ValueName: "MUIVerb"; ValueData: "Compress with FS PDF Compressor"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\CompressWithFSPDFCompressor"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\CompressWithFSPDFCompressor"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\_internal\PDFCompresor.ico"
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\CompressWithFSPDFCompressor\command"; ValueType: string; ValueData: """{app}\FS PDF Compressor.exe"" ""%1"""

[Run]
Filename: "{app}\FS PDF Compressor.exe"; Description: "Launch FS PDF Compressor"; Flags: nowait postinstall skipifsilent
