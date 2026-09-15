# Windows Build Guide — Future EPW Generator v1.0.0

## Prerequisites

For a local build machine:

- Windows 10/11 x64
- Python 3.12 x64
- Internet access for Python dependency installation
- Inno Setup 6

No special Python environment is required, though a clean virtual environment is recommended.

## Build the complete installer

From PowerShell at the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\build_installer.ps1
```

The script installs Python dependencies, runs the application tests and self-test, creates the PyInstaller onedir bundle, executes the **frozen** engine self-test, then invokes Inno Setup.

Expected output:

```text
release\FutureEPWGenerator_Setup_v1.0.0.exe
```


### Using a specific Python executable

If Python is not on PATH, pass it explicitly. For example:

```powershell
.\scripts\build_installer.ps1 -PythonExe "C:\path\to\python.exe"
```

## Build only the PyInstaller app

```powershell
.\scripts\build_windows.ps1
```

Expected outputs:

```text
dist\FutureEPWGenerator\FutureEPWGenerator.exe
dist\FutureEPWGenerator\FutureEPWEngine.exe
```

The first is the GUI. The second is the console backend runner and must remain beside the GUI executable.

## Build only the installer after an existing app build

```powershell
.\scripts\build_installer.ps1 -SkipAppBuild
```

If Inno Setup is installed in a non-standard location:

```powershell
$env:ISCC_PATH = 'D:\Tools\Inno Setup 6\ISCC.exe'
.\scripts\build_installer.ps1 -SkipAppBuild
```

## GitHub Actions

The workflow `.github/workflows/windows-release.yml` supports:

- manual `workflow_dispatch`
- automatic build on tag `v1.0.0`

A tagged build creates:

```text
FutureEPWGenerator_Setup_v1.0.0.exe
FutureEPWGenerator_Setup_v1.0.0.exe.sha256
```

and attaches both files to the GitHub Release.

## Why onedir instead of onefile

The application includes PySide6, NumPy/Pandas/Xarray/SciPy, cloud filesystem clients, Zarr, CMIP6 workflow scripts, and subprocess workers. Onedir avoids repeated extraction at launch and makes subprocess/data-file behavior more predictable for a scientific desktop application.

## Code signing

The current installer is unsigned. This does not affect the scientific calculation but Windows SmartScreen may warn users. Add Authenticode signing only after obtaining a trusted code-signing certificate.
