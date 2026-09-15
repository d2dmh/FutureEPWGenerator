@echo off
setlocal
cd /d "%~dp0"
echo Building Future EPW Generator v1.0.0 installer...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_installer.ps1"
if errorlevel 1 (
  echo.
  echo Build failed. See the messages above.
  pause
  exit /b 1
)
echo.
echo Installer created under release\FutureEPWGenerator_Setup_v1.0.0.exe
pause
