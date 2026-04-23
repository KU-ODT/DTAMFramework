#define AppName "TrafficS"
#define AppVersion "0.82"
#define AppExeName "TrafficS.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={pf}\{#AppName}
DefaultGroupName={#AppName}
OutputBaseFilename=KADA TrafficS v0.82
OutputDir=product\installer
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
WizardStyle=modern
SetupIconFile=resources\TrafficSim.ico
UninstallDisplayIcon={app}\{#AppExeName}

[Files]
Source: "product\TrafficS\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
Source: "VC_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Run]
Filename: "{tmp}\VC_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing VC++ Runtime..."; Check: NeedsVCRedist
Filename: "{app}\{#AppExeName}"; Flags: nowait postinstall skipifsilent

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"

[Code]
function NeedsVCRedist: Boolean;
var
  installed: Cardinal;
begin
  Result := True;
  if RegQueryDWordValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', installed) then
    Result := installed <> 1;
end;
