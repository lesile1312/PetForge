from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import replace
from pathlib import Path

from .benchmark import run_case
from .corpus import EvalCase, default_eval_root, load_eval_cases
from .device import DeviceProfile, probe_device
from .manifest import validate_manifest
from .providers.base import CancelToken, GenerationCancelled
from .providers.cutout import AlphaCutoutProvider, RemBgBiRefNetPortrait, rembg_model_path
from .providers.layers import GeometricLayerSegmenter
from .providers.person import MediaPipePersonDetector
from .providers.portrait import LocalSDXLPortraitGenerator
from .report import write_eval_report
from .providers.base import LayerAsset, LayerSet, PortraitCandidate
from .rig_seed import Landmark, LandmarkCorrection, SUPPORTED_JOINTS, seed_rig
from .action_pose import ActionPoseCandidate, ActionPreview, generate_action_pose, render_action_preview
from .p0_gate import evaluate_p0, load_local_p0_evidence, write_p0_gate_report
from PIL import Image, ImageChops, ImageDraw


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_model_root() -> Path:
    return Path(os.environ.get("PETFORGE_MODEL_ROOT", r"E:\PetForge\models"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="petforge-worker", description="Local-only PetForge photo generation P0.")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check-models", help="verify local model versions, sizes, licenses, and checksums")
    check.add_argument("--model-root", type=Path, default=default_model_root())
    check.add_argument("--manifest", type=Path, default=repo_root() / "models" / "manifest.json")

    generate = commands.add_parser("generate", help="generate and review one local photo character")
    generate.add_argument("--input", type=Path, required=True)
    selection = generate.add_mutually_exclusive_group()
    selection.add_argument("--person-index", type=int)
    selection.add_argument("--crop", help="manual source crop in pixels: x,y,width,height")
    generate.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    generate.add_argument("--model-root", type=Path, default=default_model_root())
    generate.add_argument("--output-root", type=Path, default=default_eval_root())
    generate.add_argument("--consent", action="store_true", help="confirm local processing rights and consent")
    generate.add_argument("--seed", type=int, default=20261029)

    benchmark = commands.add_parser("benchmark", help="run consented local cases and write a redacted report")
    benchmark.add_argument("--root", type=Path, required=True)
    benchmark.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    benchmark.add_argument("--model-root", type=Path, default=default_model_root())
    benchmark.add_argument("--output", type=Path)

    review = commands.add_parser("review-candidate", help="accept or reject an existing pending local character")
    review.add_argument("--candidate-dir", type=Path, required=True)
    review.add_argument("--decision", choices=("accept", "reject"), required=True)

    preview = commands.add_parser("preview-actions", help="build the isolated local five-action Godot preview")
    preview.add_argument("--candidate-dir", type=Path, required=True)
    preview.add_argument("--output-dir", type=Path)
    preview.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    preview.add_argument("--model-root", type=Path, default=default_model_root())
    preview.add_argument(
        "--correction",
        action="append",
        default=[],
        metavar="JOINT=DX,DY",
        help="adjust a normalized joint by at most 0.05 in either direction; repeat for multiple joints",
    )

    gate = commands.add_parser("evaluate-p0", help="evaluate the local P0 evidence gate and write a redacted report")
    gate.add_argument("--evidence-root", type=Path, default=default_eval_root())
    gate.add_argument("--output", type=Path, default=default_eval_root() / "reports" / "p0-gate.json")
    return parser


def _crop_arg(value: str | None) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    try:
        parts = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as error:
        raise ValueError("crop_must_be_x_y_width_height") from error
    if len(parts) != 4:
        raise ValueError("crop_must_be_x_y_width_height")
    return parts  # type: ignore[return-value]


def _device_profile(mode: str) -> DeviceProfile:
    profile = probe_device(check_gpu=(mode != "cpu"))
    if mode == "cuda" and profile.gpu_name is None:
        raise RuntimeError("nvidia_gpu_not_detected")
    if mode == "cpu" and profile.gpu_name is not None:
        return replace(profile, gpu_name=None, gpu_memory_bytes=None, gpu_driver_version=None)
    return profile


def _model_state(model_root: Path, manifest_path: Path):
    return validate_manifest(manifest_path, model_root)


def _print_model_state(model_root: Path, manifest_path: Path) -> int:
    result = _model_state(model_root, manifest_path)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ready else 2


def _providers(model_root: Path, mode: str):
    detector = MediaPipePersonDetector(model_root / "mediapipe" / "pose_landmarker_full.task")
    mask_predictor = RemBgBiRefNetPortrait(rembg_model_path(model_root))
    return (
        detector,
        AlphaCutoutProvider(mask_predictor),
        LocalSDXLPortraitGenerator(model_root, mask_predictor, device_mode=mode),
        GeometricLayerSegmenter(),
    )


def _review(candidate) -> bool:
    print(f"Review candidate: {candidate.image_path}")
    print("Generated character and intermediate files stay in the local output folder.")
    return input("Accept this character? [y/N] ").strip().lower() in {"y", "yes"}


def _print_result(result) -> None:
    print(json.dumps(
        {
            "case_id": result.case_id,
            "model_id": result.model_id,
            "device_id": result.device_id,
            "elapsed_ms": result.elapsed_ms,
            "peak_memory_bytes": result.peak_memory_bytes,
            "peak_gpu_memory_bytes": result.peak_gpu_memory_bytes,
            "stage_elapsed_ms": result.stage_elapsed_ms,
            "stages": result.stages,
            "error_code": result.error_code,
            "candidate_directory": (result.private_context or {}).get("candidate_directory"),
        },
        ensure_ascii=False,
        indent=2,
    ))


def _generate(args: argparse.Namespace) -> int:
    if not args.consent:
        print("Pass --consent after confirming local photo-processing rights and consent.", file=sys.stderr)
        return 2
    if not args.input.is_file():
        print("Photo file does not exist.", file=sys.stderr)
        return 2
    try:
        manual_crop = _crop_arg(args.crop)
        device = _device_profile(args.device)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2

    manifest_path = repo_root() / "models" / "manifest.json"
    if _print_model_state(args.model_root, manifest_path) != 0:
        return 2
    detector, cutout, generator, segmenter = _providers(args.model_root, args.device)
    case_id = f"case_{uuid.uuid4().hex[:16]}"
    case = EvalCase(case_id, args.input.resolve(), "real_person", True, True)
    cancel = CancelToken()
    try:
        result = run_case(
            case,
            detector=detector,
            cutout=cutout,
            generator=generator,
            segmenter=segmenter,
            output_root=args.output_root,
            cancel=cancel,
            device=device,
            reviewer=_review,
            person_index=args.person_index,
            manual_crop_xywh_px=manual_crop,
        )
    except KeyboardInterrupt:
        cancel.cancel()
        print("Cancellation requested. Diffusion stops at the next step boundary.", file=sys.stderr)
        return 130
    _print_result(result)
    if result.error_code == "person_selection_required":
        people = (result.private_context or {}).get("person_candidates", [])
        print("This photo contains multiple detected people. Rerun with --person-index <0-based-index>.")
        print(json.dumps(people, ensure_ascii=False, indent=2))
    elif result.error_code == "person_not_detected":
        print("Pose detection found no person. Rerun with --crop x,y,width,height in source-image pixels.")
    if result.error_code:
        return 1
    return 0


def _benchmark(args: argparse.Namespace) -> int:
    device = _device_profile(args.device)
    manifest_path = repo_root() / "models" / "manifest.json"
    if _print_model_state(args.model_root, manifest_path) != 0:
        return 2
    try:
        cases = load_eval_cases(args.root)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    detector, cutout, generator, segmenter = _providers(args.model_root, args.device)
    cancel = CancelToken()
    results = []
    interrupted = False
    try:
        for case in cases:
            result = run_case(
                case,
                detector=detector,
                cutout=cutout,
                generator=generator,
                segmenter=segmenter,
                output_root=default_eval_root() / "benchmark-output",
                cancel=cancel,
                device=device,
            )
            results.append(result)
            if result.error_code == "generation_cancelled":
                interrupted = True
                break
    except KeyboardInterrupt:
        cancel.cancel()
        interrupted = True
    report_path = args.output or (args.root / "reports" / "p0-report.json")
    write_eval_report(results, report_path)
    print(f"Redacted report: {report_path}")
    for result in results:
        _print_result(result)
    if interrupted:
        return 130
    return 1 if any(result.error_code for result in results) else 0


def _parse_landmark_corrections(values: list[str]) -> list[LandmarkCorrection]:
    corrections: list[LandmarkCorrection] = []
    seen: set[str] = set()
    for value in values:
        try:
            name, offsets = value.split("=", maxsplit=1)
            dx_raw, dy_raw = offsets.split(",", maxsplit=1)
            dx, dy = float(dx_raw), float(dy_raw)
        except (ValueError, AttributeError) as error:
            raise ValueError("correction_must_be_joint_dx_dy") from error
        if name not in SUPPORTED_JOINTS or name in seen or not all(-0.05 <= offset <= 0.05 for offset in (dx, dy)):
            raise ValueError("invalid_landmark_correction")
        seen.add(name)
        corrections.append(LandmarkCorrection(name, dx, dy))
    return corrections


def _load_reviewable_candidate(candidate_dir: Path, corrections: list[LandmarkCorrection] | None = None):
    root = Path(candidate_dir).resolve()
    try:
        metadata = json.loads((root / "p0-candidate.json").read_text(encoding="utf-8"))
        if metadata.get("schema_version") != 1 or metadata.get("state") not in {"pending", "revisions"}:
            raise ValueError("candidate_not_reviewable")
        image_path = (root / metadata["candidate_image"]).resolve()
        mask_path = (root / metadata["candidate_mask"]).resolve()
        image_path.relative_to(root)
        mask_path.relative_to(root)
        pose_doc = json.loads((root / metadata["candidate_pose"]).read_text(encoding="utf-8"))
        confidence_doc = json.loads((root / metadata["layer_confidence"]).read_text(encoding="utf-8"))
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("candidate_manifest_invalid") from error
    provenance_path = image_path.with_name("provenance.json")
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        provenance = {}
    candidate = PortraitCandidate(image_path, mask_path, tuple(provenance.get("inferred_regions", [])), provenance)
    layer_root = (root / metadata["layer_directory"]).resolve()
    layer_root.relative_to(root)
    assets: dict[str, LayerAsset] = {}
    for name, details in confidence_doc.get("assets", {}).items():
        path = (layer_root / f"{name}.png").resolve()
        path.relative_to(root)
        if path.is_file() and isinstance(details, dict):
            assets[name] = LayerAsset(path, float(details.get("confidence", 0.0)), bool(details.get("inferred", False)))
    layers = LayerSet(assets, tuple(confidence_doc.get("missing_layers", [])))
    raw_landmarks = pose_doc.get("landmarks_norm", {})
    landmarks = [Landmark(name, float(values[0]), float(values[1]), float(values[2]) if len(values) > 2 else 0.0)
                 for name, values in raw_landmarks.items()
                 if name in SUPPORTED_JOINTS and isinstance(values, list) and len(values) >= 2]
    rig = seed_rig(candidate, landmarks, corrections=corrections, layers=layers)
    return root, candidate, rig


def _write_local_json(path: Path, payload: dict[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)


def _review_candidate(args: argparse.Namespace) -> int:
    try:
        candidate_root, candidate, rig = _load_reviewable_candidate(args.candidate_dir)
        del candidate, rig
        metadata_path = candidate_root / "p0-candidate.json"
        evidence_path = candidate_root / "p0-eval-evidence.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError, ValueError) as error:
        print(str(error) if str(error).isidentifier() else "candidate_review_evidence_invalid", file=sys.stderr)
        return 2

    case_id = metadata.get("case_id")
    revision_id = metadata.get("revision_id")
    reference_id = metadata.get("character_reference_id")
    stages = evidence.get("stages")
    if (
        candidate_root.parent.name != "pending"
        or candidate_root.name != revision_id
        or metadata.get("state") != "pending"
        or metadata.get("accepted") is not False
        or not isinstance(case_id, str)
        or re.fullmatch(r"case_[a-f0-9]{8,32}", case_id) is None
        or not isinstance(revision_id, str)
        or re.fullmatch(r"rev_[0-9]+_[a-f0-9]{8}", revision_id) is None
        or evidence.get("schema_version") != 1
        or evidence.get("case_id") != case_id
        or evidence.get("character_reference_id") != reference_id
        or evidence.get("subject_type") != "real_person"
        or evidence.get("photo_consent_confirmed") is not True
        or evidence.get("privacy_preflight_passed") is not True
        or evidence.get("owner_approved_character") is not False
        or not isinstance(stages, dict)
        or stages.get("review") != "needs_review"
    ):
        print("candidate_not_pending_review", file=sys.stderr)
        return 2

    case_root = candidate_root.parent.parent
    accepted = args.decision == "accept"
    target_state = "revisions" if accepted else "rejected"
    destination = case_root / target_state / revision_id
    if destination.exists():
        print("candidate_review_destination_exists", file=sys.stderr)
        return 2
    destination.parent.mkdir(parents=True, exist_ok=True)
    candidate_root.replace(destination)

    metadata["state"] = target_state
    metadata["accepted"] = accepted
    stages["review"] = "passed" if accepted else "rejected"
    evidence["owner_approved_character"] = accepted
    _write_local_json(destination / "p0-candidate.json", metadata)
    _write_local_json(destination / "p0-eval-evidence.json", evidence)
    if accepted:
        _write_local_json(case_root / "accepted.json", {"revision": f"revisions/{revision_id}"})

    print(json.dumps({
        "decision": args.decision,
        "case_id": case_id,
        "character_reference_id": reference_id,
        "candidate_directory": str(destination),
    }, ensure_ascii=False, indent=2))
    return 0


def _write_contact_sheet(output_dir: Path, previews: list[ActionPreview], canvas_size: tuple[int, int]) -> Path:
    thumb_width = 220
    thumb_height = max(180, round(thumb_width * canvas_size[1] / canvas_size[0]))
    label_height = 36
    sheet = Image.new("RGBA", (thumb_width * 3, (thumb_height + label_height) * 5), (250, 247, 243, 255))
    draw = ImageDraw.Draw(sheet)
    for row, preview in enumerate(previews):
        draw.text((8, row * (thumb_height + label_height) + 8), f"{preview.action_id} · {preview.status}", fill=(45, 38, 34, 255))
        if not preview.frame_paths:
            draw.text((12, row * (thumb_height + label_height) + label_height + 12), ", ".join(preview.issues) or "no frames", fill=(125, 58, 48, 255))
            continue
        for column, frame_index in enumerate((0, len(preview.frame_paths) // 2, len(preview.frame_paths) - 1)):
            with Image.open(preview.frame_paths[frame_index]) as frame_file:
                frame = frame_file.convert("RGBA")
            frame.thumbnail((thumb_width - 12, thumb_height - 12), Image.Resampling.LANCZOS)
            x = column * thumb_width + (thumb_width - frame.width) // 2
            y = row * (thumb_height + label_height) + label_height + (thumb_height - frame.height) // 2
            sheet.alpha_composite(frame, (x, y))
            frame.close()
    path = output_dir / "contact-sheet.png"
    sheet.save(path, format="PNG")
    sheet.close()
    return path


def _write_rig_manifest(candidate: PortraitCandidate, rig, output_dir: Path, manifest_root: Path) -> str:
    from PIL import Image, ImageChops

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    with Image.open(candidate.image_path) as source_file:
        image = source_file.convert("RGBA")
    width, height = image.size
    removed = Image.new("L", image.size, 0)
    layers: dict[str, dict[str, object]] = {}
    pivots = {
        "left_arm": "left_shoulder",
        "right_arm": "right_shoulder",
        "left_leg": "left_hip",
        "right_leg": "right_hip",
    }
    for layer_id, pivot_name in pivots.items():
        layer_path = rig.layer_refs.get(layer_id)
        if layer_path is None or not layer_path.is_file():
            continue
        with Image.open(layer_path) as layer_file:
            layer = layer_file.convert("RGBA")
        alpha = layer.getchannel("A")
        if alpha.size != image.size or alpha.getbbox() is None:
            alpha.close()
            layer.close()
            continue
        next_removed = ImageChops.lighter(removed, alpha)
        removed.close()
        removed = next_removed
        relative_layer = Path(os.path.relpath(layer_path.resolve(), Path(manifest_root).resolve())).as_posix()
        layers[layer_id] = {"path": relative_layer, "pivot": pivot_name}
        alpha.close()
        layer.close()

    eyes_path = rig.layer_refs.get("eyes")
    if eyes_path is not None and eyes_path.is_file():
        with Image.open(eyes_path) as eyes_file:
            eyes = eyes_file.convert("RGBA")
        eyes_alpha = eyes.getchannel("A")
        bounds = eyes_alpha.getbbox()
        if bounds is not None:
            padding = 3
            left = max(0, bounds[0] - padding)
            top = max(0, bounds[1] - padding)
            right = min(width, bounds[2] + padding)
            bottom = min(height, bounds[3] + padding)
            eyes_crop = eyes.crop((left, top, right, bottom))
            eyes_alpha_crop = eyes_crop.getchannel("A")
            next_removed = ImageChops.lighter(removed, eyes_alpha)
            removed.close()
            removed = next_removed
            eyes_crop_path = root / "eyes.png"
            eyes_crop.save(eyes_crop_path, format="PNG", optimize=True)
            layers["eyes"] = {
                "path": Path(os.path.relpath(eyes_crop_path.resolve(), Path(manifest_root).resolve())).as_posix(),
                "offset_norm": [(left + eyes_crop.width / 2) / width, (top + eyes_crop.height / 2) / height],
            }
            eyes_alpha_crop.close()
            eyes_crop.close()
        eyes_alpha.close()
        eyes.close()
    alpha = image.getchannel("A")
    body_alpha = ImageChops.subtract(alpha, removed)
    body = image.copy()
    body.putalpha(body_alpha)
    body_path = root / "base-body.png"
    body.save(body_path, format="PNG", optimize=True)
    body.close()
    alpha.close()
    body_alpha.close()
    removed.close()
    image.close()

    payload = {
        "schema_version": 1,
        "character_reference_id": rig.character_reference_id,
        "canvas_size": [width, height],
        "base_body": Path(os.path.relpath(body_path.resolve(), Path(manifest_root).resolve())).as_posix(),
        "joints_norm": {name: [joint.x, joint.y, joint.confidence] for name, joint in sorted(rig.joints.items())},
        "editable_joints": list(rig.editable_joints),
        "layers": layers,
    }
    manifest_path = root / "rig.json"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return Path(os.path.relpath(manifest_path.resolve(), Path(manifest_root).resolve())).as_posix()


def _require_generated_pose_rig(preview: ActionPreview, action_rig_paths: dict[str, str]) -> ActionPreview:
    if preview.action_id not in {"wave_smile", "phone_crouch"} or preview.action_id in action_rig_paths:
        return preview
    if preview.status != "ready":
        return preview
    return replace(
        preview,
        status="needs_fix",
        issues=tuple(dict.fromkeys((*preview.issues, "key_pose_rig_unavailable"))),
    )


def _preview_actions(args: argparse.Namespace) -> int:
    manifest_path = repo_root() / "models" / "manifest.json"
    if _print_model_state(args.model_root, manifest_path) != 0:
        return 2
    try:
        corrections = _parse_landmark_corrections(args.correction)
        candidate_root, candidate, rig = _load_reviewable_candidate(args.candidate_dir, corrections)
        device = _device_profile(args.device)
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    output_dir = Path(args.output_dir).resolve() if args.output_dir else candidate_root / "p0-actions"
    output_dir.mkdir(parents=True, exist_ok=True)
    if rig.status != "ready":
        print(json.dumps({
            "status": "unsupported",
            "issues": list(rig.issues),
            "missing_layers": rig.missing_layers,
            "missing_joints": rig.missing_joints,
        }, indent=2))
        return 1

    detector, _, generator, _ = _providers(args.model_root, args.device)
    segmenter = GeometricLayerSegmenter()
    cancel = CancelToken()
    previews: list[ActionPreview] = []
    action_poses: dict[str, ActionPoseCandidate] = {}
    for action_id in ("wave_smile", "phone_crouch"):
        try:
            action_poses[action_id] = generate_action_pose(
                candidate,
                rig,
                action_id,
                generator=generator,
                detector=detector,
                device=device,
                output_dir=output_dir / "key-poses" / action_id,
                cancel=cancel,
            )
        except KeyboardInterrupt:
            cancel.cancel()
            print("Cancellation requested. Current model step will finish before stopping.", file=sys.stderr)
            return 130
        except GenerationCancelled:
            print("Generation cancelled. Private inputs and completed intermediates were retained.", file=sys.stderr)
            return 130
        except Exception as error:
            code = getattr(error, "code", None) or (str(error) if str(error).isidentifier() else "key_pose_generation_failed")
            action_poses[action_id] = ActionPoseCandidate(rig.character_reference_id, action_id, {}, Path(), (code,))

    source_rig_path = _write_rig_manifest(candidate, rig, output_dir / "rig" / "source", output_dir)
    action_rig_paths: dict[str, str] = {}
    for action_id, pose in action_poses.items():
        if pose.issues or not Path(pose.image_path).is_file():
            continue
        pose_candidate = PortraitCandidate(
            Path(pose.image_path),
            Path(pose.image_path).with_name("mask.png"),
            candidate.inferred_regions,
        )
        pose_layers = segmenter.segment(
            pose_candidate,
            pose.landmarks_norm,
            output_dir / "rig" / "key-poses" / action_id / "layers",
        )
        pose_landmarks = [
            Landmark(name, float(values[0]), float(values[1]), float(values[2]) if len(values) > 2 else 0.0)
            for name, values in pose.landmarks_norm.items()
            if len(values) >= 2
        ]
        pose_rig = seed_rig(pose_candidate, pose_landmarks, layers=pose_layers)
        if pose_rig.status == "ready":
            action_rig_paths[action_id] = _write_rig_manifest(
                pose_candidate, pose_rig, output_dir / "rig" / "key-poses" / action_id, output_dir
            )

    case_id = _read_candidate_case_id(candidate_root)

    for action_id in ("idle", "run_left", "run_right", "wave_smile", "phone_crouch"):
        key_pose = action_poses.get(action_id)
        preview = render_action_preview(
            candidate,
            rig,
            action_id,
            key_pose=key_pose,
            output_dir=output_dir / "frames" / action_id,
            case_id=case_id,
        )
        preview = _require_generated_pose_rig(preview, action_rig_paths)
        previews.append(preview)

    with Image.open(candidate.image_path) as candidate_image:
        canvas_size = list(candidate_image.size)
    manifest = {
        "schema_version": 1,
        "case_id": case_id,
        "character_reference_id": rig.character_reference_id,
        "fps_target": 60,
        "canvas_size": canvas_size,
        "rig_manifest": source_rig_path,
        "landmark_corrections": [
            {"joint": item.name, "dx": item.dx, "dy": item.dy} for item in corrections
        ],
        "correction_count": len(corrections),
        "actions": [
            {
                "action_id": preview.action_id,
                "case_id": preview.case_id,
                "key_pose_rig_manifest": action_rig_paths.get(preview.action_id),
                "pose_control_path": (
                    action_poses[preview.action_id].control_image_path.relative_to(output_dir).as_posix()
                    if preview.action_id in action_poses and action_poses[preview.action_id].control_image_path
                    else None
                ),
                "status": preview.status,
                "duration_seconds": preview.duration_seconds,
                "fps_target": preview.fps_target,
                "frame_paths": [path.relative_to(output_dir).as_posix() for path in preview.frame_paths],
                "issues": list(preview.issues),
                "reviewed": False,
                "defects": [],
            }
            for preview in previews
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    contact_sheet = _write_contact_sheet(output_dir, previews, tuple(canvas_size))
    print(json.dumps({"manifest": str(output_dir / "manifest.json"), "contact_sheet": str(contact_sheet), "character_reference_id": rig.character_reference_id, "actions": [{"action_id": item.action_id, "status": item.status, "issues": list(item.issues)} for item in previews]}, ensure_ascii=False, indent=2))
    return 0


def _evaluate_p0(args: argparse.Namespace) -> int:
    try:
        results, previews = load_local_p0_evidence(args.evidence_root)
        report = evaluate_p0(results, previews)
        report_path = write_p0_gate_report(report, args.output)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps({**report.to_dict(), "report_path": str(report_path)}, ensure_ascii=False, indent=2))
    return {"pass": 0, "incomplete_samples": 1, "fail": 2}[report.status]


def _read_candidate_case_id(candidate_root: Path) -> str:
    try:
        metadata = json.loads((candidate_root / "p0-candidate.json").read_text(encoding="utf-8"))
        case_id = metadata.get("case_id")
    except (OSError, json.JSONDecodeError):
        raise ValueError("candidate_manifest_invalid")
    if not isinstance(case_id, str) or re.fullmatch(r"case_[a-f0-9]{8,32}", case_id) is None:
        raise ValueError("candidate_case_id_invalid")
    return case_id


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "check-models":
        return _print_model_state(args.model_root, args.manifest)
    if args.command == "generate":
        return _generate(args)
    if args.command == "benchmark":
        return _benchmark(args)
    if args.command == "review-candidate":
        return _review_candidate(args)
    if args.command == "preview-actions":
        return _preview_actions(args)
    if args.command == "evaluate-p0":
        return _evaluate_p0(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
