param(
    [string]$Godot = $env:PETFORGE_GODOT_EXECUTABLE,
    [string]$Output = "dist\windows\PetForge.exe"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $projectRoot

if (-not $Godot -or -not (Test-Path -LiteralPath $Godot -PathType Leaf)) {
    throw "Set PETFORGE_GODOT_EXECUTABLE to a Godot 4 executable, or pass -Godot <path>."
}

$absoluteOutput = Join-Path $projectRoot $Output
$outputDirectory = Split-Path -Parent $absoluteOutput
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
& $Godot --headless --path "apps\desktop" --export-release "Windows Desktop" $absoluteOutput
if ($LASTEXITCODE -ne 0) {
    throw "Godot export failed. Check that Windows export templates are installed."
}
if (-not (Test-Path -LiteralPath $absoluteOutput -PathType Leaf)) {
    throw "Godot returned without producing the runtime executable."
}
Write-Host "Exported PetForge Runtime: $absoluteOutput"
