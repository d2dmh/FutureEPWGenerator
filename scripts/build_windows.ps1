param(
    [switch]$SkipInstall,
    [string]$PythonExe = "python"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== Future EPW Generator v1.0.0 Windows build =="
if (-not $SkipInstall) {
    & $PythonExe -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed with exit code $LASTEXITCODE" }
    & $PythonExe -m pip install -r requirements.txt -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed with exit code $LASTEXITCODE" }
}

& $PythonExe app.py --self-test
if ($LASTEXITCODE -ne 0) { throw "Application self-test failed with exit code $LASTEXITCODE" }
& $PythonExe -m pytest -q tests
if ($LASTEXITCODE -ne 0) { throw "Application tests failed with exit code $LASTEXITCODE" }

Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
& $PythonExe -m PyInstaller --noconfirm --clean packaging\FutureEPWGenerator.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$Exe = Join-Path $Root "dist\FutureEPWGenerator\FutureEPWGenerator.exe"
$EngineExe = Join-Path $Root "dist\FutureEPWGenerator\FutureEPWEngine.exe"
if (-not (Test-Path $Exe)) { throw "PyInstaller GUI output missing: $Exe" }
if (-not (Test-Path $EngineExe)) { throw "PyInstaller engine output missing: $EngineExe" }

# Conda Python may link pyexpat.pyd against an external Expat runtime in
# <env>\Library\bin. PyInstaller does not always discover that dependency.
# If the build interpreter has such a DLL, require the frozen onedir bundle to
# contain it before attempting the engine self-test.
$SourceExpat = (& $PythonExe -c "import sys,pathlib; roots=[pathlib.Path(sys.prefix)/'Library'/'bin',pathlib.Path(sys.prefix)/'DLLs',pathlib.Path(sys.prefix)]; hits=[str(p) for r in roots if r.is_dir() for p in r.glob('*expat*.dll')]; print(hits[0] if hits else '')").Trim()
if ($LASTEXITCODE -ne 0) { throw "Could not inspect Python Expat runtime dependencies (exit code $LASTEXITCODE)" }
if ($SourceExpat) {
    Write-Host "Build interpreter uses external Expat runtime: $SourceExpat"
    $BundledExpat = Get-ChildItem -Path (Join-Path $Root "dist\FutureEPWGenerator") -Recurse -File -Filter "*expat*.dll" -ErrorAction SilentlyContinue
    if (-not $BundledExpat) {
        throw "Bundled Expat runtime DLL missing. PyInstaller must include the Conda *expat*.dll required by pyexpat.pyd."
    }
    Write-Host "Bundled Expat runtime: $($BundledExpat[0].FullName)"
}

Write-Host "Running frozen engine self-test..."
& $EngineExe --self-test
if ($LASTEXITCODE -ne 0) { throw "Frozen self-test failed with exit code $LASTEXITCODE" }
Write-Host "Windows onedir build ready: $Exe"
