# Explicit installation using the external venv; existing environments/data stay intact.
param([switch]$Wake, [switch]$AllExtras)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$JarvisVenv = Join-Path $env:LOCALAPPDATA 'Jarvis\venv312'
$JarvisPython = Join-Path $JarvisVenv 'Scripts\python.exe'
if (-not (Test-Path $JarvisPython)) {
    if (Test-Path $JarvisVenv) { throw 'External venv folder exists but Python is missing. Preserve it and repair/select the environment manually.' }
    py -3.12 -m venv $JarvisVenv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 venv creation failed.' }
}
& $JarvisPython -c "import sys; assert sys.version_info[:2] == (3,12), 'Python 3.12 required'; assert sys.prefix != sys.base_prefix, 'Virtual environment required'"
if ($LASTEXITCODE -ne 0) { throw 'External virtual environment validation failed.' }
$JarvisExtras = @('windows')
if ($Wake) { $JarvisExtras += 'wake' }
if ($AllExtras) { $JarvisExtras += @('browser','documents','dashboard','media','wake') }
& $JarvisPython setup.py --extras $JarvisExtras
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Review the original pip error; do not delete your environments.' }
Write-Host 'Dependencies installed. Run RUN_WINDOWS.ps1; verify actual hardware/account readiness in the HUD.'
