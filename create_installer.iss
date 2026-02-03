; Inno Setup Script for FloatingDictionary
; create_installer.iss

[Setup]
AppName=FloatingDictionary
AppVersion=3.0
AppPublisher=Thanachote
PrivilegesRequired=lowest
DefaultDirName={localappdata}\FloatingDictionary
DefaultGroupName=FloatingDictionary
OutputDir=.\install
OutputBaseFilename=FloatingDictionary-Installer-v3.0
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\FloatingDictionary.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; NOTE: The source path is the location of your built files from PyInstaller
Source: "dist\FloatingDictionary\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FloatingDictionary"; Filename: "{app}\FloatingDictionary.exe"
Name: "{group}\{cm:UninstallProgram,FloatingDictionary}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\FloatingDictionary"; Filename: "{app}\FloatingDictionary.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FloatingDictionary.exe"; Description: "{cm:LaunchProgram,FloatingDictionary}"; Flags: nowait postinstall skipifsilent
