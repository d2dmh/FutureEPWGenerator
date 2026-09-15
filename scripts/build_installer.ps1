param(
    [switch]$SkipAppBuild,
    [string]$PythonExe = "python"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $SkipAppBuild) {
    & "$PSScriptRoot\build_windows.ps1" -PythonExe $PythonExe
}

$candidates = @(
    $env:ISCC_PATH,
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "C:\ProgramData\chocolatey\bin\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }
if (-not $candidates) {
    throw "Inno Setup 6 compiler (ISCC.exe) was not found. Install Inno Setup 6 or set ISCC_PATH."
}
$Iscc = @($candidates)[0]
New-Item -ItemType Directory -Force -Path (Join-Path $Root "release") | Out-Null
& $Iscc (Join-Path $Root "packaging\FutureEPWGenerator.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }
$Installer = Join-Path $Root "release\FutureEPWGenerator_Setup_v1.0.0.exe"
if (-not (Test-Path $Installer)) { throw "Installer output missing: $Installer" }
Write-Host "Installer ready: $Installer"


