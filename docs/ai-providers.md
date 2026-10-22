# Local image-to-pet pipeline

PetForge keeps portrait processing on the same computer:

1. [`danielgatis/rembg`](https://github.com/danielgatis/rembg) with the `birefnet-portrait` ONNX model finds a person and saves the transparent source as `cutout.png`.
2. A local palette-reduction, contour, and sticker-outline pass creates the comic-style `character.png` sprite. This is deterministic image processing, not generative anime redraw.
3. The official [VAST-AI-Research/TripoSR](https://github.com/VAST-AI-Research/TripoSR) project optionally reconstructs a static `model.glb` from the unfiltered cutout.
4. The web editor previews the animated sprite by default and offers the GLB as a separate rotatable view. The Godot desktop runtime animates the comic sprite with procedural idle, walk, sleep, jump, wave, happy, spin, stretch, dance, and angry motions.

The app keeps original uploads in local storage. Setup downloads model dependencies and weights to `E:\Caches\PetForge`; uploaded photos stay on the local API and are not sent to a cloud reconstruction service. A single view cannot reveal hidden surfaces, so the model's back and unseen geometry are inferred.

## Setup

Run `scripts/setup.ps1` once for the web/API dependencies, then run `scripts/setup-ai.ps1` in PowerShell. The AI setup keeps PyTorch and downloaded weights in `E:\Caches\PetForge`, uses CUDA PyTorch when an NVIDIA GPU is available, and configures a CPU mesh-extraction fallback for Windows machines without the native `torchmcubes` build toolchain. It then writes the selected provider and local paths to `.env`.

After setup, start the editor and API with `pnpm dev`. The first upload runs local person segmentation, and the 3D checkpoint is already cached locally. TripoSR's upstream README reports approximately 6 GB of VRAM for its default one-image input. PetForge requests a 192-cell mesh resolution to leave more headroom on an 8 GB GPU.

To keep the first stage on the simpler edge-color algorithm, set `BACKGROUND_REMOVAL_PROVIDER=edge-matte`. To disable local 3D reconstruction, set `PETFORGE_3D_PROVIDER=disabled`; uploaded files still stay local. These alternate modes do not claim a completed AI 3D conversion.

## Output and diagnostics

Each exported pet package contains `pet.json`, the cutout `cutout.png`, the comic sprite `character.png`, and—when generated—`model.glb`. The original upload remains in the local project storage and is not included in the export. Godot launch logs are written to `storage/pets/<pet-id>/runtime.log`; TripoSR output is written to `storage/pets/<pet-id>/triposr.log`.

The TripoSR source and pretrained model are distributed under MIT by their upstream project. The `rembg` Python package has its own license, and each segmentation model's weights can have a separate license. Review the selected model's license before commercial distribution.

## Upstream references

- [rembg](https://github.com/danielgatis/rembg) provides local ONNX-based image segmentation and lists `birefnet-portrait` for portrait cutouts.
- [VAST-AI-Research/TripoSR](https://github.com/VAST-AI-Research/TripoSR) provides the single-image 3D reconstruction pipeline and GLB export used here.
- [Godot runtime file loading and saving](https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html) documents loading glTF/GLB scenes through `GLTFDocument` and `GLTFState`.
- [phanstudio/Desktop-Pet](https://github.com/phanstudio/Desktop-Pet) demonstrates Godot's transparent, borderless, always-on-top desktop-pet window settings.
