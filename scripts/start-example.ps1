param([string]$GodotExecutable = $env:PETFORGE_GODOT_EXECUTABLE)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $GodotExecutable -or -not (Test-Path -LiteralPath $GodotExecutable -PathType Leaf)) {
    throw 'Pass -GodotExecutable with the path to Godot 4, or set PETFORGE_GODOT_EXECUTABLE.'
}
$project = Join-Path $root 'apps\desktop'
$pet = Join-Path $root 'examples\creator-pet'
Start-Process -FilePath $GodotExecutable -ArgumentList @('--path', ('"{0}"' -f $project), '--', '--pet-project', ('"{0}"' -f $pet)) -WorkingDirectory $project -WindowStyle Hidden
