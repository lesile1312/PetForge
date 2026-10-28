from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class ModelAvailability:
    model_id: str | None
    revision: str | None
    status: str
    ready: bool
    license_id: str | None
    missing_files: tuple[str, ...] = ()
    hash_mismatches: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for field in ("missing_files", "hash_mismatches", "errors"):
            payload[field] = list(payload[field])
        return payload


def _invalid(
    model_id: str | None,
    revision: str | None,
    errors: list[str],
    license_id: str | None = None,
) -> ModelAvailability:
    return ModelAvailability(
        model_id=model_id,
        revision=revision,
        status="invalid_manifest",
        ready=False,
        license_id=license_id,
        errors=tuple(dict.fromkeys(errors)),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest(manifest_path: Path, model_root: Path) -> ModelAvailability:
    """Check local model metadata and files; never fetch a model or contact its source."""
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _invalid(None, None, ["manifest_unreadable"])

    if not isinstance(document, dict) or document.get("schema_version") != 1:
        return _invalid(None, None, ["unsupported_manifest_schema"])

    model_id = document.get("active_model_id")
    if not isinstance(model_id, str) or not model_id.strip():
        return ModelAvailability(None, None, "not_selected", False, None, errors=("no_model_selected",))

    models = document.get("models")
    if not isinstance(models, list):
        return _invalid(model_id, None, ["models_must_be_a_list"])
    model = next((item for item in models if isinstance(item, dict) and item.get("id") == model_id), None)
    if model is None:
        return _invalid(model_id, None, ["active_model_not_found"])

    revision = model.get("revision") if isinstance(model.get("revision"), str) else None
    errors: list[str] = []
    source_url = model.get("source_url")
    if not isinstance(source_url, str) or urlparse(source_url).scheme != "https":
        errors.append("source_url_must_use_https")
    if not revision or not revision.strip():
        errors.append("revision_missing")

    license_data = model.get("license")
    license_id = None
    if not isinstance(license_data, dict):
        errors.append("license_metadata_missing")
    else:
        spdx_id = license_data.get("spdx_id")
        terms_url = license_data.get("terms_url")
        redistributable = license_data.get("weights_redistributable")
        if not isinstance(spdx_id, str) or not spdx_id.strip():
            errors.append("license_spdx_missing")
        else:
            license_id = spdx_id.strip()
        if not isinstance(terms_url, str) or urlparse(terms_url).scheme != "https":
            errors.append("license_terms_url_invalid")
        if not isinstance(redistributable, bool):
            errors.append("weight_redistribution_status_missing")

    listed_files = model.get("files")
    if not isinstance(listed_files, list) or not listed_files:
        errors.append("model_files_missing")
        listed_files = []

    root = model_root.resolve()
    missing_files: list[str] = []
    hash_mismatches: list[str] = []
    for entry in listed_files:
        if not isinstance(entry, dict):
            errors.append("invalid_file_entry")
            continue
        relative_path = entry.get("path")
        expected_hash = entry.get("sha256")
        if not isinstance(relative_path, str) or not relative_path.strip():
            errors.append("file_path_missing")
            continue
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append("unsafe_file_path")
            continue
        if not isinstance(expected_hash, str) or re.fullmatch(r"[a-fA-F0-9]{64}", expected_hash) is None:
            errors.append("file_sha256_invalid")
            continue
        if not candidate.is_file():
            missing_files.append(relative_path)
            continue
        try:
            if _sha256(candidate).lower() != expected_hash.lower():
                hash_mismatches.append(relative_path)
        except OSError:
            errors.append("file_unreadable")

    if errors:
        return _invalid(model_id, revision, errors, license_id)
    if hash_mismatches:
        return ModelAvailability(model_id, revision, "hash_mismatch", False, license_id, (), tuple(hash_mismatches))
    if missing_files:
        return ModelAvailability(model_id, revision, "missing_files", False, license_id, tuple(missing_files))
    return ModelAvailability(model_id, revision, "ready", True, license_id)
