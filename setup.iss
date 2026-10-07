; ==========================================
; KyteShelf - Inno Setup 打包腳本
; ==========================================

#define MyAppName "KyteShelf"
#define MyAppVersion "1.4.2"
#define MyAppPublisher "ais7896-hue"
#define MyAppURL "https://github.com/ais7896-hue/KyteShelf"
#define MyAppExeName "KyteShelf.exe"

[Setup]
; 應用程式基本資訊
AppId={{8E3C1B20-5A2C-497B-864D-0D8B6E3210F8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases

; 預設安裝目錄：{autopf} 會自動根據系統判定 Program Files 或使用者 AppData
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}

; 限制與支援純 64 位元環境安裝
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; 授權協議檔案（安裝精靈會顯示條款內容）
LicenseFile=LICENSE

; 輸出設定
OutputDir=Output
OutputBaseFilename=KyteShelf_Setup_v{#MyAppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; 壓縮方式（lzma2 具備極佳壓縮率與解壓效能）
Compression=lzma2/ultra64
SolidCompression=yes

; 權限設定：允許一般使用者安裝至個人目錄，亦可提權至全機安裝
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; 安裝與更新時自動偵測並關閉正在背景常駐的 KyteShelf，避免檔案被佔用
CloseApplications=yes
CloseApplicationsFilter=*.exe

[Languages]
Name: "chinesetrad"; MessagesFile: "compiler:Languages\ChineseTraditional.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinesetrad.CreateDesktopIcon=建立桌面捷徑
chinesetrad.AdditionalIcons=額外捷徑:
chinesetrad.AutoStart=開機時自動啟動置物架（常駐系統匣）
chinesetrad.AutoStartGroup=啟動設定:
chinesetrad.UninstallApp=解除安裝 {#MyAppName}
chinesetrad.LaunchApp=立即啟動 {#MyAppName}

english.CreateDesktopIcon=Create a &desktop shortcut
english.AdditionalIcons=Additional icons:
english.AutoStart=Launch KyteShelf on Windows startup (System Tray)
english.AutoStartGroup=Startup options:
english.UninstallApp=Uninstall {#MyAppName}
english.LaunchApp=Launch {#MyAppName}

; ==========================================
; 安裝自訂選項
; ==========================================
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startup"; Description: "{cm:AutoStart}"; GroupDescription: "{cm:AutoStartGroup}"

; ==========================================
; 要打包進安裝包的檔案清單
; ==========================================
[Files]
; 來源為 PyInstaller 打包產出的 dist\KyteShelf 目錄
Source: "dist\KyteShelf\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; ==========================================
; 捷徑建立設定
; ==========================================
[Icons]
; 開始功能表捷徑
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallApp}"; Filename: "{uninstallexe}"
; 桌面捷徑（由使用者勾選決定）
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; 開機自動啟動捷徑（由使用者勾選決定，放入 Startup 目錄）
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

; ==========================================
; 安裝完成後動作
; ==========================================
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent