; Inno Setup Script for FloatingDictionary
; create_installer.iss

[Setup]
AppName=FloatingDictionary
AppVersion=1.0
AppPublisher=Thanachote
; --- [แก้ไข] เปลี่ยนสิทธิ์การติดตั้งเป็นของผู้ใช้ปัจจุบัน (ไม่ต้องใช้ Admin) ---
PrivilegesRequired=lowest
; --- [แก้ไข] เปลี่ยนโฟลเดอร์ติดตั้งเริ่มต้นไปที่ AppData ของผู้ใช้ ---
DefaultDirName={localappdata}\FloatingDictionary
DefaultGroupName=FloatingDictionary
OutputDir=.\install
OutputBaseFilename=FloatingDictionary-Installer-v1.0
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
