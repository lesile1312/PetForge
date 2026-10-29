[CmdletBinding()]
param(
    [ValidateSet('auto', 'cpu', 'cuda')]
    [string]$Device = 'auto',
    [switch]$InstallRuntime,
    [switch]$Dev
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$workerRoot = Join-Path $repoRoot 'services\worker'
$venvPath = Join-Path $workerRoot '.venv'
$venvPython = Join-Path $venvPath 'Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    $pythonPath = $null
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvCommand) {
        $pythonPath = (& uv python find 3.12).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $pythonPath) {
            throw 'uv could not find Python 3.12. Install Python 3.12 or configure uv.'
        }
    } else {
        $pythonPath = (& py -3.12 -c 'import sys; print(sys.executable)' 2>$null | Select-Object -Last 1)
        if ($LASTEXITCODE -ne 0 -or -not $pythonPath) {
            throw 'Python 3.12 is required. Install CPython 3.12 or Astral uv.'
        }
        $pythonPath = $pythonPath.Trim()
    }
    & $pythonPath -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated worker environment.' }
}

$version = & $venvPython --version
if ($LASTEXITCODE -ne 0 -or $version.Trim() -notmatch '^Python 3\.12(?:\.|$)') {
    throw "Worker environment must use Python 3.12; found $version. Remove only services/worker/.venv and rerun this script."
}

& $venvPython -m pip install -e $workerRoot -r (Join-Path $workerRoot 'requirements-p0.txt')
if ($LASTEXITCODE -ne 0) { throw 'Worker base dependencies did not install.' }
if ($Dev) {
    & $venvPython -m pip install -r (Join-Path $workerRoot 'requirements-p0-dev.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Worker development dependencies did not install.' }
}

if ($InstallRuntime) {
    $selectedDevice = $Device
    if ($selectedDevice -eq 'auto') {
        & nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Out-Null
        $selectedDevice = if ($LASTEXITCODE -eq 0) { 'cuda' } else { 'cpu' }
    }
    $cacheRoot = 'E:\PetForge\cache'
    New-Item -ItemType Directory -Force -Path $cacheRoot | Out-Null
    $env:PIP_CACHE_DIR = Join-Path $cacheRoot 'pip'
    if ($selectedDevice -eq 'cuda') {
        $torchIndex = 'https://download.pytorch.org/whl/cu130'
        $torchVersion = '2.14.1+cu130'
        $visionVersion = '0.29.1+cu130'
    } else {
        $torchIndex = 'https://download.pytorch.org/whl/cpu'
        $torchVersion = '2.14.1+cpu'
        $visionVersion = '0.29.1+cpu'
    }
    & $venvPython -m pip install --index-url $torchIndex "torch==$torchVersion" "torchvision==$visionVersion"
    if ($LASTEXITCODE -ne 0) { throw "PyTorch $selectedDevice wheels did not install." }
    & $venvPython -m pip install -r (Join-Path $workerRoot 'requirements-photo-runtime.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Photo inference runtime did not install.' }
    $runtime = & $venvPython -c 'import torch; print(torch.__version__); print(torch.cuda.is_available())'
    if ($LASTEXITCODE -ne 0) { throw 'Could not verify the photo inference runtime.' }
    if ($selectedDevice -eq 'cuda' -and $runtime[1].Trim() -ne 'True') {
        throw 'CUDA runtime installed, but PyTorch cannot access the NVIDIA GPU.'
    }
    Write-Host "Photo runtime ready: mode $selectedDevice, Torch $($runtime[0]), CUDA available $($runtime[1])."
} else {
    Write-Host 'Photo runtime packages remain uninstalled. Add -InstallRuntime to install CPU or CUDA dependencies.'
}

Write-Host "Worker environment ready: $($version.Trim()), requested device mode $Device."
Write-Host 'Model weights remain uninstalled until scripts/install-photo-models.ps1 verifies licenses, sizes, and hashes.'
