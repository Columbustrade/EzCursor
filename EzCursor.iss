; Bộ cài đặt EzCursor - biên dịch bằng Inno Setup 6 (build_installer.bat làm tự động)

#define MyAppName "EzCursor"
#define MyAppVersion "2.3.0"
#define MyAppPublisher "EzCursor"
#define MyAppExeName "EzCursor.exe"

[Setup]
AppId={{C8D323DE-4B41-41D4-952C-B7C3CDEAE4A6}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Thông tin phiên bản của chính file bộ cài (Properties)
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoCopyright=GPL-3.0
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Cài cho người dùng hiện tại, không cần quyền Admin
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=EzCursor_Setup_{#MyAppVersion}
SetupIconFile=ezcursor.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
LicenseFile=LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no
; Tự chọn ngôn ngữ theo Windows (tiếng Việt / tiếng Anh), không hỏi
ShowLanguageDialog=no

[Languages]
; Tiếng Anh đứng đầu: Windows không phải tiếng Việt thì dùng tiếng Anh
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "vietnamese"; MessagesFile: "inno\Vietnamese.isl"

[CustomMessages]
english.Options=Options:
vietnamese.Options=Tùy chọn:
english.StartupTask=Start with Windows (runs in the system tray)
vietnamese.StartupTask=Khởi động cùng Windows (chạy ngầm dưới khay hệ thống)
english.DeleteUserData=Also delete your EzCursor settings and saved cursors (cursors you made, downloaded or added)?%n%nChoose No to keep them for a later reinstall.
vietnamese.DeleteUserData=Xóa luôn cài đặt và các con trỏ bạn đã lưu (con trỏ tự tạo, tải về hoặc thêm vào)?%n%nChọn Không để giữ lại cho lần cài sau.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:Options}"
Name: "startup"; Description: "{cm:StartupTask}"; GroupDescription: "{cm:Options}"; Flags: unchecked

[InstallDelete]
; Xóa thư viện của bản cũ trước khi cài bản mới
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; Bản build dạng thư mục: EzCursor.exe + thư mục _internal
Source: "dist\EzCursor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; AppUserModelID: "Columbustrade.EzCursor"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; AppUserModelID: "Columbustrade.EzCursor"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "EzCursor"; ValueData: """{app}\{#MyAppExeName}"" --tray"; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
; Khi EzCursor tự cập nhật (cài im lặng với /RELAUNCH) thì mở lại chương trình
Filename: "{app}\{#MyAppExeName}"; Flags: nowait; Check: ShouldRelaunch

[Code]
// Tắt EzCursor đang chạy một cách an toàn (để con trỏ chuột được khôi phục)
procedure CloseEzCursor();
var
  ResultCode: Integer;
  ExePath: String;
begin
  ExePath := ExpandConstant('{app}\{#MyAppExeName}');
  if FileExists(ExePath) then
  begin
    Exec(ExePath, '--quit', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(2500);
  end;
  // Dự phòng: nếu vẫn còn chạy thì buộc tắt
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im {#MyAppExeName}', '', SW_HIDE,
       ewWaitUntilTerminated, ResultCode);
  Sleep(800);
end;

function ShouldRelaunch(): Boolean;
var
  i: Integer;
begin
  Result := False;
  for i := 1 to ParamCount do
    if CompareText(ParamStr(i), '/RELAUNCH') = 0 then
      Result := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  CloseEzCursor();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  CloseEzCursor();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // Xóa chế độ khởi động cùng Windows kể cả khi người dùng bật nó trong phần mềm
  if CurUninstallStep = usUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'EzCursor');
  // Cài đặt và con trỏ của người dùng (%APPDATA%\EzCursor): chỉ xóa khi người dùng đồng ý, mặc định giữ lại.
  // Gỡ im lặng (vd winget uninstall) thì luôn giữ.
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    if MsgBox(CustomMessage('DeleteUserData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{userappdata}\EzCursor'), True, True, True);
end;
