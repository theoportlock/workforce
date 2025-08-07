[Setup]
AppName=workforce
AppVersion=1.0
DefaultDirName={pf}\workforce
DefaultGroupName=workforce
OutputBaseFilename=workforce_setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "C:\\Users\\tpor598\\workforce\\dist\\windows\\workforce.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\\workforce"; Filename: "{app}\\workforce.exe"

[Run]
Filename: "{app}\\workforce.exe"; Description: "Launch workforce"; Flags: nowait postinstall skipifsilent

