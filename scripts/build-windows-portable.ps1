param(
    [Parameter(Mandatory = $true)][string]$GodotExecutable,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $GodotExecutable -PathType Leaf)) { throw 'Godot executable not found.' }
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Output directory already exists; choose a new one.' }
$output = New-Item -ItemType Directory -Path $OutputDirectory
$runtime = New-Item -ItemType Directory -Path (Join-Path $output.FullName 'PetForgeRuntime')
foreach ($item in @('project.godot', 'assets', 'scenes', 'scripts', 'shaders')) {
    Copy-Item -LiteralPath (Join-Path $root "apps\desktop\$item") -Destination $runtime.FullName -Recurse
}
Copy-Item -LiteralPath (Join-Path $root 'examples\creator-pet') -Destination (Join-Path $output.FullName 'pet') -Recurse
Copy-Item -LiteralPath $GodotExecutable -Destination (Join-Path $output.FullName 'PetForge.exe')
Copy-Item -LiteralPath (Join-Path $root 'LICENSE') -Destination (Join-Path $output.FullName 'LICENSE-PetForge.txt')
Copy-Item -LiteralPath (Join-Path $root 'THIRD_PARTY_NOTICES.md') -Destination (Join-Path $output.FullName 'THIRD_PARTY_NOTICES.txt')
Copy-Item -LiteralPath (Join-Path $root 'docs\GODOT-LICENSE.txt') -Destination (Join-Path $output.FullName 'GODOT-LICENSE.txt')
$launch = @'
@echo off
cd /d "%~dp0"
start "" "%~dp0PetForge.exe" --path "%~dp0PetForgeRuntime" -- --pet-project "%~dp0pet"
'@
[IO.File]::WriteAllText((Join-Path $output.FullName 'Start-PetForge.bat'), $launch, [Text.Encoding]::ASCII)
$readme = @'
自定义桌宠 PetForge — Windows 便携版

完整解压后双击 Start-PetForge.bat。鼠标左键拖动角色，右键切换互动，选中桌宠后按 Esc 退出。
这只卡通女孩的细致动作是专门制作的。想做自己的桌宠，请看 https://github.com/lesile1312/PetForge 的透明 PNG 和本机编辑器教程。
本包已包含 Godot，无需另装；照片处理和编辑网页需按项目教程单独运行。

PetForge Windows desktop pet

Unzip the entire archive and double-click Start-PetForge.bat.
Drag with the left mouse button; right-click the pet to cycle actions; focus the pet and press Esc to exit.
The bundled character is an example; its detailed animation is specifically authored for this character.
To make your own pet, see https://github.com/lesile1312/PetForge for the transparent PNG and local editor workflows.
This portable package includes Godot and does not require a separate Godot installation. It does not include the editor or photo processing service.
'@
[IO.File]::WriteAllText((Join-Path $output.FullName 'README.txt'), $readme, [Text.UTF8Encoding]::new($false))
Write-Output $output.FullName
