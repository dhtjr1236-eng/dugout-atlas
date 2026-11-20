param(
    [switch]$Clean,
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
if ($env:OS -ne "Windows_NT") { throw "Build on Windows 11." }
$Root = Split-Path -Parent $PSScriptRoot
$BuildPath = $env:PATH
Push-Location $Root
try {
    if ($Clean) {
        foreach ($Name in @("build", "dist")) {
            $Target = Join-Path $Root $Name
            if (Test-Path $Target) {
                $Item = Get-Item $Target
                if ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                    throw "Refusing to clean a linked build directory."
                }
                Remove-Item -LiteralPath $Target -Recurse -Force
            }
        }
    }
    $Version = ((Get-Content "$Root/pyproject.toml" | Select-String '^version\s*=\s*"([\d.]+)"').Matches.Groups[1].Value)
    & $Python "$Root/tools/installer/generate_assets.py" $Version
    if ($LASTEXITCODE -ne 0) { throw "Installer asset generation failed" }
    & $Python "$Root/tools/installer/collect_licenses.py"
    if ($LASTEXITCODE -ne 0) { throw "License collection failed" }
    # The spec owns onedir, name, --add-data equivalents and collection rules.
    # No --noconfirm: existing outputs must not be silently replaced.
    # Avoid unrelated DLLs from desktop tooling (Poppler, libheif, etc.) on PATH.
    $env:PATH = (Split-Path -Parent $Python) + ";$env:SystemRoot\System32;$env:SystemRoot"
    $VersionedDist = Join-Path $Root "dist/v$Version"
    $VersionedBuild = Join-Path $Root "build/v$Version"
    & $Python -m PyInstaller --distpath $VersionedDist --workpath $VersionedBuild "$Root/tools/pyinstaller/DugoutAtlas.spec"
    $Result = $LASTEXITCODE
} catch {
    Write-Error $_ -ErrorAction Continue
    $Result = 1
} finally {
    $env:PATH = $BuildPath
    Pop-Location
}
exit $Result
