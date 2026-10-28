# 自定义桌宠petforge

**Make a desktop companion from your own character image.**

[中文文档](README.zh-CN.md) · **English** · [Live demo](https://lesile1312.github.io/PetForge/#example) · [Create with your reference](https://lesile1312.github.io/PetForge/#create)

自定义桌宠petforge is a Windows-first open-source desktop-pet studio built with Next.js, FastAPI and Godot. Bring a transparent character PNG to run a pet directly, or process a portrait locally into a transparent, comic-filtered image before launching it in an independent desktop window.

## New here? Start with the route that fits

| What you want to do | Follow this route | You will need |
| --- | --- | --- |
| I already have a transparent character PNG | [Run a PNG desktop pet](#make-your-own-pet--transparent-png-route) ([download source ZIP](https://github.com/lesile1312/PetForge/archive/refs/heads/main.zip)) | Windows, Godot 4, and the 自定义桌宠petforge source |
| I want to start from a portrait | [Set up the local photo editor](#quick-start-windows-development) | Windows, Node.js, pnpm, Python, Godot 4, and internet for the first model download |
| I only want to preview the project | [Open the live demo](https://lesile1312.github.io/PetForge/#example) | A browser; the demo cannot launch a pet on your computer |

**What this release does:** GitHub Pages is a static showcase and reference-photo helper, not a hosted photo-generation service. Photo processing currently removes the background and applies a comic filter. It does not yet redraw arbitrary photos as polished chibi art, invent cropped body parts, or generate a character-specific animation rig. This repository contains source code; a one-click consumer installer is not available yet. For the most reliable result today, start with a complete transparent cartoon PNG. 自定义桌宠petforge is an independent community project and is not affiliated with OpenAI or Codex.

## From the original photo to the custom character

<p align="center">
  <img src="docs/images/pet-demo/reference-photo.jpg" height="340" alt="Original portrait used as the character reference" />
  <img src="docs/images/pet-demo/idle-portrait.png" height="300" alt="Custom cartoon desktop pet based on the reference" />
</p>

These images show the same creator-owned character: the provided reference photo and the custom cartoon girl designed and refined over multiple iterations. The website showcase, its action previews, and the desktop runtime default use the same character assets. This is a custom case; arbitrary photo uploads do not automatically receive the same artwork or animation rig.

<p align="center"><img src="docs/images/pet-demo/action-gallery.png" width="760" alt="Custom pet idle, blink, left-run and right-run poses" /></p>

[View the original-photo comparison](https://lesile1312.github.io/PetForge/#example) · [View run-cycle frames](docs/images/pet-demo/run-cycle.png)

## 18 actions in the custom character showcase

[Browse the full illustrated action catalog and watch the motion previews](https://lesile1312.github.io/PetForge/#actions). The page includes 18 character-specific action illustrations and three animated previews rendered from the Godot desktop runtime at 60 FPS, including a full 16-second phone interaction.

- **Everyday (4):** quiet breathing idle, waiting for input, blink and smile, sleep.
- **Movement (2):** run left, run right.
- **Greetings and gestures (11):** wave and smile, happy smile, bow, adjust hair, look in a mirror, chin-rest thinking, look around, shy face touch, stretch, covered-mouth laugh, send a heart.
- **Phone interaction (1):** crouch, watch the screen, tap, and swipe.

These are custom assets for the showcased character. A newly uploaded image does not automatically receive these poses, animation frames, or a character-specific rig.

## What you can use today

| Capability | Current behavior |
| --- | --- |
| Your own PNG → desktop pet | Creates a package from your image and runs the generic Godot pet; no AI model required |
| Portrait processing | Local rembg segmentation plus a comic palette/outline filter; original and processed images are shown together |
| Desktop window | Transparent, borderless, draggable, optionally always on top; independent of the browser |
| Behavior | The showcased character has 18 custom action illustrations; the generic runtime provides idle, movement, sleep, jump and click reactions. Other images do not inherit this character's gestures automatically |
| Portable package | `pet.json` and `character.png`; optional cutout and static GLB |
| Public website | Reference-photo preview and `.petforge.json` download; no cloud photo generation |
| AI chibi redrawing, body completion, automatic rigging | Planned; see the [technical design](docs/photo-to-pet-technical-design.zh-CN.md) |

An uploaded photo is currently filtered, not redrawn into a new chibi illustration. For a polished cartoon pet today, prepare a cartoon PNG first and use the direct-PNG route. Existing artwork is animated through the generic runtime; new limb-motion frames are not automatically generated.

## Make your own pet — transparent PNG route

Requires Windows 10/11 x64, PowerShell, Git (or a downloaded repository ZIP), and a Godot 4 executable. This route does not require Node.js, Python, CUDA or an AI account.

1. Clone the repository, or download and extract its ZIP:

```powershell
git clone https://github.com/lesile1312/PetForge.git
cd PetForge
```

2. Prepare a transparent PNG with the whole character visible. Keep padding around hair, hands and feet. A PNG with an opaque background will display that background too.
3. Run this command, replacing both example file paths with your own:

```powershell
.\scripts\create-pet.ps1 -ImagePath 'C:\Pictures\my-character.png' -Name 'My companion' -GodotExecutable 'C:\Tools\Godot\Godot.exe'
```

The script prints the package folder and starts the pet. Each run creates a new folder under `storage/custom-pets/`; it does not modify your source image or overwrite existing packages. To create files without starting Godot:

```powershell
.\scripts\create-pet.ps1 -ImagePath 'C:\Pictures\my-character.png' -Name 'My companion' -NoLaunch
```

Drag with the left mouse button, right-click to cycle interactions, and press Esc while the pet has focus to quit. The small pet window can appear over other applications. Action quality depends on the image and available rig, especially for a single flat PNG.

## Quick start (Windows development)

Use the full local editor when starting from a photograph.

### Requirements

- Windows 10/11 x64; Git or the extracted repository ZIP.
- Node.js 22.13+ and pnpm 11.19.0 (as declared in `package.json`; pnpm requires this Node version).
- Python 3.12 with the Windows `py` launcher or `python.exe` on PATH.
- Godot 4 to run the desktop pet. The current project has been developed with Godot 4.7.2; use a compatible Godot 4 build.
- Internet access for dependency installation and the first segmentation-model download. CPU segmentation is supported; a CUDA GPU is only needed for the separate TripoSR experiment.

### Install, configure, start

From the repository root:

```powershell
npm install --global pnpm@11.19.0
.\scripts\setup.ps1
```

The setup script creates `.env` if missing. Edit this line to point to your installed executable:

```dotenv
PETFORGE_GODOT_EXECUTABLE=C:/Tools/Godot/Godot.exe
```

Then start both local services:

```powershell
pnpm dev
```

Keep that terminal open and visit <http://127.0.0.1:3000/>. API health: <http://127.0.0.1:8000/health>.

### Photo → processed image → your desktop pet

1. Select a PNG/JPG/WEBP photo (maximum 10 MB), or import the `.petforge.json` reference file saved by the public website.
2. Wait for local portrait segmentation and the comic filter. The first model load can download weights; a complicated background or occluded hair may need a different source image.
3. Compare the original with the transparent result. Adjust appearance and behavior in the editor. This step currently does not offer AI cartoon redrawing or automatic body completion.
4. Click **启动桌宠** after you are satisfied. Godot must be configured in `.env`; restart `pnpm dev` after changing configuration. The pet runs in a separate native window.
5. Click **导出资源** to keep or share your generated ZIP. It is an asset package, not an `.exe` installer.

3D generation is an explicit optional action, so making a 2D pet does not wait for TripoSR. Install the separate environment with `scripts/setup-ai.ps1` only if you want the static 3D preview. It can download large files and requires compatible CUDA hardware.

### Run an exported pet again

Extract the resource ZIP into its own folder. Keep `pet.json` beside `character.png` and preserve any referenced assets. Run:

```powershell
& 'C:\Tools\Godot\Godot.exe' --path '.\apps\desktop' -- --pet-project 'C:\MyPets\MyCompanion'
```

Run this from the repository root. The pet continues independently of the web editor; Esc exits the focused pet. To share a package, recipients also need this project and Godot or a compatible 自定义桌宠petforge runtime. Exporting only the ZIP does not install that runtime on another computer.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `127.0.0.1:3000` cannot open | Start `pnpm dev` on that computer and keep the terminal open. The public Pages site does not start local services. |
| Launch reports Godot is not configured | Set the actual executable path in `.env` and restart services; `create-pet.ps1` accepts `-GodotExecutable` directly. |
| Script execution is blocked | Open a PowerShell session with a process-only policy, e.g. `powershell -NoProfile -ExecutionPolicy Bypass`, then run the command there after reviewing the script. No machine-wide policy change is needed. |
| Installation fails | Check Node/pnpm/Python versions and the terminal error; rerun `scripts/setup.ps1` after correcting it. |
| First segmentation is slow or fails | Model loading may require a download. Check the API terminal, network and free disk space. A transparent PNG can use the direct route while you resolve model setup. |
| The output looks like a filtered photo | That is the present photo-processing capability. Supply a prepared cartoon PNG for a cartoon character. |
| Hair or a foot is missing | Check the source and segmentation result. Add transparent padding; the runtime cannot recover body parts missing from the source. |
| New image does not perform the sample's gestures | The sample uses custom art. A new PNG gets generic runtime behavior, not a matching newly generated skeletal rig. |
| 3D fails | 2D creation still works. 3D is optional and needs its separately installed environment. |

## Privacy, licenses and contribution

Visitor photos selected on the static website remain in that browser unless the visitor saves/shares the reference file. The local editor sends images to FastAPI on the same machine; source images, generated files and project data live under `storage/` by default. Choose another location with `PETFORGE_STORAGE_ROOT` and `PETFORGE_DATABASE_PATH`. Neither runtime script uploads photos. Do not commit `.env`, personal projects or model caches.

The demonstration photo was published at the creator's request. Its display does not grant reuse rights; see [third-party notices](THIRD_PARTY_NOTICES.md). Source code is [Apache-2.0](LICENSE); model weights and artwork have separate terms.

The API is a local development service. Public hosting requires additional access control, quotas, storage and retention policies. Dependencies also need regular security updates; a development build is not a security audit.

Contributions to installer packaging, automatic character rigging, natural gestures and accessible editing are welcome. Include reproduction steps and your OS/version in issues; omit private photos and credentials.

## Project structure and design

See the [workflow validation record](docs/validation-2026-10-23.md) for what was checked locally and the remaining verification boundaries.

```text
apps/web/              Next.js local editor
apps/desktop/          Godot transparent desktop runtime
services/api/          FastAPI and local image processing
packages/pet-schema/   Shared pet configuration contracts
scripts/create-pet.ps1 Direct image-to-runtime workflow
storage/               Local private projects (ignored by Git)
docs/                  Public website and technical documentation
```

[Architecture](docs/architecture.md) · [Photo-to-pet design](docs/photo-to-pet-technical-design.zh-CN.md) · [Package format](docs/pet-format.md) · [Development](docs/development.md) · [Project status](docs/project-status.md)
