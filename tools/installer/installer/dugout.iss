; Adapted from MrUmid2oo4/windows-setup-shell (MIT), commit
; d1e0c642c50fcce1e04a2ea3dccd697f46184518. See ../LICENSE.windows-setup-shell.
; Inno owns installation; custom split panels provide options -> progress -> done.
#include "product.inc"
[Setup]
AppId={{4170AF12-1FF4-4BAA-A9C7-9D49359BB183}
AppName=Dugout Atlas
AppVersion={#AppVersion}
AppPublisher=dhtjr1236-eng
AppPublisherURL=https://github.com/dhtjr1236-eng/dugout-atlas
AppSupportURL=https://github.com/dhtjr1236-eng/dugout-atlas/issues
DefaultDirName={localappdata}\Programs\Dugout Atlas
DefaultGroupName=Dugout Atlas
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=yes
DisableReadyPage=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
OutputDir={#ReleaseDir}
OutputBaseFilename=DugoutAtlas-v{#AppVersion}-Setup
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\DugoutAtlas.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern dark
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName=Dugout Atlas
VersionInfoDescription=Dugout Atlas Setup
ShowLanguageDialog=auto
LanguageDetectionMethod=uilanguage
UninstallDisplayName=Dugout Atlas
[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\hero.bmp"; Flags: dontcopy
[Tasks]
Name: "desktopicon"; Description: "Desktop shortcut"; Flags: unchecked
Name: "startmenuicon"; Description: "Start Menu shortcut"
[Icons]
Name: "{autoprograms}\Dugout Atlas"; Filename: "{app}\DugoutAtlas.exe"; WorkingDir: "{app}"; Tasks: startmenuicon
Name: "{autodesktop}\Dugout Atlas"; Filename: "{app}\DugoutAtlas.exe"; WorkingDir: "{app}"; Tasks: desktopicon
[Code]
const
  BG = $00150D08;
  PANEL = $0024160D;
  INK = $00F4F6F8;
  MUTED = $00B6A697;
  ACCENT = $00FFE500;
var
  Korean, Launched: Boolean;
  OptionsPage, ProgressPage, DonePage: TPanel;
  DirEdit: TNewEdit;
  DesktopCheck, MenuCheck, LaunchCheck: TNewCheckBox;
  Progress: TNewProgressBar;
  ProgressText, StepLabel: TNewStaticText;
function L(const Ko, En: string): string;
begin
  if Korean then Result := Ko else Result := En;
end;
function LabelAt(Parent: TWinControl; const Caption: string; X, Y, W, H, Size: Integer; Color: Integer): TNewStaticText;
begin
  Result := TNewStaticText.Create(WizardForm); Result.Parent := Parent;
  Result.SetBounds(ScaleX(X), ScaleY(Y), ScaleX(W), ScaleY(H));
  Result.AutoSize := False; Result.WordWrap := True; Result.Caption := Caption;
  Result.Font.Name := 'Segoe UI'; Result.Font.Size := Size; Result.Font.Color := Color;
end;
function NewPanel: TPanel;
begin
  Result := TPanel.Create(WizardForm); Result.Parent := WizardForm;
  Result.SetBounds(ScaleX(352), 0, ScaleX(608), ScaleY(534));
  Result.BevelOuter := bvNone; Result.Color := PANEL;
end;
procedure BrowseClick(Sender: TObject);
var Dir: string;
begin
  Dir := DirEdit.Text;
  if BrowseForFolder(L('설치 폴더 선택', 'Choose installation folder'), Dir, False) then DirEdit.Text := Dir;
end;
procedure HelpClick(Sender: TObject);
var RC: Integer;
begin
  ShellExec('open', 'https://github.com/dhtjr1236-eng/dugout-atlas', '', '', SW_SHOW, ewNoWait, RC);
end;
procedure HideStock;
begin
  WizardForm.OuterNotebook.Hide; WizardForm.InnerNotebook.Hide;
  WizardForm.MainPanel.Hide; WizardForm.Bevel.Hide; WizardForm.BackButton.Hide;
  WizardForm.NextButton.Visible := True;
  WizardForm.NextButton.SetBounds(ScaleX(740), ScaleY(550), ScaleX(184), ScaleY(36));
  WizardForm.NextButton.BringToFront;
  WizardForm.CancelButton.SetBounds(ScaleX(616), ScaleY(550), ScaleX(108), ScaleY(36));
  WizardForm.CancelButton.BringToFront;
end;
procedure InitializeWizard;
var Hero: TBitmapImage; Heading: TNewStaticText; Browse: TNewButton;
begin
  if WizardSilent then Exit;
  Korean := ActiveLanguage = 'korean';
  WizardForm.ClientWidth := ScaleX(960); WizardForm.ClientHeight := ScaleY(600);
  WizardForm.Color := BG; WizardForm.Caption := 'Dugout Atlas {#AppVersion}';
  WizardForm.Position := poScreenCenter; HideStock;
  ExtractTemporaryFile('hero.bmp');
  Hero := TBitmapImage.Create(WizardForm); Hero.Parent := WizardForm;
  Hero.SetBounds(0, 0, ScaleX(352), ScaleY(534)); Hero.Stretch := True;
  Hero.Bitmap.LoadFromFile(ExpandConstant('{tmp}\hero.bmp')); Hero.Enabled := False;
  StepLabel := LabelAt(WizardForm, '', 24, 552, 540, 32, 10, ACCENT);
  StepLabel.Cursor := crHand; StepLabel.OnClick := @HelpClick;
  OptionsPage := NewPanel;
  Heading := LabelAt(OptionsPage, L('Dugout Atlas 설치', 'Install Dugout Atlas'), 32, 36, 544, 44, 22, INK);
  Heading.Font.Style := [fsBold];
  LabelAt(OptionsPage, L('설치 위치와 바로가기를 선택하세요.', 'Choose where to install and how to open your app.'), 32, 92, 544, 38, 11, MUTED);
  LabelAt(OptionsPage, L('설치 폴더', 'Install folder'), 32, 154, 544, 24, 11, INK);
  DirEdit := TNewEdit.Create(WizardForm); DirEdit.Parent := OptionsPage;
  DirEdit.SetBounds(ScaleX(32), ScaleY(184), ScaleX(426), ScaleY(30)); DirEdit.Text := WizardForm.DirEdit.Text;
  Browse := TNewButton.Create(WizardForm); Browse.Parent := OptionsPage;
  Browse.SetBounds(ScaleX(468), ScaleY(182), ScaleX(108), ScaleY(34));
  Browse.Caption := L('찾아보기...', 'Browse...'); Browse.OnClick := @BrowseClick;
  LabelAt(OptionsPage, L('필요한 공간: 약 {#RequiredMB} MB', 'Required space: about {#RequiredMB} MB'), 32, 228, 544, 24, 10, MUTED);
  DesktopCheck := TNewCheckBox.Create(WizardForm); DesktopCheck.Parent := OptionsPage;
  DesktopCheck.SetBounds(ScaleX(32), ScaleY(280), ScaleX(544), ScaleY(28));
  DesktopCheck.Caption := L('바탕화면에 바로가기 만들기', 'Create a desktop shortcut');
  DesktopCheck.Checked := WizardIsTaskSelected('desktopicon');
  MenuCheck := TNewCheckBox.Create(WizardForm); MenuCheck.Parent := OptionsPage;
  MenuCheck.SetBounds(ScaleX(32), ScaleY(320), ScaleX(544), ScaleY(28));
  MenuCheck.Caption := L('시작 메뉴에 바로가기 만들기', 'Create a Start Menu shortcut');
  MenuCheck.Checked := WizardIsTaskSelected('startmenuicon');
  LabelAt(OptionsPage, L('Python 설치 없이 실행할 수 있습니다.' + #13#10 + '실시간 기록을 조회하려면 인터넷 연결이 필요합니다.',
    'Python is included.' + #13#10 + 'Internet is required to retrieve live statistics.'), 32, 384, 544, 60, 11, MUTED);
  LabelAt(OptionsPage, L('설정과 즐겨찾기는 사용자 데이터 폴더에 저장됩니다.' + #13#10 + '업데이트하거나 제거해도 이 데이터는 유지합니다.',
    'Settings and favorites are stored in your user data folder.' + #13#10 + 'Updates and uninstall preserve that data.'), 32, 464, 544, 54, 10, MUTED);
  ProgressPage := NewPanel;
  Heading := LabelAt(ProgressPage, L('설치 중', 'Installing'), 32, 48, 544, 44, 22, INK); Heading.Font.Style := [fsBold];
  LabelAt(ProgressPage, L('실행 파일과 분석 도구를 준비하고 있습니다.', 'Preparing Dugout Atlas and its analysis tools.'), 32, 116, 544, 52, 11, MUTED);
  Progress := TNewProgressBar.Create(WizardForm); Progress.Parent := ProgressPage;
  Progress.SetBounds(ScaleX(32), ScaleY(204), ScaleX(544), ScaleY(14)); Progress.Min := 0; Progress.Max := 100;
  ProgressText := LabelAt(ProgressPage, '0%', 32, 240, 544, 32, 12, ACCENT);
  DonePage := NewPanel;
  Heading := LabelAt(DonePage, L('설치가 완료되었습니다', 'Ready to explore'), 32, 48, 544, 48, 22, INK); Heading.Font.Style := [fsBold];
  LabelAt(DonePage, L('Dugout Atlas에서 선수와 시즌을 탐색해 보세요.', 'Explore players and seasons with Dugout Atlas.'), 32, 120, 544, 56, 12, MUTED);
  LaunchCheck := TNewCheckBox.Create(WizardForm); LaunchCheck.Parent := DonePage;
  LaunchCheck.SetBounds(ScaleX(32), ScaleY(220), ScaleX(544), ScaleY(30));
  LaunchCheck.Caption := L('Dugout Atlas 실행', 'Launch Dugout Atlas'); LaunchCheck.Checked := True;
  LabelAt(DonePage, L('설치된 프로그램은 Windows 설정의 앱 목록에서 제거할 수 있습니다.', 'You can uninstall the app from Windows Settings.'), 32, 300, 544, 60, 11, MUTED);
end;
procedure CurPageChanged(CurPageID: Integer);
begin
  if WizardSilent then Exit;
  HideStock;
  OptionsPage.Visible := (CurPageID <> wpInstalling) and (CurPageID <> wpFinished);
  ProgressPage.Visible := CurPageID = wpInstalling; DonePage.Visible := CurPageID = wpFinished;
  if CurPageID = wpFinished then begin
    WizardForm.CancelButton.Hide; WizardForm.NextButton.Caption := L('완료', 'Finish');
    StepLabel.Caption := L('03 / 완료  ·  도움말', '03 / FINISHED  ·  Help');
  end else if CurPageID = wpInstalling then begin
    WizardForm.NextButton.Hide; StepLabel.Caption := L('02 / 파일 설치', '02 / INSTALLING');
  end else begin
    WizardForm.NextButton.Caption := L('설치', 'Install'); StepLabel.Caption := L('01 / 설치 옵션  ·  도움말', '01 / OPTIONS  ·  Help');
  end;
end;
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (not WizardSilent) and (PageID in [wpSelectDir, wpSelectProgramGroup, wpSelectTasks, wpReady]);
end;
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if WizardSilent or (CurPageID <> wpWelcome) then Exit;
  if Trim(DirEdit.Text) = '' then begin
    MsgBox(L('설치 폴더를 선택하세요.', 'Choose an installation folder.'), mbError, MB_OK); Result := False; Exit;
  end;
  WizardForm.DirEdit.Text := DirEdit.Text;
  if DesktopCheck.Checked then WizardSelectTasks('desktopicon') else WizardSelectTasks('!desktopicon');
  if MenuCheck.Checked then WizardSelectTasks('startmenuicon') else WizardSelectTasks('!startmenuicon');
end;
procedure CurInstallProgressChanged(CurProgress, MaxProgress: Integer);
var Pct: Integer;
begin
  if WizardSilent or (MaxProgress <= 0) then Exit;
  Pct := Round(CurProgress * 100.0 / MaxProgress); Progress.Position := Pct; ProgressText.Caption := IntToStr(Pct) + '%';
end;
procedure CurStepChanged(CurStep: TSetupStep);
var RC: Integer;
begin
  if (CurStep = ssDone) and not WizardSilent and not Launched then begin
    if LaunchCheck.Checked then begin
      Launched := True;
      if not Exec(ExpandConstant('{app}\DugoutAtlas.exe'), '', ExpandConstant('{app}'), SW_SHOWNORMAL, ewNoWait, RC) then
        MsgBox(L('앱을 시작하지 못했습니다. 설치 폴더의 DugoutAtlas.exe를 실행하세요.', 'Could not start the app. Open DugoutAtlas.exe from the installation folder.'), mbError, MB_OK);
    end;
  end;
end;
