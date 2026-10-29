from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from urllib.parse import urlparse


_CASE_ID = re.compile(r"case_[a-f0-9]{8,32}\Z")
_SUBJECT_TYPES = {"real_person", "synthetic", "licensed_illustration"}
_VARIATION_TAGS = {
    "full_body",
    "half_body",
    "portrait",
    "group_photo",
    "indoor",
    "outdoor",
    "low_light",
    "complex_background",
    "simple_background",
    "different_clothing",
}


class CorpusError(ValueError):
    """A stable, path-free local evaluation corpus error."""


@dataclass(frozen=True, slots=True)
class EvalCase:
    case_id: str
    image_path: Path
    subject_type: str
    is_real_person: bool
    likeness_approved: bool
    variation_tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvalResult:
    case_id: str
    model_id: str
    device_id: str
    elapsed_ms: int
    peak_memory_bytes: int
    correction_count: int
    stages: dict[str, str]
    error_code: str | None = None
    private_context: dict[str, Any] | None = None
    stage_elapsed_ms: dict[str, int] | None = None
    peak_gpu_memory_bytes: int | None = None


def default_eval_root() -> Path:
    configured = os.environ.get("PETFORGE_EVAL_ROOT")
    return Path(configured) if configured else Path(r"E:\PetForge\evaluations")


def _raise(code: str) -> None:
    raise CorpusError(code)


def _is_recorded_consent(value: object) -> bool:
    if not isinstance(value, dict) or value.get("evaluation") is not True:
        return False
    recorded_at = value.get("recorded_at")
    if not isinstance(recorded_at, str) or not recorded_at.strip():
        return False
    try:
        datetime.fromisoformat(recorded_at.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _has_license_record(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    spdx_id = value.get("spdx_id")
    source_url = value.get("source_url")
    if not isinstance(spdx_id, str) or not spdx_id.strip():
        return False
    if not isinstance(source_url, str):
        return False
    parsed_url = urlparse(source_url)
    return parsed_url.scheme == "https" and bool(parsed_url.netloc)


def load_eval_cases(root: Path) -> list[EvalCase]:
    """Load local cases and require explicit evaluation consent for real people."""
    corpus_root = root.resolve()
    manifest_path = corpus_root / "eval-cases.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _raise("manifest_unreadable")

    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        _raise("unsupported_manifest_schema")
    records = manifest.get("cases")
    if not isinstance(records, list):
        _raise("cases_must_be_a_list")

    seen_ids: set[str] = set()
    cases: list[EvalCase] = []
    for record in records:
        if not isinstance(record, dict):
            _raise("invalid_case_record")
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or _CASE_ID.fullmatch(case_id) is None:
            _raise("invalid_case_id")
        if case_id in seen_ids:
            _raise("duplicate_case_id")
        seen_ids.add(case_id)

        subject_type = record.get("subject_type")
        if not isinstance(subject_type, str) or subject_type not in _SUBJECT_TYPES:
            _raise("invalid_subject_type")
        is_real_person = subject_type == "real_person"
        approved = _is_recorded_consent(record.get("consent"))
        if is_real_person and not approved:
            _raise("consent_required")
        if subject_type == "licensed_illustration" and not _has_license_record(record.get("license")):
            _raise("license_metadata_required")

        raw_variation_tags = record.get("variation_tags", [])
        if not isinstance(raw_variation_tags, list) or any(
            not isinstance(tag, str) or tag not in _VARIATION_TAGS for tag in raw_variation_tags
        ):
            _raise("invalid_variation_tags")

        image_value = record.get("image")
        if not isinstance(image_value, str) or not image_value.strip():
            _raise("image_path_missing")
        posix_path = PurePosixPath(image_value.replace("\\", "/"))
        windows_path = PureWindowsPath(image_value)
        if (
            posix_path.is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.drive)
            or ".." in posix_path.parts
        ):
            _raise("unsafe_image_path")
        try:
            image_path = (corpus_root / Path(*posix_path.parts)).resolve()
            image_path.relative_to(corpus_root)
        except ValueError:
            _raise("unsafe_image_path")
        except (OSError, RuntimeError):
            _raise("invalid_image_path")
        if not image_path.is_file():
            _raise("image_missing")

        cases.append(
            EvalCase(
                case_id=case_id,
                image_path=image_path,
                subject_type=subject_type,
                is_real_person=is_real_person,
                likeness_approved=is_real_person and approved,
                variation_tags=tuple(sorted(set(raw_variation_tags))),
            )
        )
    return cases
