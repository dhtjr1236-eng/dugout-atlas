param([string]$Installer = '')
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
if (-not $Installer) { $Installer = Join-Path $Root 'release/DugoutAtlas-Setup.exe' }
$Validation = Join-Path $Root 'output/installer-validation'
$InstallDir = [IO.Path]::GetFullPath((Join-Path $Validation '설치 확인/Dugout Atlas'))
$AppKey = 'HKCU:/Software/Microsoft/Windows/CurrentVersion/Uninstall/{4170AF12-1FF4-4BAA-A9C7-9D49359BB183}_is1'
if (Test-Path $AppKey) {
    $Existing = (Get-ItemProperty $AppKey).InstallLocation
    if (-not $Existing -or -not ([IO.Path]::GetFullPath($Existing).StartsWith([IO.Path]::GetFullPath($Validation), [StringComparison]::OrdinalIgnoreCase))) {
        throw 'A real Dugout Atlas installation exists. Use a clean Windows test account.'
    }
}
New-Item -ItemType Directory -Path $Validation -Force | Out-Null
function Run-Checked([string]$Exe, [string[]]$Arguments) {
    $Process = Start-Process -FilePath $Exe -ArgumentList $Arguments -WindowStyle Hidden -PassThru
    if (-not $Process.WaitForExit(120000)) {
        Stop-Process -Id $Process.Id
        throw 'Installer test timed out'
    }
    if ($Process.ExitCode -ne 0) { throw "Process failed: $Exe ($($Process.ExitCode))" }
}
$ArgsForInstall = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/TASKS=""',
    ('/DIR="' + $InstallDir + '"'), ('/LOG="' + (Join-Path $Validation 'install.log') + '"'))
Run-Checked $Installer $ArgsForInstall
$Exe = Join-Path $InstallDir 'DugoutAtlas.exe'
if (-not (Test-Path -LiteralPath $Exe)) { throw 'Missing installed executable' }
# This process sees no Python installation on PATH; frozen runtime must stand alone.
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
$Report = Join-Path $Validation 'installed/report.json'
Run-Checked $Exe @('--self-test', ('"' + $Report + '"'))
$Smoke = Get-Content -LiteralPath $Report -Raw | ConvertFrom-Json
if (-not $Smoke.ok -or -not $Smoke.frozen) { throw 'Installed application self-test failed' }
$UserData = Join-Path $Validation 'installed/isolated-runtime/Dugout Atlas/data'
$Sentinel = Join-Path $UserData 'favorites.json'
[IO.File]::WriteAllText($Sentinel, '{"installer_validation":true}')
$Database = Join-Path $UserData 'mlb_advanced_gameday.sqlite3'
$Before = @{}
foreach ($File in @($Sentinel, $Database)) { $Before[$File] = (Get-FileHash -LiteralPath $File).Hash }
Run-Checked $Installer $ArgsForInstall
foreach ($File in $Before.Keys) {
    if ((Get-FileHash -LiteralPath $File).Hash -ne $Before[$File]) { throw 'Upgrade changed user data' }
}
Run-Checked $Exe @('--self-test', ('"' + (Join-Path $Validation 'upgraded/report.json') + '"'))
$Uninstaller = Join-Path $InstallDir 'unins000.exe'
$ResolvedInstall = [IO.Path]::GetFullPath($InstallDir)
if (-not $ResolvedInstall.StartsWith([IO.Path]::GetFullPath($Validation) + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Refusing to uninstall outside validation directory'
}
Run-Checked $Uninstaller @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG="' + (Join-Path $Validation 'uninstall.log') + '"'))
if (Test-Path -LiteralPath $Exe) { throw 'Uninstall did not remove the program' }
foreach ($File in $Before.Keys) {
    if ((Get-FileHash -LiteralPath $File).Hash -ne $Before[$File]) { throw 'Uninstall changed user data' }
}
$Result = @{ok=$true; version=$Smoke.version; checks=@('silent install','Korean and space path','no Python on PATH',
    'frozen app self-test','upgrade preserves SQLite and favorites','upgraded app starts','uninstall preserves user data')}
$Result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Validation 'installer-result.json') -Encoding UTF8
Write-Output 'Installer lifecycle checks passed.'
