$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$cacheRoot = if (Test-Path -LiteralPath "E:\") { "E:\Caches\PetForge" } else { Join-Path $projectRoot ".tools\ai-cache" }
$triposrEnvironment = Join-Path $cacheRoot "triposr-venv"
$triposrModelDirectory = Join-Path $cacheRoot "triposr-model"
$huggingFaceCache = Join-Path $cacheRoot "huggingface"
$rembgCache = Join-Path $cacheRoot "rembg"
$repo = Join-Path $projectRoot ".tools\TripoSR"
$apiPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$triposrPython = Join-Path $triposrEnvironment "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $apiPython)) {
    throw "PetForge's API environment is missing. Run scripts/setup.ps1 first."
}
New-Item -ItemType Directory -Force -Path $cacheRoot, $huggingFaceCache, $rembgCache | Out-Null
$env:PIP_CACHE_DIR = Join-Path $cacheRoot "pip-cache"
$env:HF_HOME = $huggingFaceCache
$env:REMBG_HOME = $rembgCache

if (-not (Test-Path -LiteralPath (Join-Path $repo "run.py"))) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $repo) | Out-Null
    git clone --depth 1 https://github.com/VAST-AI-Research/TripoSR.git $repo
    if ($LASTEXITCODE -ne 0) { throw "Could not clone the official VAST-AI-Research/TripoSR repository." }
}

& $apiPython -m pip install -r services/api/requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Could not install PetForge's local background-removal dependencies." }

if (-not (Test-Path -LiteralPath $triposrPython)) {
    & $apiPython -m venv $triposrEnvironment
    if ($LASTEXITCODE -ne 0) { throw "Could not create the TripoSR environment from PetForge's Python 3.12 API environment." }
}

& $triposrPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw "Could not prepare pip for the TripoSR environment." }
$wheelhouse = Join-Path $cacheRoot "wheelhouse"
New-Item -ItemType Directory -Force -Path $wheelhouse | Out-Null
$torchWheel = Join-Path $wheelhouse "torch-2.2.2+cu121-cp312-cp312-win_amd64.whl"
$torchvisionWheel = Join-Path $wheelhouse "torchvision-0.17.2+cu121-cp312-cp312-win_amd64.whl"
if (-not (Test-Path -LiteralPath $torchWheel) -or (Get-Item -LiteralPath $torchWheel).Length -ne 2454764288) {
    Invoke-WebRequest -Uri "https://download.pytorch.org/whl/cu121/torch-2.2.2%2Bcu121-cp312-cp312-win_amd64.whl" -OutFile $torchWheel -TimeoutSec 1200 -UseBasicParsing
}
if (-not (Test-Path -LiteralPath $torchvisionWheel) -or (Get-Item -LiteralPath $torchvisionWheel).Length -ne 5659975) {
    Invoke-WebRequest -Uri "https://download.pytorch.org/whl/cu121/torchvision-0.17.2%2Bcu121-cp312-cp312-win_amd64.whl" -OutFile $torchvisionWheel -TimeoutSec 1200 -UseBasicParsing
}
if ((Get-Item -LiteralPath $torchWheel).Length -ne 2454764288 -or (Get-Item -LiteralPath $torchvisionWheel).Length -ne 5659975) {
    throw "The official CUDA 12.1 PyTorch wheel download was incomplete. Rerun this script to resume setup."
}
& $triposrPython -m pip install $torchWheel $torchvisionWheel
if ($LASTEXITCODE -ne 0) { throw "Could not install the CUDA 12.1 PyTorch wheels for TripoSR." }
& $triposrPython -m pip install "numpy<2"
if ($LASTEXITCODE -ne 0) { throw "Could not install a NumPy version compatible with the selected PyTorch release." }

$requirementsFile = Join-Path $repo "requirements.txt"
# The CLI uses pre-cutout input, so omit upstream Gradio/FFmpeg/rembg extras and its Windows-incompatible tokenizer pin.
$portableRequirements = @(
    Get-Content -LiteralPath $requirementsFile |
        Where-Object { $_ -notmatch "torchmcubes|^rembg$|^gradio$|^imageio\[ffmpeg\]$" } |
        ForEach-Object {
            if ($_ -eq "transformers==4.35.0") { "transformers==4.46.3" }
            elseif ($_ -eq "huggingface-hub") { "huggingface-hub<1.0" }
            else { $_ }
        }
)
$portableRequirements += "imageio"
& $triposrPython -m pip install $portableRequirements
if ($LASTEXITCODE -ne 0) { throw "Could not install the official TripoSR Python dependencies." }
& $triposrPython -m pip uninstall -y rembg onnxruntime scikit-image pymatting numba llvmlite tifffile
if ($LASTEXITCODE -ne 0) { throw "Could not remove unused segmentation dependencies from TripoSR's dedicated environment." }
& $triposrPython -m pip install "numpy<2" "scipy<1.16" PyMCubes
if ($LASTEXITCODE -ne 0) { throw "Could not install the Windows-compatible mesh extraction fallback." }
& $triposrPython (Join-Path $projectRoot "scripts\patch-triposr-windows.py")
if ($LASTEXITCODE -ne 0) { throw "Could not prepare TripoSR's Windows mesh extraction fallback." }

$segmentationDirectory = Join-Path $rembgCache "models\birefnet-portrait"
$segmentationModel = Join-Path $segmentationDirectory "birefnet-portrait.onnx"
New-Item -ItemType Directory -Force -Path $segmentationDirectory | Out-Null
if (-not (Test-Path -LiteralPath $segmentationModel) -or (Get-Item -LiteralPath $segmentationModel).Length -ne 972666916) {
    & curl.exe --fail --location --continue-at - --retry 5 --retry-delay 2 --connect-timeout 30 --output $segmentationModel "https://github.com/danielgatis/rembg/releases/download/v0.0.0/BiRefNet-portrait-epoch_150.onnx"
    if ($LASTEXITCODE -ne 0) { throw "Could not download the local BiRefNet portrait weights. Rerun this script to resume." }
}
$segmentationHash = (Get-FileHash -LiteralPath $segmentationModel -Algorithm MD5).Hash.ToLowerInvariant()
if ((Get-Item -LiteralPath $segmentationModel).Length -ne 972666916 -or $segmentationHash -ne "c3a64a6abf20250d090cd055f12a3b67") {
    throw "The BiRefNet portrait model failed its size or checksum validation."
}

$triposrRevision = "5b521936b01fbe1890f6f9baed0254ab6351c04a"
$triposrCheckpoint = Join-Path $triposrModelDirectory "model.ckpt"
$triposrConfig = Join-Path $triposrModelDirectory "config.yaml"
New-Item -ItemType Directory -Force -Path $triposrModelDirectory | Out-Null
if (-not (Test-Path -LiteralPath $triposrConfig)) {
    & curl.exe --fail --location --retry 5 --retry-delay 2 --connect-timeout 30 --output $triposrConfig "https://huggingface.co/stabilityai/TripoSR/resolve/$triposrRevision/config.yaml?download=true"
    if ($LASTEXITCODE -ne 0) { throw "Could not download the TripoSR model configuration." }
}
if (-not (Test-Path -LiteralPath $triposrCheckpoint) -or (Get-Item -LiteralPath $triposrCheckpoint).Length -ne 1677246742) {
    & curl.exe --fail --location --continue-at - --retry 5 --retry-delay 2 --connect-timeout 30 --output $triposrCheckpoint "https://huggingface.co/stabilityai/TripoSR/resolve/$triposrRevision/model.ckpt?download=true"
    if ($LASTEXITCODE -ne 0) { throw "Could not download the TripoSR checkpoint. Rerun this script to resume the download." }
}
if ((Get-Item -LiteralPath $triposrCheckpoint).Length -ne 1677246742) {
    throw "The TripoSR checkpoint size is invalid. Rerun scripts/setup-ai.ps1 to resume or repair it."
}

$envFile = Join-Path $projectRoot ".env"
$lines = if (Test-Path -LiteralPath $envFile) { @(Get-Content -LiteralPath $envFile) } else { @() }
$updates = [ordered]@{
    BACKGROUND_REMOVAL_PROVIDER = "rembg"
    PETFORGE_3D_PROVIDER = "triposr"
    PETFORGE_TRIPOSR_REPO = ".tools/TripoSR"
    PETFORGE_TRIPOSR_MODEL = $triposrModelDirectory.Replace("\", "/")
    PETFORGE_TRIPOSR_PYTHON = $triposrPython.Replace("\", "/")
    PETFORGE_TRIPOSR_TIMEOUT_SECONDS = "1200"
    HF_HOME = $huggingFaceCache.Replace("\", "/")
    REMBG_HOME = $rembgCache.Replace("\", "/")
}
foreach ($entry in $updates.GetEnumerator()) {
    $found = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match "^\s*$([regex]::Escape($entry.Key))=") {
            $lines[$index] = "$($entry.Key)=$($entry.Value)"
            $found = $true
            break
        }
    }
    if (-not $found) { $lines += "$($entry.Key)=$($entry.Value)" }
}
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($envFile, (($lines -join "`n") + "`n"), $utf8NoBom)

& $apiPython -c "import rembg; print('rembg import: OK')"
if ($LASTEXITCODE -ne 0) { throw "The local segmentation runtime did not import successfully." }
Push-Location $repo
try {
    & $triposrPython -c "import torch, tsr, mcubes; print('TripoSR imports: OK'); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU fallback')"
    $triposrImportExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($triposrImportExitCode -ne 0) { throw "The TripoSR runtime did not import successfully." }
if ($LASTEXITCODE -ne 0) { throw "The TripoSR runtime did not import successfully." }

Write-Host "Local AI dependencies are ready. Restart PetForge with pnpm dev."
Write-Host "TripoSR weights are cached at $triposrModelDirectory."
