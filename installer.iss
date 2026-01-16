[Setup]
AppName=workforce
AppVersion=1.1.14
DefaultDirName={pf}\workforce
DefaultGroupName=workforce
OutputBaseFilename=workforce_setup
OutputDir=dist
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
LicenseFile=LICENSE
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\windows\__main__.exe"; DestDir: "{app}"; DestName: "workforce.exe"; Flags: ignoreversion

[Icons]
Name: "{group}\workforce"; Filename: "{app}\workforce.exe"
Name: "{commondesktop}\workforce"; Filename: "{app}\workforce.exe"

[Run]
Filename: "{app}\workforce.exe"; Description: "Launch workforce"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

