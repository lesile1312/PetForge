[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Root,
    [ValidateSet('auto', 'cpu', 'cuda')]
    [string]$Device = 'auto',
    [string]$ModelRoot = 'E:\PetForge\models',
    [string]$Output
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$workerPython = Join-Path $repoRoot 'services\worker\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $workerPython -PathType Leaf)) {
    throw 'Run scripts/setup-photo-worker.ps1 before the benchmark.'
}
if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    throw 'Evaluation corpus folder does not exist.'
}

$arguments = @('-m', 'petforge_worker.cli', 'benchmark', '--root', (Resolve-Path $Root).Path, '--device', $Device, '--model-root', $ModelRoot)
if ($Output) { $arguments += @('--output', $Output) }
& $workerPython @arguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
