from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import urlparse

from .action_pose import ActionPreview
from .corpus import EvalResult


_REQUIRED_ACTIONS = {"idle", "run_left", "run_right", "wave_smile", "phone_crouch"}
_REQUIRED_LICENSES = {
    "sdxl-base-1.0",
    "ip-adapter-plus-sdxl-vit-h",
    "t2i-adapter-openpose-sdxl-1.0",
    "birefnet-portrait-cutout",
    "mediapipe-pose-full",
}
_GIB = 1024**3
_REQUIRED_STAGES = {"preflight", "detection", "cutout", "generation", "candidate_pose", "layer_segmentation", "review"}
_SAFE_CASE_ID = re.compile(r"case_[a-f0-9]{8,32}\Z")
_SAFE_CHARACTER_ID = re.compile(r"[a-f0-9]{24}\Z")


@dataclass(frozen=True, slots=True)
class P0GateReport:
    status: str
    real_case_count: int
    variation_category_count: int
    approved_character_count: int
    reviewed_action_count: int
    missing_evidence: tuple[str, ...]
    failure_codes: tuple[str, ...]
    case_ids: tuple[str, ...]
    character_reference_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for key in ("missing_evidence", "failure_codes", "case_ids", "character_reference_ids"):
            payload[key] = list(payload[key])
        return payload


def evaluate_p0(results: list[EvalResult], action_previews: list[ActionPreview]) -> P0GateReport:
    if not isinstance(results, list) or any(not isinstance(item, EvalResult) for item in results):
        raise ValueError("invalid_gate_results")
    if not isinstance(action_previews, list) or any(not isinstance(item, ActionPreview) for item in action_previews):
        raise ValueError("invalid_gate_action_previews")

    by_case: dict[str, EvalResult] = {}
    failures: set[str] = set()
    missing: set[str] = set()
    for result in results:
        if result.case_id in by_case:
            failures.add("duplicate_case_evidence")
        if not isinstance(result.case_id, str) or _SAFE_CASE_ID.fullmatch(result.case_id) is None:
            failures.add("case_id_not_pseudonymous")
        by_case[result.case_id] = result
        context = result.private_context or {}
        if result.error_code:
            failures.add("photo_pipeline_failed")
        if result.stages.get("review") == "rejected":
            failures.add("character_review_rejected")
        if context.get("subject_type") == "real_person" and context.get("photo_consent_confirmed") is not True:
            failures.add("real_photo_consent_missing")
        if context.get("privacy_preflight_passed") is not True:
            failures.add("privacy_preflight_failed")

        if result.elapsed_ms <= 0 or result.peak_memory_bytes <= 0 or result.correction_count < 0:
            missing.add("measured_time_memory_and_corrections")
        if result.stage_elapsed_ms is None or not _REQUIRED_STAGES.issubset(result.stage_elapsed_ms):
            missing.add("complete_stage_timings")

        model_evidence = context.get("model_evidence")
        if not _valid_model_evidence(model_evidence):
            failures.add("model_license_evidence_missing")
        if result.device_id == "cpu" and _is_16_gib_windows_x64(context.get("device_profile")):
            pass
        elif result.device_id == "cuda" and _has_supported_gpu(context.get("device_profile"), result.peak_gpu_memory_bytes):
            pass

    real_cases = {
        case_id: result
        for case_id, result in by_case.items()
        if (result.private_context or {}).get("subject_type") == "real_person"
        and (result.private_context or {}).get("photo_consent_confirmed") is True
    }
    variation_tags = {
        tag
        for result in real_cases.values()
        for tag in (result.private_context or {}).get("variation_tags", [])
        if isinstance(tag, str)
    }
    if len(real_cases) < 6:
        missing.add("six_consented_real_cases")
    if len(real_cases) >= 6 and len(variation_tags) < 3:
        missing.add("varied_real_cases")

    cpu_run = any(
        result.device_id == "cpu" and _is_16_gib_windows_x64((result.private_context or {}).get("device_profile"))
        for result in results
    )
    gpu_run = any(
        result.device_id == "cuda"
        and _has_supported_gpu((result.private_context or {}).get("device_profile"), result.peak_gpu_memory_bytes)
        for result in results
    )
    if not cpu_run:
        missing.add("sixteen_gib_cpu_run")
    if not gpu_run:
        missing.add("supported_discrete_gpu_run")

    approved: dict[str, EvalResult] = {}
    for case_id, result in real_cases.items():
        context = result.private_context or {}
        reference_id = context.get("character_reference_id")
        if (
            result.stages.get("review") == "passed"
            and context.get("owner_approved_character") is True
            and isinstance(reference_id, str)
            and _SAFE_CHARACTER_ID.fullmatch(reference_id) is not None
        ):
            approved[case_id] = result
    approved_character_ids = {
        str((result.private_context or {}).get("character_reference_id")) for result in approved.values()
    }
    if len(approved_character_ids) < 2:
        missing.add("two_reviewed_characters")

    preview_by_character: dict[tuple[str, str], dict[str, ActionPreview]] = {}
    reviewed_count = 0
    for preview in action_previews:
        if preview.action_id not in _REQUIRED_ACTIONS:
            failures.add("unknown_action_preview")
            continue
        if preview.reviewed and (preview.status != "ready" or preview.defects):
            failures.add("reviewed_action_failed")
        if not isinstance(preview.case_id, str) or _SAFE_CASE_ID.fullmatch(preview.case_id) is None:
            if preview.reviewed:
                failures.add("case_id_not_pseudonymous")
            continue
        if preview.case_id not in approved:
            if preview.reviewed:
                failures.add("action_for_unapproved_character")
            continue
        expected_reference_id = (approved[preview.case_id].private_context or {}).get("character_reference_id")
        if (
            not isinstance(preview.character_reference_id, str)
            or _SAFE_CHARACTER_ID.fullmatch(preview.character_reference_id) is None
            or preview.character_reference_id != expected_reference_id
        ):
            failures.add("action_character_reference_mismatch")
            continue
        group = preview_by_character.setdefault((preview.case_id, preview.character_reference_id), {})
        if preview.action_id in group:
            failures.add("duplicate_action_preview")
        group[preview.action_id] = preview
        if preview.reviewed and preview.status == "ready" and not preview.defects:
            reviewed_count += 1

    reviewed_characters = 0
    for case_id in approved:
        reference_id = str((approved[case_id].private_context or {}).get("character_reference_id"))
        previews = preview_by_character.get((case_id, reference_id), {})
        if _REQUIRED_ACTIONS.issubset(previews) and all(
            previews[action].reviewed and previews[action].status == "ready" and not previews[action].defects
            for action in _REQUIRED_ACTIONS
        ):
            reviewed_characters += 1
    if reviewed_characters < 2:
        missing.add("ten_reviewed_action_previews")

    status = "fail" if failures else ("incomplete_samples" if missing else "pass")
    return P0GateReport(
        status=status,
        real_case_count=len(real_cases),
        variation_category_count=len(variation_tags),
        approved_character_count=len(approved_character_ids),
        reviewed_action_count=reviewed_count,
        missing_evidence=tuple(sorted(missing)),
        failure_codes=tuple(sorted(failures)),
        case_ids=tuple(sorted(case_id for case_id in real_cases if _SAFE_CASE_ID.fullmatch(case_id))),
        character_reference_ids=tuple(sorted(
            character_id for character_id in approved_character_ids if _SAFE_CHARACTER_ID.fullmatch(character_id)
        )),
    )


def _valid_model_evidence(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    licenses = value.get("licenses")
    if not isinstance(licenses, list):
        return False
    by_id: dict[str, dict[str, Any]] = {
        item["component_id"]: item for item in licenses if isinstance(item, dict) and isinstance(item.get("component_id"), str)
    }
    if not _REQUIRED_LICENSES.issubset(by_id):
        return False
    for item in by_id.values():
        url = item.get("terms_url")
        if (
            not isinstance(item.get("license_name"), str)
            or not isinstance(url, str)
            or urlparse(url).scheme != "https"
            or not isinstance(item.get("weights_redistributable"), bool)
        ):
            return False
    return True


def _is_16_gib_windows_x64(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    memory = value.get("total_ram_bytes")
    return (
        value.get("os_name") == "Windows"
        and value.get("architecture") == "x86_64"
        and isinstance(memory, int)
        and abs(memory - 16 * _GIB) <= _GIB // 2
        and value.get("gpu_name") is None
    )


def _has_supported_gpu(value: object, peak_gpu_memory_bytes: int | None) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("gpu_name"), str):
        return False
    gpu_memory = value.get("gpu_memory_bytes")
    return (
        value.get("os_name") == "Windows"
        and value.get("architecture") == "x86_64"
        and isinstance(gpu_memory, int)
        and gpu_memory >= 4 * _GIB
        and isinstance(peak_gpu_memory_bytes, int)
        and peak_gpu_memory_bytes > 0
    )


def write_p0_gate_report(report: P0GateReport, output_path: Path) -> Path:
    if not isinstance(report, P0GateReport):
        raise ValueError("invalid_p0_gate_report")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", prefix=f".{output.name}.", suffix=".tmp", dir=output.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        json.dump(report.to_dict(), stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, output)
    return output


def load_local_p0_evidence(evidence_root: Path) -> tuple[list[EvalResult], list[ActionPreview]]:
    """Read P0 gate evidence from a private local evaluation folder, never from Git."""
    root = Path(evidence_root).resolve()
    results: list[EvalResult] = []
    previews: list[ActionPreview] = []
    for path in root.rglob("p0-eval-evidence.json"):
        payload = _read_json_under(root, path)
        correction_count = payload.get("correction_count", 0)
        if not isinstance(correction_count, int) or correction_count < 0:
            correction_count = -1
        action_manifest_path = path.parent / "p0-actions" / "manifest.json"
        if action_manifest_path.is_file():
            action_manifest = _read_json_under(root, action_manifest_path)
            recorded_corrections = action_manifest.get("correction_count", 0)
            if isinstance(recorded_corrections, int) and recorded_corrections >= 0:
                correction_count = max(correction_count, recorded_corrections)
        results.append(
            EvalResult(
                case_id=str(payload.get("case_id", "")),
                model_id="p0-local",
                device_id="cuda" if (payload.get("device_profile") or {}).get("gpu_name") else "cpu",
                elapsed_ms=payload.get("elapsed_ms", 0),
                peak_memory_bytes=payload.get("peak_memory_bytes", 0),
                correction_count=correction_count,
                stages=payload.get("stages", {}),
                error_code=payload.get("error_code"),
                private_context={
                    key: payload.get(key)
                    for key in (
                        "subject_type",
                        "photo_consent_confirmed",
                        "variation_tags",
                        "owner_approved_character",
                        "character_reference_id",
                        "privacy_preflight_passed",
                        "device_profile",
                        "model_evidence",
                    )
                },
                stage_elapsed_ms=payload.get("stage_elapsed_ms"),
                peak_gpu_memory_bytes=payload.get("peak_gpu_memory_bytes"),
            )
        )
    for path in root.rglob("manifest.json"):
        if path.parent.name != "p0-actions":
            continue
        payload = _read_json_under(root, path)
        for action in payload.get("actions", []):
            if not isinstance(action, dict):
                continue
            previews.append(
                ActionPreview(
                    action_id=str(action.get("action_id", "")),
                    status=str(action.get("status", "unsupported")),
                    frame_paths=tuple(path.parent / str(item) for item in action.get("frame_paths", [])),
                    fps_target=action.get("fps_target", 0),
                    duration_seconds=action.get("duration_seconds", 0),
                    issues=tuple(action.get("issues", [])),
                    character_reference_id=str(payload.get("character_reference_id", "")),
                    reviewed=action.get("reviewed") is True,
                    defects=tuple(action.get("defects", [])),
                    case_id=str(action.get("case_id", payload.get("case_id", ""))),
                )
            )
    return results, previews


def _read_json_under(root: Path, path: Path) -> dict[str, Any]:
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("p0_evidence_unreadable") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("p0_evidence_schema_invalid")
    return payload
