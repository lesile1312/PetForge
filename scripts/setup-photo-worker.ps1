[CmdletBinding()]
param(
    [ValidateSet('auto', 'cpu', 'cuda')]
    [string]$Device = 'auto',
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

Write-Host "Worker environment ready: $($version.Trim()), requested device mode $Device."
Write-Host 'Model-specific Torch/CUDA wheels and weights remain uninstalled until the P0 model/license choice.'

