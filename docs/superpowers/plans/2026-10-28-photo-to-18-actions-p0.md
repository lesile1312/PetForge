# Photo-to-PetForge Feasibility Spike Implementation Plan

**Status:** Approved by owner on 2026-10-28; P0 implementation is present, but the evidence gate remains incomplete. Last verified 2026-10-29.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Prove that local photo conditioning can create a user-approved full-body cartoon character and adapt it to five representative PetForge motions before building the public 18-action flow.

**Architecture:** Run an isolated Python worker and CLI beside the existing FastAPI app. Load image preflight, person/cutout/character/action providers behind interfaces, keep models and evaluation photos under local ignored storage, and render a hybrid rig/key-pose preview through Godot. P0 is one vertical slice because the action proof depends on the exact candidate/layer contract produced by photo generation. P0 validates feasibility; it does not replace the upload UI or claim the whole 18-action feature is ready.

**Tech Stack:** Existing Python 3.12 and FastAPI project; isolated Python worker environment; candidate Diffusers/PyTorch local image models selected by a license and hardware spike; existing Godot 4 desktop project; JSON manifests and Markdown/JSON evaluation reports.

**Spec:** [Photo-to-PetForge 18-Action Generation design](../specs/2026-10-28-photo-to-18-actions-design.md)

**Execution scope:** This plan stops at P0 evidence. Write P1, P2, P3, and P4 plans from measured P0 results; do not invent model choices or acceptance claims in advance.

## Global Constraints

- Windows 10/11 x64 is the target platform; the initial CPU-only reference machine has 16 GB RAM.
- The user accepts longer CPU waits; P0 has no promised generation-time ceiling, but must report real stage times and progress, remain cancellable, and complete without exhausting memory.
- After model setup, photos and generated assets remain on the user's computer; no cloud inference or photo upload is allowed.
- Person detection finds a person and visible pose/traits; it does not identify a real-world person or use an identity database.
- Missing body regions from head-only or half-body photos must be marked as inferred.
- 60 Hz is the runtime update target, not a claim of 60 independently generated images per second.
- Source photos, masks, candidates, corrections, and logs stay outside GitHub, CI, public previews, and telemetry unless each subject separately approves publication.
- Put model weights and evaluation assets under `E:\PetForge\models` and `E:\PetForge\evaluations` by default; allow `PETFORGE_MODEL_ROOT` and `PETFORGE_EVAL_ROOT` overrides. Keep generated project output selectable with `--output-root`.
- Existing version 1.0 pet packages must keep working and must not be overwritten.
- Commit each completed task locally after its final green verification; do not push during P0.
- A complete **18-action-ready** result requires all 18 actions; this P0 only evaluates idle, left/right run, wave, and phone-crouch.

## Review Focus

- Invalid, oversized, or corrupt images must fail before any model loads; pin this in `test_input_preflight_rejects_invalid_images`.
- Group photos must return selectable person candidates, not silently use the first; pin this in `test_group_photo_requires_selection`.
- Half-body inputs must label generated lower-body regions as inferred; pin this in `test_candidate_marks_inferred_regions`.
- CPU-only 16 GB and missing/corrupt model files must report a supported/unsupported state without switching to cloud; pin this in `test_device_profile_and_model_preflight`.
- Evaluation reports must not contain source paths, names, EXIF, prompt text, or image bytes; pin this in `test_report_contains_only_redacted_metrics`.

---

### Task 1: Isolated worker and model manifest

**Files:**
- Create: `services/worker/requirements-p0.txt`
- Create: `services/worker/requirements-p0-dev.txt`
- Create: `services/worker/pyproject.toml`
- Create: `services/worker/petforge_worker/__init__.py`
- Modify: `.gitignore`
- Create: `services/worker/petforge_worker/device.py`
- Create: `services/worker/petforge_worker/manifest.py`
- Create: `models/manifest.json`
- Create: `scripts/setup-photo-worker.ps1`
- Test: `services/worker/tests/test_device.py`
- Test: `services/worker/tests/test_manifest.py`
- Test: `services/worker/tests/test_setup_script.py`

**Interfaces:**
- `probe_device(check_gpu: bool = False) -> DeviceProfile` returns OS/architecture, available RAM, GPU name/VRAM when checked, and unsupported reasons. Probe system RAM without loading Torch; import the selected GPU backend only when `check_gpu=True`.
- `validate_manifest(manifest_path: Path, model_root: Path) -> ModelAvailability` checks revision, source URL, expected file hashes, license metadata, and local file state without downloading files.
- `DeviceProfile` and `ModelAvailability` are immutable dataclasses serialized with snake_case JSON keys.

- [x] **Step 1: Add worker package/test configuration and write failing device/manifest tests**

Add the package metadata in `pyproject.toml`, including pytest `pythonpath = ["."]`. Add `pytest` to the separate development requirements. Add device tests with a mocked system probe for Windows x64/16 GB CPU, a CUDA-capable GPU, unsupported architecture, and a lower-memory profile. Add manifest tests for missing weights, hash mismatch, and absent license metadata. Do not install Torch or download weights here.

- [x] **Step 2: Run focused worker tests**

Create the venv with `$python312 = (uv python find 3.12).Trim(); & $python312 -m venv services/worker/.venv`, install the editable package and dev requirements with `services/worker/.venv/Scripts/python.exe -m pip install -e services/worker -r services/worker/requirements-p0-dev.txt`, then run `services/worker/.venv/Scripts/python.exe -m pytest -c services/worker/pyproject.toml services/worker/tests/test_device.py services/worker/tests/test_manifest.py -q`. The setup script must prefer `uv python find 3.12` and fall back to `py -3.12` when `uv` is absent.
Expected: FAIL because worker modules do not exist.

- [x] **Step 3: Implement device and manifest checks**

Keep heavyweight imports out of `services/api`. Store only public model metadata in `models/manifest.json`; weights go under the user-selected local model root.

- [x] **Step 4: Complete the PowerShell environment setup entrypoint**

`setup-photo-worker.ps1` creates the isolated worker environment, installs the editable worker package plus `requirements-p0.txt`, and installs `requirements-p0-dev.txt` with `-Dev`. It prints the selected CPU/CUDA mode. It does not alter the API `.venv`, install model-specific Torch wheels, or download model weights.

- [x] **Step 5: Run focused checks**

Run: `services/worker/.venv/Scripts/python.exe -m pytest -c services/worker/pyproject.toml services/worker/tests/test_device.py services/worker/tests/test_manifest.py services/worker/tests/test_setup_script.py -q`

Expected: PASS; CPU/GPU status and missing model details are actionable and contain no user-photo data.

### Task 2: Private evaluation corpus and redacted report contract

**Files:**
- Create: `services/worker/petforge_worker/corpus.py`
- Create: `services/worker/petforge_worker/report.py`
- Create: `services/worker/petforge_worker/evaluation_schema.json`
- Create: `services/worker/petforge_worker/preflight.py`
- Create: `services/worker/tests/test_corpus.py`
- Create: `services/worker/tests/test_report.py`
- Create: `services/worker/tests/test_preflight.py`
- Modify: `services/worker/requirements-p0.txt`
- Create: `services/worker/requirements-photo-runtime.txt`

**Interfaces:**
- `load_eval_cases(root: Path) -> list[EvalCase]` reads local sample metadata and refuses real photos without explicit consent metadata.
- `write_eval_report(results: list[EvalResult], output_path: Path) -> Path` writes only pseudonymous case IDs, model/device IDs, timings, resource peaks, correction counts, and stage outcomes.
- `preflight_image(source_path: Path, output_path: Path, limits: ImageLimits) -> PreflightResult` validates type, size, dimensions, decode integrity, and orientation before any model import; derived previews drop EXIF.
- `PETFORGE_MODEL_ROOT` defaults to `E:\PetForge\models`; `PETFORGE_EVAL_ROOT` defaults to `E:\PetForge\evaluations`, both outside tracked source. Real photos are never copied into `docs/` or `tests/fixtures/`.

- [x] **Step 1: Write failing image-preflight, corpus-privacy, and report-redaction tests**

Cover invalid/oversized/corrupt files, EXIF orientation removal, missing consent, valid opt-in, private paths, duplicate sample IDs, and model error strings containing absolute paths.

- [x] **Step 2: Run focused privacy and preflight tests**

Run: `services/worker/.venv/Scripts/python.exe -m pytest -c services/worker/pyproject.toml services/worker/tests/test_preflight.py services/worker/tests/test_corpus.py services/worker/tests/test_report.py -q`

Expected: FAIL because the worker modules do not exist.

- [x] **Step 3: Implement preflight, corpus loader, and report schema**

Require a local consent record for real photographs. Synthetic images and openly licensed illustrations may supplement technical cases; neither counts as a user-approved likeness result. A license record only describes asset reuse and never replaces subject consent for real-person photos.

- [x] **Step 4: Verify the local evaluation directory is ignored**

Run `git check-ignore -v storage/evaluations/sample.png` and confirm the existing root-anchored `/storage/` rule covers it. Do not add a redundant ignore rule or broad pattern that hides API source.

- [x] **Step 5: Run focused checks**

Run: `services/worker/.venv/Scripts/python.exe -m pytest -c services/worker/pyproject.toml services/worker/tests/test_preflight.py services/worker/tests/test_corpus.py services/worker/tests/test_report.py -q`

Expected: PASS; reports contain no names, original paths, prompts, image bytes, or EXIF.

Task 2 limits: Match the existing browser/API upload cap at 10 MiB; cap decoded images at 8192 pixels per edge and 80 megapixels. Pillow is required for decoding and EXIF-safe output, pinned to the API-supported Pillow>=10.4,<13.0 range.

### Task 3: Local character-generation benchmark CLI

**Files:**
- Modify: `services/worker/pyproject.toml`
- Modify: `services/worker/requirements-p0.txt`
- Modify: `models/manifest.json`
- Modify: `services/worker/petforge_worker/manifest.py`
- Create: `services/worker/petforge_worker/providers/base.py`
- Create: `services/worker/petforge_worker/providers/cutout.py`
- Create: `services/worker/petforge_worker/providers/person.py`
- Create: `services/worker/petforge_worker/providers/layers.py`
- Create: `services/worker/petforge_worker/providers/portrait.py`
- Create: `services/worker/petforge_worker/benchmark.py`
- Create: `services/worker/petforge_worker/cli.py`
- Create: `services/worker/tests/test_cutout_provider.py`
- Create: `services/worker/tests/test_person_provider.py`
- Create: `services/worker/tests/test_layers_provider.py`
- Create: `services/worker/tests/test_portrait_provider.py`
- Create: `services/worker/tests/test_benchmark.py`
- Create: `services/worker/tests/test_cli.py`
- Create: `scripts/run-photo-benchmark.ps1`
- Create: `scripts/install-photo-models.ps1`

**Interfaces:**
- `CutoutProvider.cutout(source_path: Path, selected_person: PersonCandidate, output_dir: Path) -> CutoutResult` uses the selected normalized source-image box, saves a transparency-preserving mask/cutout pair, and records the padded source bounds plus reversible source-to-cutout transform.
- `PersonDetector.detect(source_path: Path) -> list[PersonCandidate]` returns normalized person boxes and pose confidence; the CLI requires an explicit selection for multiple candidates and accepts a manual crop when detection fails.
- `LayerSegmenter.segment(candidate: PortraitCandidate, landmarks_norm: dict[str, tuple[float, ...]], output_dir: Path) -> LayerSet` returns cutouts and confidence for the limbs, torso, hair, face, and eyes needed by the P0 motions. Landmarks come from a second detection pass on the generated candidate canvas.
- `PersonCandidate` contains `bbox_xywh_norm`, `landmarks_norm`, and `confidence`; `PortraitCandidate` contains local image/mask paths, inferred-region IDs, and provenance; `LayerSet` maps the P0 body-part IDs to local texture paths and confidence values.
- `PortraitRequest` contains a local source path, selected normalized source-image crop, style preset, optional clothing description, and inferred-region labels.
- `PortraitGenerator` is a protocol with `generate(request: PortraitRequest, device: DeviceProfile, output_dir: Path, cancel: CancelToken | None) -> PortraitCandidate`; the local model checks cancellation at diffusion step boundaries.
- `EvalCase` and `EvalResult` are defined in `corpus.py`.
- `LocalSDXLPortraitGenerator.generate(request: PortraitRequest, device: DeviceProfile, output_dir: Path, cancel: CancelToken | None) -> PortraitCandidate` writes a full-body RGBA candidate and machine-readable provenance record; cancellation is checked at diffusion step boundaries.
- `run_case(case: EvalCase, detector: PersonDetector, cutout: CutoutProvider, generator: PortraitGenerator, segmenter: LayerSegmenter, output_root: Path, cancel: CancelToken, reviewer: optional callback, person_index: optional index, manual_crop_xywh_px: optional crop) -> EvalResult` reports separate preflight, detection, cutout, generation, layer-segmentation, and review stages. Each stage writes to a retained revision directory; only explicit review acceptance updates the accepted pointer.
- CLI entrypoints: `petforge-worker generate --input <photo> [--person-index N | --crop x,y,w,h] --device auto --output-root <folder>` creates one local candidate; `petforge-worker benchmark --root <consented-case-root> --device auto` runs the private evaluation corpus; `petforge-worker review-candidate --candidate-dir <folder> --decision accept|reject` records explicit review without regeneration. Multi-person input must stop for a person selection.

- [x] **Step 1: Write provider-contract tests with a deterministic fake**

Pin corrupt-image rejection before model load, one-person selection, required group-photo choice, manual crop fallback, padded transparent cutout bounds and source-coordinate map, candidate dimensions/alpha, inferred-region labels, required layer confidence, provenance fields, cancellation, and stage-failure preservation without downloading real models.

- [x] **Step 2: Run provider-contract tests**

Run the focused tests listed in Step 5. Expected: FAIL because provider modules do not exist. The test suite must use fakes and must not import or download model weights.

- [x] **Step 3: Verify model source, license, and CPU/GPU configuration**

Use primary project/model documentation. Select one local candidate stack and record exact revisions, license findings, expected hashes, disk footprint, offline inference requirements, and separate CPU/CUDA dependency commands in the manifest before loading weights. Reject any stack whose source/weight license or redistribution/use conditions are unclear.

- [x] **Step 4: Implement the local providers and CLI**

Generate one candidate at a time. Use person detection for candidate boxes and pose hints; keep manual crop as the fallback. Run semantic layer extraction as a separate provider stage. Preserve the source, mask, candidate, seed, model revision, settings, and elapsed times in the private project directory. Require explicit review acceptance or rejection; preserve the previous accepted revision when a candidate is rejected. Label unseen lower-body regions as inferred; never claim they were read from the photo. Disable model-hub telemetry and force local-only model loading after installation.

- [x] **Step 5: Run contract checks**

Run: `services/worker/.venv/Scripts/python.exe -m pytest -c services/worker/pyproject.toml services/worker/tests/test_cutout_provider.py services/worker/tests/test_person_provider.py services/worker/tests/test_layers_provider.py services/worker/tests/test_portrait_provider.py services/worker/tests/test_benchmark.py services/worker/tests/test_cli.py services/worker/tests/test_manifest.py services/worker/tests/test_report.py -q`

Expected: PASS with the fake provider; no GPU or model downloads are needed for this check.

- [x] **Step 6: Install the selected model and run the local benchmark**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-photo-models.ps1 -Device auto` then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-photo-benchmark.ps1 -Device auto`
The installer shows model licenses, exact download size, destination, and free-space check before download; it verifies hashes and supports resume. Model weights never enter Git. Inference sets local-only model flags and disables model-hub telemetry. Expected: per-stage progress, cancellable generation, candidate files under ignored local storage, and a redacted report.

Result (2026-10-29): all four model components passed local size/hash/license checks. One consented CUDA photo run completed all inference stages in 134,841 ms; peak process memory was 15,772,946,432 bytes and peak GPU reservation was 6,765,412,352 bytes. Candidate remains pending owner review. A separate run generated additional candidates; those remain private and unaccepted.

### Task 4: Hybrid five-action preview spike

**Files:**
- Create: `services/worker/petforge_worker/rig_seed.py`
- Create: `services/worker/petforge_worker/action_pose.py`
- Create: `services/worker/tests/test_layer_confidence.py`
- Create: `services/worker/tests/test_rig_seed.py`
- Create: `services/worker/tests/test_action_pose.py`
- Create: `apps/desktop/tools/preview_photo_p0.gd`
- Create: `apps/desktop/scripts/animation/photo_pet_rig_p0.gd`
- Create: `apps/desktop/scripts/animation/photo_pet_action_p0.gd`

**Interfaces:**
- `seed_rig(candidate: PortraitCandidate, landmarks: list[Landmark], corrections: list[LandmarkCorrection]) -> RigSeed` uses normalized canvas coordinates, confidence, joints, feet baseline, and layer references.
- `RigSeed` is created only when all required P0 layer references exist; low-confidence joints remain editable and missing limb layers produce an explicit unsupported result.
- `ActionPoseCandidate` contains a stable character-reference ID, action ID, normalized key-pose landmarks, and local generated image path.
- `ActionPreview` contains `action_id`, `status` (`ready`, `needs_fix`, or `unsupported`), `frame_paths`, `fps_target`, `duration_seconds`, and `issues`; P0 supports only the five action IDs listed below.
- `generate_action_pose(candidate: PortraitCandidate, rig: RigSeed, action_id: str) -> ActionPoseCandidate` accepts only `wave_smile` or `phone_crouch` in P0.
- `render_action_preview(candidate: PortraitCandidate, rig: RigSeed, action_id: str, key_pose: ActionPoseCandidate | None = None) -> ActionPreview` renders `idle`, `run_left`, `run_right`, `wave_smile`, or `phone_crouch` at the selected original display scale. Idle and run use rig interpolation; wave and phone-crouch require a matching generated key pose plus interpolated entry/hold/return.
- Godot preview reads a local P0 manifest and fits the complete character to the existing desktop runtime's 330 px maximum height; it does not change the shipped default-pet configuration.

- [x] **Step 1: Write rig and action-pose contract checks**

Write rig and preview tests for normalized coordinates, bounded corrections, unknown action rejection, stable character reference, matching required key poses, missing-layer handling, and ready/needs-fix/unsupported states.

- [x] **Step 2: Run rig and preview contract tests**

Run: `services/worker/.venv/Scripts/python.exe -m pytest -c services/worker/pyproject.toml services/worker/tests/test_layer_confidence.py services/worker/tests/test_rig_seed.py services/worker/tests/test_action_pose.py -q`

Expected: FAIL because rig and preview modules do not exist.

- [x] **Step 3: Implement a coordinate-driven P0 rig seed**

Build isolated P0 animation scripts that read normalized rig data. Do not modify the existing creator-specific gesture/phone scripts or copy their absolute pixel coordinates into generated character outputs.

- [ ] **Step 4: Generate and render the five representative actions**

Use continuous rig interpolation for idle and left/right run; use reference-conditioned key poses for wave and phone-crouch. Include entry, hold, and return phases at the selected original display scale.

Run: `services/worker/.venv/Scripts/python.exe -m pytest -c services/worker/pyproject.toml services/worker/tests/test_layer_confidence.py services/worker/tests/test_rig_seed.py services/worker/tests/test_action_pose.py -q`

Expected: PASS; ready previews contain valid local frames and report 60 Hz as the runtime target.

Result (2026-10-29): five 60 Hz target previews and a contact sheet were generated for one riggable candidate. All five actions are `needs_fix`; the generated wave and phone key poses have missing/low-confidence landmarks and visible character drift. No action was accepted.

- [ ] **Step 5: Render two consented cases in Godot and review the complete silhouette**

Run: `& $env:PETFORGE_GODOT_EXECUTABLE --path apps/desktop --script res://tools/preview_photo_p0.gd -- --input <local-eval-case>`

Expected: five complete motion previews sampled at a 60 Hz runtime update target, a contact sheet, original character scale, no photo files written to the repository, and unsupported actions clearly marked. The 60 Hz target means time-based runtime interpolation; it does not require AI to generate 60 new frames per second.

Result (2026-10-29): not run. Godot executable was not found on PATH or the checked install locations; only one consented case has usable rig evidence.

### Task 5: P0 gate report and handoff

**Files:**
- Create: `services/worker/petforge_worker/p0_gate.py`
- Create: `services/worker/tests/test_p0_gate.py`
- Create: `docs/photo-to-pet-p0-template.md`

**Interfaces:**
- `evaluate_p0(results: list[EvalResult], action_previews: list[ActionPreview]) -> P0GateReport` returns `pass`, `incomplete_samples`, or `fail` with pseudonymous case IDs, relative evidence IDs, and explicit unsupported cases; never include absolute source paths or names.

- [x] **Step 1: Write P0 gate tests**

Require at least six varied consented real cases, at least two subject/owner-approved generated characters, five reviewed motions on both accepted characters, a measured Windows x64/16 GB CPU run, and a measured supported discrete-GPU run. Reject missing license, timing, memory, correction, or privacy evidence.

- [x] **Step 2: Run P0 gate tests**

Run: `services/worker/.venv/Scripts/python.exe -m pytest -c services/worker/pyproject.toml services/worker/tests/test_p0_gate.py -q`

Expected: FAIL because gate evaluator does not exist.

- [x] **Step 3: Implement a redacted, reproducible gate report**

Record CPU/GPU model, RAM/VRAM, model versions/licenses, per-stage time, peak usage, manual corrections, visible action defects, and the reason for pass/incomplete/fail.

- [x] **Step 4: Run P0 review and record the decision**

Run: `services/worker/.venv/Scripts/python.exe -m pytest -c services/worker/pyproject.toml services/worker/tests/test_p0_gate.py -q`

Expected: PASS for gate logic. The actual gate remains `incomplete_samples` until its real-photo and human-review evidence is present.

Result (2026-10-29): all 90 worker tests passed. The selected single-case gate report is `incomplete_samples`, with no failure codes. It records one consented real case, zero owner-approved characters, zero reviewed actions, and missing six-case, 16 GiB CPU, two-character, and ten-action evidence.

- [x] **Step 5: Stop at the evidence gate**

If P0 passes, use its measured model and rig evidence to write the separate P1 local-generation plan. If it fails, revise the design and return to the owner before expanding the implementation. Do not claim the full 18-action workflow from P0 evidence.

Result (2026-10-29): stopped before P1. Five-action quality and real-Godot review remain unresolved; the P0 evidence threshold is not met.

## Execution boundary

This plan implements and measures P0 only. It does not add a public upload flow for generated characters, promise all 18 motions, migrate pet packages, publish model weights, or create a Windows installer. Those phases need P0 evidence and their own focused plans.

## Plan self-review

- Spec coverage: local image preflight, person selection, reviewable full-body candidate, inferred-region labels, retained local intermediates, five representative actions, and Windows CPU/GPU measurements are included.
- Compatibility: worker and Godot spike stay isolated; existing pet package v1.0 and creator-specific motion scripts remain unchanged.
- Privacy/licensing: private paths stay on E: by default, reports redact identifying data, inference uses local model files, and model installation verifies licenses and hashes.
- Test coverage: invalid input, group photos, missing/corrupt models, inferred regions, privacy redaction, cancellation, layer confidence, rig bounds, preview status, and P0 evidence gates are pinned.
- Limitation: P0 cannot prove all 18 actions or the browser upload flow. It must supply evidence before their later plans and any complete-feature claim.
