param(
    [switch]$Clean,
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
if ($env:OS -ne "Windows_NT") { throw "Build on Windows 11." }
$Root = Split-Path -Parent $PSScriptRoot
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
    # The spec owns onedir, name, --add-data equivalents and collection rules.
    # No --noconfirm: existing outputs must not be silently replaced.
    & $Python -m PyInstaller --distpath "$Root/dist" --workpath "$Root/build" "$Root/tools/pyinstaller/DugoutAtlas.spec"
    $Result = $LASTEXITCODE
} catch {
    Write-Error $_ -ErrorAction Continue
    $Result = 1
} finally {
    Pop-Location
}
exit $Result
