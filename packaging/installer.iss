#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\本機PDF工具箱"
#endif
#ifndef OutputDir
  #define OutputDir "..\release"
#endif
#ifndef OutputBaseName
  #define OutputBaseName "本機PDF工具箱-安裝程式-未簽章測試版"
#endif

[Setup]
AppId={{18D34507-C3D3-4532-9F04-B88CC2D59EC8}
AppName=本機 PDF 工具箱
AppVersion={#MyAppVersion}
AppVerName=本機 PDF 工具箱 {#MyAppVersion}
AppPublisher=Local PDF Toolbox
DefaultDirName={localappdata}\Programs\LocalPDFToolbox
DefaultGroupName=本機 PDF 工具箱
UninstallDisplayIcon={app}\本機PDF工具箱.exe
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
CloseApplicationsFilter=本機PDF工具箱.exe
AppMutex=Local\LocalPDFToolbox
VersionInfoVersion={#MyAppVersion}.0
VersionInfoProductName=本機 PDF 工具箱
VersionInfoDescription=本機 PDF 工具箱安裝程式
UseSetupLdr=yes

[Languages]
Name: "chinesetraditional"; MessagesFile: "languages\ChineseTraditional.isl"

[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑"; GroupDescription: "其他工作："; Flags: checkedonce

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\本機 PDF 工具箱"; Filename: "{app}\本機PDF工具箱.exe"
Name: "{autodesktop}\本機 PDF 工具箱"; Filename: "{app}\本機PDF工具箱.exe"; Tasks: desktopicon

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\LocalPDFToolbox"
