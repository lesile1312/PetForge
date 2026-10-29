[CmdletBinding()]
param(
    [ValidateSet('auto', 'cpu', 'cuda')]
    [string]$Device = 'auto',
    [string]$ModelRoot = 'E:\PetForge\models',
    [switch]$SkipRuntimeSetup
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$manifestPath = Join-Path $repoRoot 'models\manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.schema_version -ne 2) { throw 'Unsupported model manifest schema.' }
$model = @($manifest.models | Where-Object { $_.id -eq $manifest.active_model_id }) | Select-Object -First 1
if (-not $model) { throw 'Active photo model is missing from the manifest.' }

$resolvedModelRoot = [System.IO.Path]::GetFullPath($ModelRoot)
New-Item -ItemType Directory -Force -Path $resolvedModelRoot | Out-Null
$driveRoot = [System.IO.Path]::GetPathRoot($resolvedModelRoot)
$availableBytes = [System.IO.DriveInfo]::new($driveRoot).AvailableFreeSpace
$files = @()
$downloadBytes = [int64]0

Write-Host "Model stack: $($model.id) ($($model.revision))"
foreach ($component in $model.components) {
    Write-Host ""
    Write-Host "Component: $($component.id)"
    Write-Host "  Revision: $($component.revision)"
    Write-Host "  Source: $($component.source_url)"
    $licenseLabel = $component.license.spdx_id
    if (-not $licenseLabel) { $licenseLabel = $component.license.license_name }
    Write-Host "  License: $licenseLabel"
    Write-Host "  License terms: $($component.license.terms_url)"
    if ($component.license.notice) { Write-Host "  Notice: $($component.license.notice)" }
    foreach ($file in $component.files) {
        $destination = [System.IO.Path]::GetFullPath((Join-Path $resolvedModelRoot $file.path))
        if (-not $destination.StartsWith($resolvedModelRoot.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Unsafe model file path in manifest.'
        }
        $files += [pscustomobject]@{ Component = $component; Entry = $file; Destination = $destination }
        if (-not (Test-Path -LiteralPath $destination -PathType Leaf)) {
            $downloadBytes += [int64]$file.size_bytes
        }
        Write-Host ("  {0}  {1:N0} bytes" -f $file.path, [int64]$file.size_bytes)
    }
}

$requiredBytes = $downloadBytes + 8GB
Write-Host ""
Write-Host "Destination: $resolvedModelRoot"
Write-Host ("Model bytes to download: {0:N0}" -f $downloadBytes)
Write-Host ("Free bytes: {0:N0}" -f $availableBytes)
Write-Host ("Required free space including 8 GiB runtime/cache reserve: {0:N0}" -f $requiredBytes)
if ($availableBytes -lt $requiredBytes) { throw 'Not enough free space for the local model and runtime.' }

if (-not $SkipRuntimeSetup) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'setup-photo-worker.ps1') -Device $Device -InstallRuntime
    if ($LASTEXITCODE -ne 0) { throw 'Photo worker runtime setup failed.' }
}

$receipt = [System.Collections.Generic.List[object]]::new()
foreach ($item in $files) {
    $entry = $item.Entry
    $destination = $item.Destination
    $partial = "$destination.partial"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null

    if (Test-Path -LiteralPath $destination -PathType Leaf) {
        $existing = Get-Item -LiteralPath $destination
        if ([int64]$existing.Length -ne [int64]$entry.size_bytes) {
            throw "Existing model file has wrong size; preserved at $destination"
        }
        $sha = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($entry.sha256 -and $sha -ne $entry.sha256.ToLowerInvariant()) {
            throw "Existing model file has wrong SHA-256; preserved at $destination"
        }
        if ($entry.md5 -and (Get-FileHash -LiteralPath $destination -Algorithm MD5).Hash.ToLowerInvariant() -ne $entry.md5.ToLowerInvariant()) {
            throw "Existing model file has wrong upstream MD5; preserved at $destination"
        }
        $receipt.Add([pscustomobject]@{ path = $entry.path; size_bytes = $existing.Length; sha256 = $sha })
        continue
    }

    $partialReady = $false
    if (Test-Path -LiteralPath $partial -PathType Leaf) {
        $partialSize = [int64](Get-Item -LiteralPath $partial).Length
        if ($partialSize -gt [int64]$entry.size_bytes) {
            throw "Resume file exceeds expected size; preserved at $partial"
        }
        $partialReady = $partialSize -eq [int64]$entry.size_bytes
    }
    if (-not $partialReady) {
        Write-Host "Downloading $($entry.path)"
        & curl.exe --fail --location --retry 3 --retry-delay 2 --continue-at - --output $partial $entry.download_url
        if ($LASTEXITCODE -ne 0) { throw "Download failed; resumable file remains at $partial" }
    } else {
        Write-Host "Verifying complete resume file $($entry.path)"
    }

    $downloaded = Get-Item -LiteralPath $partial
    if ([int64]$downloaded.Length -ne [int64]$entry.size_bytes) {
        throw "Downloaded size mismatch; file remains at $partial"
    }
    $sha = (Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($entry.sha256 -and $sha -ne $entry.sha256.ToLowerInvariant()) {
        throw "Downloaded SHA-256 mismatch; file remains at $partial"
    }
    if ($entry.md5 -and (Get-FileHash -LiteralPath $partial -Algorithm MD5).Hash.ToLowerInvariant() -ne $entry.md5.ToLowerInvariant()) {
        throw "Downloaded upstream MD5 mismatch; file remains at $partial"
    }
    Move-Item -LiteralPath $partial -Destination $destination
    $receipt.Add([pscustomobject]@{ path = $entry.path; size_bytes = $downloaded.Length; sha256 = $sha })
}

$receiptPath = Join-Path $resolvedModelRoot 'manifest-receipt.json'
$receiptJson = [pscustomobject]@{
    schema_version = 1
    model_id = $model.id
    model_revision = $model.revision
    installed_at = [DateTimeOffset]::UtcNow.ToString('O')
    files = @($receipt)
} | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($receiptPath, $receiptJson + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

$workerPython = Join-Path $repoRoot 'services\worker\.venv\Scripts\python.exe'
& $workerPython -m petforge_worker.cli check-models --model-root $resolvedModelRoot
if ($LASTEXITCODE -ne 0) { throw 'Model files did not pass the local manifest check.' }
Write-Host "Models ready. SHA-256 receipt: $receiptPath"
