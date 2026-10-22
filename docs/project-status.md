# Development status

PetForge is an active Windows-first local-development project. This page describes the code and generic demo assets included in the public repository. It does not describe the excluded private character artwork or its local development archives.

## Included foundations

- Next.js editor for the photo upload and pet settings flow.
- FastAPI API with local SQLite and file storage.
- Local portrait segmentation provider and transparent cutout workflow.
- Comic-style image processing and optional local single-image 3D reconstruction experiment.
- Godot 4 transparent desktop runtime with a generic cat demo, screen movement and interaction foundations.
- Shared pet configuration schema and ZIP export path.

## In progress

- Generating a consistent cartoon character from different personal photographs.
- Automatically separating body, face, eyes, hair and limbs into reusable animation layers.
- Rigging arbitrary generated characters and quality-checking actions without writing character-specific code.
- Recoverable background jobs, a general-purpose Windows installer, and clean-machine release validation.

The advanced animation poses in the local development history use a private, character-specific asset package, which is deliberately excluded from this public repository. The generic demo must not be presented as proof that every uploaded photo already receives those poses automatically.

## Verification boundary

Existing local Godot motion captures cover one character package and do not demonstrate universal photo-to-rig generation. A packaged consumer installer, broad Windows hardware matrix, CPU generative-illustration path, and public hosted service have not been validated as part of this publication preparation.

See the [technical design](photo-to-pet-technical-design.zh-CN.md) and [current source audit](current-state-audit.zh-CN.md) for the implementation path and known limitations.
