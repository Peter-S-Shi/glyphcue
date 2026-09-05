; GlyphCue V1 Inno Setup Offline Installer Script
; Governed by Wayfinder Issue #19, #23, #25, and #26 Charter.
; Mode: Per-user offline installer ({localappdata}\Programs\GlyphCue)
; User Data: Isolated at %USERPROFILE%\.glyphcue\

#ifndef MyAppVersion
#define MyAppVersion "0.1.0"
#endif

#ifndef MyAppRoot
#define MyAppRoot "build_artifacts\app_root"
#endif

[Setup]
AppId={{9C5E47A1-5292-491C-B7D8-B9356FE8F1D2}
AppName=GlyphCue
AppVersion={#MyAppVersion}
AppPublisher=GlyphCue Project
AppPublisherURL=https://github.com/Peter-S-Shi/glyphcue
AppSupportURL=https://github.com/Peter-S-Shi/glyphcue/issues
DefaultDirName={localappdata}\Programs\GlyphCue
DefaultGroupName=GlyphCue
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=GlyphCue-Setup
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\GlyphCue.exe
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Distribute all files from the assembled <app_root> tree
Source: "{#MyAppRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\GlyphCue"; Filename: "{app}\GlyphCue.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall GlyphCue"; Filename: "{uninstallexe}"
Name: "{autodesktop}\GlyphCue"; Filename: "{app}\GlyphCue.exe"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\GlyphCue.exe"; Description: "{cm:LaunchProgram,GlyphCue}"; Flags: nowait postinstall skipifsilent

[Code]
// Custom uninstallation page: Explicit purge option
var
  PurgeUserDataCheckbox: TNewCheckBox;

procedure InitializeUninstallProgressForm();
var
  CustomPage: TNewNotebookPage;
begin
  CustomPage := UninstallProgressForm.InnerPage;
  PurgeUserDataCheckbox := TNewCheckBox.Create(UninstallProgressForm);
  PurgeUserDataCheckbox.Parent := UninstallProgressForm;
  PurgeUserDataCheckbox.Left := ScaleX(20);
  PurgeUserDataCheckbox.Top := ScaleY(140);
  PurgeUserDataCheckbox.Width := ScaleX(360);
  PurgeUserDataCheckbox.Height := ScaleY(24);
  PurgeUserDataCheckbox.Caption := 'Remove user databases and custom settings (%USERPROFILE%\.glyphcue)';
  PurgeUserDataCheckbox.Checked := False;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserDataPath: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Check if user requested explicit purge
    if (PurgeUserDataCheckbox <> nil) and PurgeUserDataCheckbox.Checked then
    begin
      UserDataPath := ExpandConstant('{userprofile}\.glyphcue');
      if DirExists(UserDataPath) then
      begin
        DelTree(UserDataPath, True, True, True);
      end;
    end;
  end;
end;
