# Launch with the known external venv; no activation policy changes.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$JarvisPython = Join-Path $env:LOCALAPPDATA 'Jarvis\venv312\Scripts\python.exe'
if (-not (Test-Path $JarvisPython)) { throw 'External venv Python missing. Run INSTALL_WINDOWS.ps1 or follow WINDOWS_SETUP.md.' }
& $JarvisPython main.py
exit $LASTEXITCODE
