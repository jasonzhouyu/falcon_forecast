; 猛禽迁徙预测系统安装脚本
; Inno Setup 脚本

[Setup]
AppName=猛禽迁徙预测系统
AppVersion=1.0.0
AppPublisher=Jason Zhou
AppPublisherURL=https://github.com/jasonzhouyu/falcon_forecast
AppSupportURL=https://github.com/jasonzhouyu/falcon_forecast/issues
AppUpdatesURL=https://github.com/jasonzhouyu/falcon_forecast
DefaultDirName={pf}\FalconForecast
DefaultGroupName=猛禽迁徙预测系统
OutputDir=output
OutputBaseFilename=FalconForecastSetup
Compression=lzma
SolidCompression=yes

[Languages]
Name: "chinese"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\FalconForecast\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\猛禽迁徙预测系统"; Filename: "{app}\FalconForecast.exe"
Name: "{group}\卸载 猛禽迁徙预测系统"; Filename: "{uninstallexe}"
Name: "{commondesktop}\猛禽迁徙预测系统"; Filename: "{app}\FalconForecast.exe"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\猛禽迁徙预测系统"; Filename: "{app}\FalconForecast.exe"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\FalconForecast.exe"; Description: "运行猛禽迁徙预测系统"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
