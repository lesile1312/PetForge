$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    $python312 = $null
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        foreach ($line in (& $launcher.Source -0p 2>$null)) {
            if ($line -match '^\s*-V:[^\s]*3\.12[^\s]*\s+(?<path>.+)$') {
                $python312 = $Matches.path.Trim()
                break
            }
        }
    }
    if ($python312 -and (Test-Path -LiteralPath $python312)) {
        & $python312 -m venv .venv
    } elseif ($launcher) {
        & $launcher.Source -3.12 -m venv .venv
    } else {
        $python = Get-Command python.exe -ErrorAction SilentlyContinue
        $pythonVersion = if ($python) { (& $python.Source --version 2>&1 | Out-String).Trim() } else { "" }
        if ($python -and $pythonVersion -match '^Python 3\.12\.') {
            & $python.Source -m venv .venv
        } else {
            throw "Python 3.12 was not found. Install Python 3.12, then rerun scripts/setup.ps1."
        }
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
        throw "Could not create the API environment with Python 3.12."
    }
}

pnpm install
& ".venv\Scripts\python.exe" -m pip install -r services/api/requirements.txt
if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item .env.example .env
}

Write-Host "PetForge dependencies are ready. Start the app with: pnpm dev"
