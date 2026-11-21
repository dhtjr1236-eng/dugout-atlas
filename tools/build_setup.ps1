param(
    [string]$Python = "",
    [string]$Iscc = "",
    [switch]$SkipAppBuild
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $Root '.venv/Scripts/python.exe' }
if (-not $Iscc) { $Iscc = Join-Path $Root '.build-tools/InnoSetup/ISCC.exe' }
if (-not (Test-Path -LiteralPath $Iscc)) { throw 'Inno Setup 6.6+ required. Supply -Iscc with the compiler path.' }
$Version = ((Get-Content (Join-Path $Root 'pyproject.toml') | Select-String '^version\s*=\s*"([\d.]+)"').Matches.Groups[1].Value)
if (-not $Version) { throw 'Missing project version' }
& $Python (Join-Path $Root 'tools/installer/generate_assets.py') $Version
if ($LASTEXITCODE -ne 0) { throw 'Artwork generation failed' }
if (-not $SkipAppBuild) {
    & (Join-Path $Root 'tools/build_windows.ps1') -Python $Python
    if ($LASTEXITCODE -ne 0) { throw 'App build failed' }
}
$Payload = Join-Path $Root "dist/v$Version/DugoutAtlas"
if (-not (Test-Path (Join-Path $Payload 'DugoutAtlas.exe'))) { throw 'Missing app payload' }
$Release = Join-Path $Root 'release'
New-Item -ItemType Directory -Path $Release -Force | Out-Null
$Size = (Get-ChildItem -LiteralPath $Payload -Recurse -File | Measure-Object Length -Sum).Sum
$Required = [Math]::Ceiling($Size / 1MB * 1.15)
$Lines = @(
    ('#define AppVersion "' + $Version + '"'),
    ('#define RequiredMB "' + $Required + '"'),
    ('#define PayloadDir "' + $Payload + '"'),
    ('#define ReleaseDir "' + $Release + '"')
)
[IO.File]::WriteAllLines((Join-Path $Root 'tools/installer/installer/product.inc'), $Lines, [Text.UTF8Encoding]::new($true))
& $Iscc (Join-Path $Root 'tools/installer/installer/dugout.iss')
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
$Setup = Get-Item (Join-Path $Release "DugoutAtlas-v$Version-Setup.exe")
if ($Setup.Length -ge 2GB) { throw 'Installer exceeds GitHub Release asset limit' }
& $Python (Join-Path $Root 'tools/installer/make_source_archive.py')
if ($LASTEXITCODE -ne 0) { throw 'Source archive creation failed' }
$Sums = @($Setup, (Get-Item (Join-Path $Release "DugoutAtlas-v$Version-source.zip"))) | ForEach-Object {
    $Hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
    $Hash.Hash.ToLower() + '  ' + $_.Name
}
[IO.File]::WriteAllLines((Join-Path $Release "DugoutAtlas-v$Version-SHA256SUMS.txt"), $Sums)
Write-Output ('Installer: ' + $Setup.FullName)
Write-Output ('Size: ' + [Math]::Round($Setup.Length / 1MB, 2) + ' MiB')
