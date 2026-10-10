; ClipCatch の Windows インストーラ（Inno Setup 6）。
; packaging/build.py から次の定数を渡して使う:
;   AppVersion  バージョン（例: 1.0.0）
;   SourceDir   PyInstaller が作った dist\ClipCatch フォルダ
;   OutputDir   出力先
;   OutputName  出力ファイル名（拡張子なし）

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "ClipCatch"
#define AppPublisher "myuto2490"
#define AppURL "https://github.com/myuto2490/ClipCatch"
#define AppExe "ClipCatch.exe"

[Setup]
; AppId はアップデートや削除で同じアプリと認識させるための値。変更しないこと。
AppId={{04A3EFD1-9E40-4AFF-82A3-D173C2A8DD82}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; 既定では管理者権限なしで自分だけに入れる。全員向けはダイアログで選べる。
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename={#OutputName}
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
LicenseFile=..\..\LICENSE
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

; 自動取得したツール（%LOCALAPPDATA%\ClipCatch）と設定は、再インストールに備えて残す。
; README の「アンインストール」に消し方を書いている。
