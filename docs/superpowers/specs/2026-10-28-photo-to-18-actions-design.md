# Photo-to-PetForge 18-Action Generation

**Status:** Approved by owner on 2026-10-28; P0 implementation is in progress.

**Decision:** Hybrid character rig and generated key poses, selected by the user on 2026-10-28.

**Scope:** Turn one user-provided portrait into a reviewed, locally generated 2D character that can perform the same 18 action types as the creator's showcase.

## Intent

Users should be able to upload a photo, choose the person to use, review a recognizable full-body cartoon character, and preview that character performing PetForge's 18 showcased actions. They should be able to correct uncertain character points, retain editable intermediate files, and run the result in the transparent Windows desktop pet.

“Read the person” means detect people, face location, pose, and visible visual traits. It does not mean identify a real-world person, compare the face with an identity database, or verify identity.

## Current baseline

- The local Next.js editor uploads an image and moves through upload, background-removal, and editor stages.
- FastAPI stores project images locally and calls a background-removal provider. `cartoon.py` applies a comic filter; it does not redraw a photo as a new cartoon character.
- `animation.py` currently contains a mock provider. It does not generate animation.
- The public page now shows 18 illustrations and three motion reels for the creator's own character. Those assets are examples, not a generator for arbitrary photos.
- The shared pet schema is version 1.0 and cannot yet describe a complete rig, per-character motion data, or generated key poses.

The larger architecture, privacy requirements, and model candidates remain in [the photo-to-pet technical design](../../photo-to-pet-technical-design.zh-CN.md). This document narrows that plan to the requested photo-to-18-actions capability.

## Approaches considered

| Approach | Benefit | Cost or risk |
| --- | --- | --- |
| Generate an independent image or frame sequence for every action | Fastest route to a visual prototype; large pose differences are easy to request | Face, hair, clothing, body size, and edges can drift between actions; frame interpolation can look unstable |
| Generate one character and auto-rig it for every action | One consistent appearance and continuous motion; small motions can be evaluated at 60 Hz | Automatic semantic layers, hidden-pixel repair, and complex prop poses are difficult; incorrect limbs can make every motion look wrong |
| **Hybrid: one confirmed character and rig for shared motion, generated key poses for difficult actions** | Keeps one character identity and continuous movement while allowing mirror/phone poses to use dedicated art | Most involved option; generated key poses still need identity checks, compatible layer geometry, and a safe fallback |

The user selected the hybrid approach. The system must never claim all 18 actions are supported merely because the action names exist. Each action becomes available only after that character's generated assets pass preview checks.

## Goals

1. Run photo inference on the user's Windows computer. After model setup, photo processing and pet generation must not upload the photo to a project server.
2. Detect and select one person. Let the user confirm the proposed character and correct uncertain landmarks or layer boundaries.
3. Create a consistent full-body cartoon character from visible photo traits. Mark unseen or inferred clothing/body parts as AI-generated guesses.
4. Adapt the complete 18-action catalog to the confirmed character, with clear per-action previews and disabled states when an action fails quality checks.
5. Use continuous rig evaluation for small and locomotion motions. Use generated, identity-conditioned key poses for large changes such as mirror and phone interactions, with controlled transitions between poses.
6. Preserve the source image, masks, generated candidates, user corrections, model revision, settings, rig, previews, and prior project revisions locally.
7. Package only the files needed to run/share a pet. Do not include the original photo or private generation metadata by default.

## Non-goals

- Cloud image generation, online accounts, paid API keys, face lookup, or face authentication.
- Promising exact identity likeness or recovering genuinely invisible details from a cropped photo.
- Replacing the optional 3D reconstruction experiment or making 3D a prerequisite.
- Shipping model weights until each model's code, weight, and redistribution licenses are verified.
- Making a single flat PNG perform detailed hand, eye, or prop motions by stretching or distorting its pixels.

## User flow

1. The local app checks installed model files, available RAM/VRAM, and inference device. It offers CPU inference when supported and shows estimated downloads before installation.
2. The user selects a PNG, JPEG, or WEBP photo. The app normalizes orientation and removes EXIF from derived previews.
3. Person detection proposes a crop and landmarks. For group photos, the user selects one person or draws a crop manually.
4. Background removal produces an editable mask and transparent cutout. The user can restore hair/edges or erase background without replacing the original.
5. The local image provider generates one full-body cartoon candidate at a time, conditioned on the face and whole-person reference. It carries forward hair, glasses, skin tone, and clothing colors where visible.
6. The user reviews the candidate. For an avatar or half-body photo, the interface labels the lower body and unseen clothing as inferred. The user can adjust the short description and regenerate.
7. The asset compiler proposes layers, pivots, joints, eye regions, and feet baseline. The user corrects only low-confidence landmarks and boundaries.
8. The motion compiler adapts the 18-action library. The preview shows the full character at the intended desktop scale and reports which actions are ready, need correction, or are unsupported.
9. The user reviews and saves a version. The app exports a versioned pet package and launches it in the existing transparent Godot runtime.
10. The pet continues independently of the editor. The user can return to the local project and revise the character, rig, or actions.

## The 18-action catalog

The action IDs should be stable and independent of their Chinese display names.

| Group | Action IDs | Required behavior |
| --- | --- | --- |
| Everyday (4) | `idle`, `waiting`, `blink_smile`, `sleep` | Subtle breathing, quiet wait, fitted eyelid/expression motion, relaxed sleep |
| Movement (2) | `run_left`, `run_right` | Alternating legs, counter-swinging arms, direction-aware motion, stable feet and complete silhouette |
| Greeting (3) | `wave_smile`, `happy_smile`, `bow` | Mouse-hover welcome, restrained expression change, smooth return to rest |
| Self gestures (8) | `hair_touch`, `mirror`, `think`, `look_around`, `shy_face_touch`, `stretch`, `covered_laugh`, `heart` | Limited joint motion, correct hand layering, eye target where relevant, no limb/face clipping |
| Prop interaction (1) | `phone_crouch` | Crouch and settle; hold gaze at phone; pause, tap, and swipe; restore standing pose smoothly |

The public showcase's labels map to these IDs: quiet idle, waiting, blink and smile, sleep, left/right run, wave and smile, happy smile, bow, adjust hair, look in mirror, chin-rest thinking, look around, shy face touch, stretch, covered-mouth laugh, send a heart, and crouch to use a phone.

## Hybrid animation design

### Confirmed character and rig

- Store normalized landmarks and confidence for head, neck, shoulders, elbows, wrists, hips, knees, ankles, eyes, and feet baseline.
- Propose semantic layers for back hair, face/head, front hair, torso, upper/lower arms, legs, shoes, eyes/mouth, and held props. Do not treat a foreground mask as semantic layers.
- Use overlap at joints and local inpainting to repair pixels hidden by separated limbs. Preserve source and each derived layer as separate revisions.
- Keep the reference image and chosen stylized character as fixed appearance references for every action-specific generation. Do not independently redraw the whole character for each motion.
- Allow a small, bounded set of manual edits for low-confidence joints and boundaries. Record edit count and time; if correction is not simple, mark the character unsupported rather than silently claiming success.

### Motion generation

- Evaluate the rig and motion curves on the runtime frame delta, targeting 60 Hz. Sixty hertz is the update target, not a claim that every motion contains 60 independently drawn images per second.
- Use shared rest pose, joint limits, easing, and explicit enter/hold/exit phases. Actions must return to rest or a compatible next state without a scale jump.
- Drive breathing, blink, gaze, run cycle, wave, bow, and small gestures through the rig where the character's parts support them.
- For `mirror` and `phone_crouch`, generate a small set of poses conditioned on the locked character reference and standard pose guides. Extract compatible layers or pose meshes, align joints, and blend transitions through the rig.
- Permit generated key poses for other gestures only when a rig-only version fails that character's preview checks. Do not inject a different face or outfit to make the pose easier.
- Validate face proportions, limb count, silhouette bounds, foot baseline, prop grip, eye target, and return-to-rest. Disable only the failing action while preserving the accepted character and other actions.
- Keep the desktop pet at the user's selected scale. Do not enlarge the character in previews to disguise missing edges or clipping.

## Architecture and package boundary

- Keep Next.js as the local editor and FastAPI as the local project/API layer.
- Add a single local worker process for long-running detection, stylization, layer extraction, rigging, and pose generation. API requests create/poll/cancel jobs; they do not wait synchronously for model inference.
- Put model access behind replaceable providers. Initial model candidates remain SDXL plus reference conditioning and pose control, subject to P0 quality, hardware, and license review. Do not hard-code an unverified model revision or CUDA-only settings into the CPU path.
- Add a motion library with versioned action IDs, joint curves, pose guides, prop anchors, constraints, preview requirements, and capability declarations.
- Introduce a versioned package format for rig, textures, motions, props, and preview images. Migrate existing 1.0 packages without overwriting them; keep the old static-sprite route working.
- The Godot runtime loads only validated declarative data from the package. It must not execute package-provided scripts or shaders.

The proposed component map and job lifecycle in the linked technical design remain authoritative for API paths and persistence until an implementation plan resolves concrete interfaces.

## Privacy, licensing, and failure behavior

- Keep photos, masks, candidate images, model cache, and project metadata under the local data root. Do not send them to GitHub Actions, analytics, or crash reports.
- On export, omit source photos, face crops, EXIF, prompts, absolute paths, and personal names unless the user explicitly opts in.
- Store model source, revision, hash, license, and redistribution decision. Use consented sample photos for quality work; do not publish test photos or generated user projects.
- Show model download size and destination before downloading. Cancellation and a failed inference must preserve prior valid project outputs.
- If detection, stylization, rigging, or a pose fails, retain completed artifacts and state which stage failed. Never replace a previously accepted action with a broken candidate.
- If the CPU path cannot complete within tested memory limits, report the device limitation and offer a user-selected lower-resolution/quality mode. Do not silently fall back to cloud inference.

## Delivery phases and acceptance

### P0 — feasibility spike

Use at least six consented, varied real test photos, including full-, half-, and head-only crops; long/short hair; glasses; different lighting/backgrounds; and one group image requiring selection. The build owner may use volunteer testers; the current project owner is not required to provide all samples. Synthetic or openly licensed images can supplement technical coverage, but do not count as user-approved likeness examples. Keep private samples out of GitHub, CI, telemetry, and public previews unless each subject separately approves publication.

The initial CPU-only reference machine is Windows 10/11 x64 with 16 GB RAM. Also record one supported discrete-GPU machine. The user accepts longer CPU waits, so P0 has no promised generation-time ceiling; it must complete without exhausting memory, report measured stage times and peak usage, remain cancellable, and show real progress. Publish the measured hardware and timings instead of claiming every Windows PC is covered. Lower-memory profiles remain unsupported until measured.

Record the actual hardware, model revisions/licenses, runtime, peak RAM/VRAM, correction count, and per-stage failure. On at least two distinct photos, complete a character accepted by its subject or the project owner, then demonstrate idle, left/right run, wave, and one complex prop action. P0 is not proof that all 18 work for all photos.

### P1 — local image and review flow

Provide capability/download checks, person selection, editable cutout, stable cartoon candidate generation, explicit inferred-body labels, saved revisions, cancellation, and recovery. CPU and GPU modes must be selected and reported honestly.

### P2 — rig and core actions

Compile editable layers/landmarks, show a fitted preview, and run idle, waiting, blink, sleep, left/right run, wave, happy smile, and bow. Actions use the full character silhouette and return to a stable rest pose.

### P3 — all 18 actions

Adapt hair, mirror, think, look-around, shy-face, stretch, covered-laugh, heart, and phone-crouch. All 18 show clear ready/needs-fix/unsupported status. Mirror gaze targets the mirror; phone gaze targets the device; crouch includes a stable hold, taps, swipe, and smooth stand-up.

Call a character **18-action-ready** only when all 18 actions pass its preview checks. A partial draft may preserve and preview its ready actions, but must show missing actions and must not be described as delivering the complete 18-action set. P3 is complete only when all 18 pass for at least two distinct, consented test photos without character-specific source-code edits.

### P4 — package and Windows release

Export/import the new package format, preserve old packages, launch/close the standalone transparent runtime, and verify ordinary Windows CPU plus a supported discrete GPU. Release only after installer, privacy, license, and clean-machine checks pass.

### Acceptance for a supported photo

- The user approves the character's visible traits and all inferred body regions are labeled.
- The character stays complete at original desktop scale across every enabled action. Hair, hands, feet, and props are not clipped.
- Left/right running uses both legs and returns to rest without a visible jump. Small motions use smooth time-based interpolation; frame-time is measured on target hardware.
- Hand gestures respect joint limits and layer order. Mirror/phone eye targets and phone interactions are visible and stable.
- Each enabled action has a full-cycle preview and has been accepted for that character. Failed actions remain disabled, with the accepted character and working actions intact.
- A result labeled **18-action-ready** contains all 18 accepted actions. A partial draft is labeled as partial and lists every missing or unsupported action.
- The original remains recoverable; all intermediate assets stay in the local project. Export excludes private source data by default.

## Builder choices left open

The implementer may settle exact model revisions, runtime/device heuristics, landmark confidence thresholds, interpolation curves, and concrete API field names after P0 measurements. The implementer must document license findings and report CPU/GPU hardware results before claiming ordinary-PC support. Do not ask the user to choose model internals before there is measurable evidence.

## Approval gate

The owner approved this design and the P0 implementation plan on 2026-10-28. Complete P0 and record evidence before claiming photo-to-18-actions works. Continue later phases from measured P0 results.
