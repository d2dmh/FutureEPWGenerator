#define MyAppName "Future EPW Generator"
#define MyAppVersion "1.0.0"
#define MyAppExeName "FutureEPWGenerator.exe"

[Setup]
AppId={{A312EF77-23FB-4FE6-8A8E-FE4E41E11000}
AppName={#MyAppName}
AppVersion=1.0.0
AppPublisher=Future EPW Generator Project
DefaultDirName={localappdata}\Programs\Future EPW Generator
DefaultGroupName=Future EPW Generator
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=FutureEPWGenerator_Setup_v1.0.0
SetupIconFile=..\assets\app_icon.ico
UninstallDisplayIcon={app}\FutureEPWGenerator.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion=1.0.0.0
VersionInfoProductName=Future EPW Generator
VersionInfoProductVersion=1.0.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\FutureEPWGenerator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Future EPW Generator"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Future EPW Generator"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Future EPW Generator"; Flags: nowait postinstall skipifsilent
