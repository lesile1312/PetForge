from __future__ import annotations

import json
import hashlib
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw

from .corpus import EvalCase, EvalResult
from .device import DeviceProfile, peak_working_set_bytes, probe_device
from .preflight import ImageLimits, preflight_image
from .providers.base import (
    CancelToken,
    CutoutResult,
    GenerationCancelled,
    LayerAsset,
    LayerSet,
    PersonCandidate,
    PersonSelectionError,
    PortraitCandidate,
    PortraitRequest,
    ProviderError,
    resolve_person_selection,
)
from .providers.cutout import AlphaCutoutProvider
from .providers.portrait import DeterministicFakePortraitGenerator
from .pose_control import write_openpose_control


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _store_revision(stage_dir: Path, case_root: Path, state: str, revision_id: str) -> Path:
    destination = case_root / state / revision_id
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage_dir.replace(destination)
    return destination


def _infer_regions(person: PersonCandidate) -> tuple[str, ...]:
    inferred: list[str] = []
    def pair_visible(part: str) -> bool:
        return all(
            len(person.landmarks_norm.get(f"{side}_{part}", ())) >= 3
            and person.landmarks_norm[f"{side}_{part}"][2] >= 0.2
            for side in ("left", "right")
        )

    if not pair_visible("hip"):
        inferred.extend(("lower_body", "lower_clothing"))
    if not pair_visible("knee"):
        inferred.extend(("lower_body_pose", "lower_clothing"))
    if not pair_visible("ankle"):
        inferred.extend(("feet", "lower_body_pose"))
    return tuple(dict.fromkeys(inferred))


def run_case(
    case: EvalCase,
    *,
    detector,
    cutout,
    generator,
    segmenter,
    output_root: Path,
    cancel: CancelToken | None = None,
    device: DeviceProfile | None = None,
    reviewer: Callable[[PortraitCandidate], bool] | None = None,
    person_index: int | None = None,
    manual_crop_xywh_px: tuple[int, int, int, int] | None = None,
) -> EvalResult:
    """Run one private case and promote only an explicitly reviewed revision."""
    started = time.perf_counter()
    token = cancel or CancelToken()
    selected_device = device or probe_device(check_gpu=True)
    device_id = "cuda" if selected_device.gpu_name else "cpu"
    model_id = getattr(generator, "model_id", "unknown-model")
    case_root = Path(output_root) / "cases" / case.case_id
    revision_id = f"rev_{time.time_ns()}_{uuid.uuid4().hex[:8]}"
    stage_dir = case_root / ".staging" / revision_id
    stage_dir.mkdir(parents=True, exist_ok=False)
    stages = {
        "preflight": "skipped",
        "detection": "skipped",
        "candidate_pose": "skipped",
        "cutout": "skipped",
        "generation": "skipped",
        "layer_segmentation": "skipped",
        "review": "skipped",
    }
    local_context: dict[str, object] = {
        "revision_id": revision_id,
        "subject_type": case.subject_type,
        "photo_consent_confirmed": case.is_real_person and case.likeness_approved,
        "variation_tags": list(case.variation_tags),
        "owner_approved_character": False,
        "privacy_preflight_passed": False,
        "device_profile": selected_device.to_dict(),
        "model_evidence": getattr(generator, "model_evidence", {}),
    }
    stage_elapsed_ms: dict[str, int] = {}
    active_stage: str | None = None
    active_stage_started: float | None = None
    error_code: str | None = None
    correction_count = 0

    def start_stage(name: str) -> None:
        nonlocal active_stage, active_stage_started
        active_stage = name
        active_stage_started = time.perf_counter()

    def finish_stage() -> None:
        nonlocal active_stage, active_stage_started
        if active_stage is not None and active_stage_started is not None:
            stage_elapsed_ms[active_stage] = max(0, int((time.perf_counter() - active_stage_started) * 1000))
        active_stage = None
        active_stage_started = None

    def failed(code: str, outcome: str = "failed") -> EvalResult:
        nonlocal error_code
        finish_stage()
        error_code = code
        failed_path = _store_revision(stage_dir, case_root, "failed", revision_id)
        local_context["candidate_directory"] = str(failed_path)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        _write_eval_evidence(
            failed_path / "p0-eval-evidence.json", case, local_context, stages, stage_elapsed_ms,
            elapsed_ms, peak_working_set_bytes(), int(getattr(generator, "peak_gpu_memory_bytes", 0)) or None,
            correction_count, error_code,
        )
        return EvalResult(
            case_id=case.case_id,
            model_id=model_id,
            device_id=device_id,
            elapsed_ms=elapsed_ms,
            peak_memory_bytes=peak_working_set_bytes(),
            correction_count=correction_count,
            stages=dict(stages),
            error_code=error_code,
            private_context=local_context,
            stage_elapsed_ms=dict(stage_elapsed_ms),
            peak_gpu_memory_bytes=int(getattr(generator, "peak_gpu_memory_bytes", 0)) or None,
        )

    try:
        token.check()
        start_stage("preflight")
        suffix = Path(case.image_path).suffix.lower()
        sanitized_path = stage_dir / f"source.sanitized{suffix}"
        preflight = preflight_image(Path(case.image_path), sanitized_path, ImageLimits())
        finish_stage()
        if not preflight.ready:
            stages["preflight"] = "failed"
            return failed(preflight.error_code or "preflight_failed")
        stages["preflight"] = "passed"
        local_context["privacy_preflight_passed"] = True
        local_context["source_width"] = preflight.width
        local_context["source_height"] = preflight.height

        token.check()
        start_stage("detection")
        people = detector.detect(sanitized_path)
        with Image.open(sanitized_path) as sanitized:
            image_size = sanitized.size
        try:
            person = resolve_person_selection(
                people,
                index=person_index,
                crop_xywh_px=manual_crop_xywh_px,
                image_size=image_size,
            )
        except PersonSelectionError as error:
            stages["detection"] = "failed"
            return failed(error.code)
        finish_stage()
        stages["detection"] = "passed"
        local_context["selected_person_confidence"] = person.confidence
        local_context["person_count"] = len(people)
        local_context["person_candidates"] = [
            {"bbox_xywh_norm": list(candidate.bbox_xywh_norm), "confidence": candidate.confidence}
            for candidate in people
        ]

        token.check()
        start_stage("cutout")
        cutout_result: CutoutResult = cutout.cutout(sanitized_path, person, stage_dir / "cutout")
        finish_stage()
        if not cutout_result.ready or cutout_result.cutout_path is None:
            stages["cutout"] = "failed"
            return failed(cutout_result.error_code or "cutout_failed")
        stages["cutout"] = "passed"
        local_context["source_bounds_xyxy"] = list(cutout_result.source_bounds_xyxy or ())
        local_context["source_to_cutout"] = cutout_result.source_to_cutout

        token.check()
        start_stage("generation")
        inferred_regions = _infer_regions(person)
        pose_control_path = write_openpose_control("idle", (768, 1024), stage_dir / "generated" / "pose-control.png")
        request = PortraitRequest(
            source_path=cutout_result.cutout_path,
            selected_crop_xywh_norm=(0.0, 0.0, 1.0, 1.0),
            style_preset="warm_chibi",
            clothing_description=None,
            inferred_regions=inferred_regions,
            seed=int(time.time_ns() % (2**31 - 1)),
            pose_description=(
                "front-facing upright idle stand, arms relaxed at sides, both legs straight, both feet flat"
            ),
            pose_control_image=pose_control_path,
        )
        try:
            candidate = generator.generate(request, selected_device, stage_dir / "generated", token)
        except KeyboardInterrupt:
            token.cancel()
            stages["generation"] = "rejected"
            return failed("generation_cancelled")
        finish_stage()
        stages["generation"] = "passed"
        local_context["inferred_regions"] = list(candidate.inferred_regions)
        local_context["character_reference_id"] = _candidate_reference_id(candidate.image_path)

        token.check()
        start_stage("candidate_pose")
        generated_people = detector.detect(candidate.image_path)
        generated_person = max(generated_people, key=lambda item: item.confidence) if generated_people else None
        candidate_landmarks = generated_person.landmarks_norm if generated_person else {}
        finish_stage()
        stages["candidate_pose"] = "passed" if generated_person else "needs_review"
        local_context["candidate_pose_confidence"] = generated_person.confidence if generated_person else 0.0
        local_context["candidate_pose_landmarks"] = {
            name: list(value) for name, value in sorted(candidate_landmarks.items())
        }
        _write_json(
            stage_dir / "candidate-pose.json",
            {
                "schema_version": 1,
                "confidence": float(generated_person.confidence) if generated_person else 0.0,
                "landmarks_norm": local_context["candidate_pose_landmarks"],
            },
        )

        token.check()
        start_stage("layer_segmentation")
        layers = segmenter.segment(candidate, candidate_landmarks, stage_dir / "layers")
        finish_stage()
        if not isinstance(layers, LayerSet):
            stages["layer_segmentation"] = "failed"
            return failed("invalid_layer_set")
        _write_json(
            stage_dir / "layers" / "layer-confidence.json",
            {
                "assets": {
                    key: {"confidence": value.confidence, "inferred": value.inferred}
                    for key, value in sorted(layers.assets.items())
                },
                "missing_layers": list(layers.missing_layers),
            },
        )
        stages["layer_segmentation"] = "passed" if not layers.missing_layers else "needs_review"
        local_context["missing_layers"] = list(layers.missing_layers)

        token.check()
        start_stage("review")
        if reviewer is None:
            stages["review"] = "needs_review"
            state = "pending"
        elif reviewer(candidate) is True:
            stages["review"] = "passed"
            state = "revisions"
            local_context["owner_approved_character"] = True
        else:
            stages["review"] = "rejected"
            state = "rejected"
        finish_stage()

        revision_path = _store_revision(stage_dir, case_root, state, revision_id)
        _write_json(
            revision_path / "p0-candidate.json",
            {
                "schema_version": 1,
                "case_id": case.case_id,
                "character_reference_id": local_context["character_reference_id"],
                "revision_id": revision_id,
                "candidate_image": "generated/candidate.png",
                "candidate_mask": "generated/mask.png",
                "candidate_pose": "candidate-pose.json",
                "layer_directory": "layers",
                "layer_confidence": "layers/layer-confidence.json",
                "state": state,
                "accepted": state == "revisions",
            },
        )
        local_context["candidate_directory"] = str(revision_path)
        if state == "revisions":
            _write_json(case_root / "accepted.json", {"revision": f"revisions/{revision_id}"})
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        _write_eval_evidence(
            revision_path / "p0-eval-evidence.json", case, local_context, stages, stage_elapsed_ms,
            elapsed_ms, peak_working_set_bytes(), int(getattr(generator, "peak_gpu_memory_bytes", 0)) or None,
            correction_count, None,
        )
        return EvalResult(
            case_id=case.case_id,
            model_id=model_id,
            device_id=device_id,
            elapsed_ms=elapsed_ms,
            peak_memory_bytes=peak_working_set_bytes(),
            correction_count=correction_count,
            stages=dict(stages),
            private_context=local_context,
            stage_elapsed_ms=dict(stage_elapsed_ms),
            peak_gpu_memory_bytes=int(getattr(generator, "peak_gpu_memory_bytes", 0)) or None,
        )
    except GenerationCancelled as error:
        if active_stage:
            stages[active_stage] = "rejected"
        stages["review"] = "skipped"
        return failed(error.code)
    except ProviderError as error:
        failing_stage = active_stage or "generation"
        stages[failing_stage] = "failed"
        return failed(error.code)
    except Exception:
        failing_stage = active_stage or "generation"
        stages[failing_stage] = "failed"
        return failed(f"{failing_stage}_failed")


def _candidate_reference_id(image_path: Path) -> str:
    digest = hashlib.sha256()
    with Path(image_path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:24]


def _write_eval_evidence(
    path: Path,
    case: EvalCase,
    local_context: dict[str, object],
    stages: dict[str, str],
    stage_elapsed_ms: dict[str, int],
    elapsed_ms: int,
    peak_memory_bytes: int,
    peak_gpu_memory_bytes: int | None,
    correction_count: int,
    error_code: str | None,
) -> None:
    """Keep only local P0 gate evidence; omit all paths, prompts, and source content."""
    _write_json(
        path,
        {
            "schema_version": 1,
            "case_id": case.case_id,
            "subject_type": case.subject_type,
            "photo_consent_confirmed": bool(local_context.get("photo_consent_confirmed")),
            "variation_tags": list(case.variation_tags),
            "owner_approved_character": bool(local_context.get("owner_approved_character")),
            "character_reference_id": local_context.get("character_reference_id"),
            "privacy_preflight_passed": bool(local_context.get("privacy_preflight_passed")),
            "device_profile": local_context.get("device_profile", {}),
            "model_evidence": local_context.get("model_evidence", {}),
            "elapsed_ms": elapsed_ms,
            "stage_elapsed_ms": dict(stage_elapsed_ms),
            "peak_memory_bytes": peak_memory_bytes,
            "peak_gpu_memory_bytes": peak_gpu_memory_bytes,
            "correction_count": correction_count,
            "stages": dict(stages),
            "error_code": error_code,
        },
    )


class DeterministicFakePersonDetector:
    def detect(self, source_path: Path) -> list[PersonCandidate]:
        with Image.open(source_path) as image:
            width, height = image.size
        landmarks = {
            "nose": (0.5, 0.18, 0.9),
            "left_shoulder": (0.38, 0.32, 0.9),
            "right_shoulder": (0.62, 0.32, 0.9),
            "left_elbow": (0.25, 0.47, 0.85),
            "right_elbow": (0.75, 0.47, 0.85),
            "left_wrist": (0.2, 0.59, 0.85),
            "right_wrist": (0.8, 0.59, 0.85),
            "left_hip": (0.42, 0.63, 0.9),
            "right_hip": (0.58, 0.63, 0.9),
            "left_knee": (0.42, 0.8, 0.85),
            "right_knee": (0.58, 0.8, 0.85),
            "left_ankle": (0.42, 0.94, 0.85),
            "right_ankle": (0.58, 0.94, 0.85),
            "left_ear": (0.43, 0.18, 0.8),
            "right_ear": (0.57, 0.18, 0.8),
            "left_eye": (0.47, 0.17, 0.8),
            "right_eye": (0.53, 0.17, 0.8),
        }
        if width <= 0 or height <= 0:
            return []
        return [PersonCandidate((0.15, 0.04, 0.7, 0.92), landmarks, 0.9)]


class DeterministicFakeCutoutProvider:
    def cutout(self, source_path: Path, selected_person: PersonCandidate, output_dir: Path) -> CutoutResult:
        with Image.open(source_path) as image:
            width, height = image.size
        return AlphaCutoutProvider(lambda crop: Image.new("L", crop.size, 255)).cutout(
            source_path, selected_person, output_dir
        )


class DeterministicFakeLayerSegmenter:
    def segment(self, candidate: PortraitCandidate, landmarks_norm, output_dir: Path) -> LayerSet:
        del landmarks_norm
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        assets: dict[str, LayerAsset] = {}
        for layer_id in ("torso", "left_arm", "right_arm", "left_leg", "right_leg", "face", "hair", "eyes"):
            path = root / f"{layer_id}.png"
            shutil.copyfile(candidate.image_path, path)
            assets[layer_id] = LayerAsset(path, confidence=0.9, inferred=layer_id in {"hair", "eyes"})
        return LayerSet(assets, ())


class FailingPortraitGenerator:
    model_id = "failing-test-model"

    def generate(
        self, request: PortraitRequest, device: DeviceProfile, output_dir: Path, cancel: CancelToken | None = None
    ) -> PortraitCandidate:
        del request, device, output_dir, cancel
        raise ProviderError("generation_failed")
