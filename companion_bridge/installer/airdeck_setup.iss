; Script generated for Inno Setup 6
; AirDeck Pro — Modern Enterprise Windows Companion Suite Installer

#define MyAppName "AirDeck Pro"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "AirDeck Inc."
#define MyAppURL "https://github.com/AirDeck"
#define MyAppExeName "AirDeck.exe"

[Setup]
AppId={{9F82A028-56C1-4D34-9BC6-19358E298F12}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\AirDeck
DisableProgramGroupPage=yes
OutputBaseFilename=AirDeck_Pro_Setup_v3.0
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\airdeck.ico
PrivilegesRequired=lowest
OutputDir=..\dist_installer

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Launch AirDeck automatically on Windows startup"; GroupDescription: "Startup:"

[Files]
Source: "..\dist\AirDeck\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\airdeck.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\airdeck.ico"; Tasks: desktopicon

[Registry]
; Start with Windows registry key (if task selected)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AirDeck"; ValueData: """{app}\{#MyAppExeName}"" --minimized"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
; Authorize Windows Firewall rule on install
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""AirDeck Pro"" dir=in action=allow protocol=TCP localport=8765-8775 profile=any"; Flags: runhidden
; Run application after install finishes
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Remove Windows Firewall rule on uninstall
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""AirDeck Pro"""; Flags: runhidden
