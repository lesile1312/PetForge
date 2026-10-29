# Development status

PetForge is a Windows-first open-source desktop-pet editor. The current goal is a dependable custom-pet workflow from a ready character image to a configurable desktop companion. This page describes the public source tree; private photo-processing runs and local character archives are not included.

## Included foundations

- Next.js editor for direct transparent-PNG import, optional photo cutout, live preview, pet settings, save, export and local launch.
- FastAPI API with local SQLite and file storage.
- Local portrait segmentation provider for the optional photo route.
- Godot 4 transparent desktop runtime with screen movement and built-in interaction foundations.
- Shared pet configuration schema and ZIP export path.

## In progress

- Windows app packaging and clean-machine setup validation.
- Better ways to adjust or add actions for each imported character.
- Automatic cartoon redraw and photo-specific action generation remain exploratory work, not part of the usable feature promise.

The illustrated 18-action set belongs to the creator's custom character. Other imported images use the runtime's built-in general actions; the custom set must not be presented as automatic output for every photo.

## Verification boundary

The static GitHub Pages site is a showcase, not a remote desktop launcher. A packaged consumer installer, clean-machine Windows matrix, broad photo-cutout quality, and universal character-specific action generation have not been validated.

See the [technical design](photo-to-pet-technical-design.zh-CN.md) and [current source audit](current-state-audit.zh-CN.md) for the implementation path and known limitations.
