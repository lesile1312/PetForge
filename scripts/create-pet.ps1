param(
    [Parameter(Mandatory = $true)][string]$ImagePath,
    [string]$Name = "My Pet",
    [string]$OutputDirectory,
    [string]$GodotExecutable = $env:PETFORGE_GODOT_EXECUTABLE,
    [switch]$NoLaunch
)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$source = (Resolve-Path -LiteralPath $ImagePath).Path
if ([IO.Path]::GetExtension($source) -ine ".png") { throw "Use a transparent PNG image. / Please export your character as PNG first." }
if ((Get-Item -LiteralPath $source).Length -gt 10MB) { throw "PNG must be smaller than 10 MB." }
$bytes = [IO.File]::ReadAllBytes($source)
if ($bytes.Length -lt 24 -or [BitConverter]::ToString($bytes[0..7]) -ne '89-50-4E-47-0D-0A-1A-0A') { throw "Invalid PNG file." }
if (-not $NoLaunch) {
    if (-not $GodotExecutable -or -not (Test-Path -LiteralPath $GodotExecutable -PathType Leaf)) {
        throw "Pass -GodotExecutable with your Godot 4 executable path, or use -NoLaunch to create the package only."
    }
    $godotPath = (Resolve-Path -LiteralPath $GodotExecutable).Path
}
$id = "pet_" + [Guid]::NewGuid().ToString("N")
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $projectRoot "storage\custom-pets\$id" }
$target = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $target) { throw "Output directory already exists. Choose a new directory; existing files will not be overwritten." }
$config = Get-Content -LiteralPath (Join-Path $projectRoot "apps\desktop\assets\default-pet\pet.json") -Raw | ConvertFrom-Json
$config.id = $id
$config.name = $Name
$null = New-Item -ItemType Directory -Path $target
Copy-Item -LiteralPath $source -Destination (Join-Path $target "character.png")
$json = $config | ConvertTo-Json -Depth 20
[IO.File]::WriteAllText((Join-Path $target "pet.json"), $json, (New-Object Text.UTF8Encoding $false))
Write-Host "Pet package created: $target"
Write-Output $target
if (-not $NoLaunch) {
    $desktopProject = Join-Path $projectRoot "apps\desktop"
    $arguments = @('--path', ('"{0}"' -f $desktopProject), '--', '--pet-project', ('"{0}"' -f $target))
    $petProcess = Start-Process -FilePath $godotPath -ArgumentList $arguments -PassThru -WindowStyle Normal
    Write-Host "Desktop pet started (process $($petProcess.Id)). Focus the pet and press Esc to exit."
}
