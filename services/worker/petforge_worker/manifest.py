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
    size_mismatches: tuple[str, ...] = ()
    component_ids: tuple[str, ...] = ()
    expected_bytes: int = 0

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for field in ("missing_files", "hash_mismatches", "errors", "size_mismatches", "component_ids"):
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


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
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

    if not isinstance(document, dict) or document.get("schema_version") not in {1, 2}:
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
    if document.get("schema_version") == 2:
        return _validate_components(model_id, revision, model, model_root)

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


def _validate_components(
    model_id: str,
    revision: str | None,
    model: dict[str, object],
    model_root: Path,
) -> ModelAvailability:
    errors: list[str] = []
    if not revision or not revision.strip() or revision.lower() in {"main", "master", "latest"}:
        errors.append("composite_revision_missing_or_unpinned")
    components = model.get("components")
    if not isinstance(components, list) or not components:
        return _invalid(model_id, revision, [*errors, "components_missing"])

    root = model_root.resolve()
    missing_files: list[str] = []
    hash_mismatches: list[str] = []
    md5_mismatches: list[str] = []
    size_mismatches: list[str] = []
    component_ids: list[str] = []
    expected_bytes = 0
    seen_paths: set[str] = set()

    for component in components:
        if not isinstance(component, dict):
            errors.append("invalid_component_entry")
            continue
        component_id = component.get("id")
        if not isinstance(component_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", component_id) is None:
            errors.append("component_id_invalid")
            continue
        if component_id in component_ids:
            errors.append("duplicate_component_id")
        else:
            component_ids.append(component_id)

        source_url = component.get("source_url")
        if not isinstance(source_url, str) or urlparse(source_url).scheme != "https" or not urlparse(source_url).netloc:
            errors.append("component_source_url_must_use_https")
        component_revision = component.get("revision")
        if (
            not isinstance(component_revision, str)
            or not component_revision.strip()
            or component_revision.lower() in {"main", "master", "latest"}
        ):
            errors.append("component_revision_missing_or_unpinned")

        license_data = component.get("license")
        if not isinstance(license_data, dict):
            errors.append("component_license_metadata_missing")
        else:
            license_id = license_data.get("spdx_id") or license_data.get("license_name")
            terms_url = license_data.get("terms_url")
            redistributable = license_data.get("weights_redistributable")
            if not isinstance(license_id, str) or not license_id.strip():
                errors.append("component_license_id_missing")
            if not isinstance(terms_url, str) or urlparse(terms_url).scheme != "https" or not urlparse(terms_url).netloc:
                errors.append("component_license_terms_url_invalid")
            if not isinstance(redistributable, bool):
                errors.append("component_weight_redistribution_status_missing")

        listed_files = component.get("files")
        if not isinstance(listed_files, list) or not listed_files:
            errors.append("component_files_missing")
            continue
        for entry in listed_files:
            if not isinstance(entry, dict):
                errors.append("invalid_file_entry")
                continue
            relative_path = entry.get("path")
            expected_hash = entry.get("sha256")
            expected_md5 = entry.get("md5")
            download_url = entry.get("download_url")
            file_size = entry.get("size_bytes")
            if not isinstance(relative_path, str) or not relative_path.strip():
                errors.append("file_path_missing")
                continue
            candidate = (root / relative_path).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                errors.append("unsafe_file_path")
                continue
            if relative_path in seen_paths:
                errors.append("duplicate_model_file_path")
                continue
            seen_paths.add(relative_path)
            if not isinstance(download_url, str) or urlparse(download_url).scheme != "https" or not urlparse(download_url).netloc:
                errors.append("file_download_url_invalid")
            if expected_hash is not None and (
                not isinstance(expected_hash, str) or re.fullmatch(r"[a-fA-F0-9]{64}", expected_hash) is None
            ):
                errors.append("file_sha256_invalid")
            if expected_hash is None and (
                not isinstance(expected_md5, str) or re.fullmatch(r"[a-fA-F0-9]{32}", expected_md5) is None
            ):
                errors.append("file_checksum_missing")
            if not isinstance(file_size, int) or isinstance(file_size, bool) or file_size <= 0:
                errors.append("file_size_invalid")
            else:
                expected_bytes += file_size
            if not candidate.is_file():
                missing_files.append(relative_path)
                continue
            if isinstance(file_size, int) and not isinstance(file_size, bool) and file_size > 0:
                try:
                    if candidate.stat().st_size != file_size:
                        size_mismatches.append(relative_path)
                except OSError:
                    errors.append("file_unreadable")
            if isinstance(expected_hash, str) and re.fullmatch(r"[a-fA-F0-9]{64}", expected_hash):
                try:
                    if _sha256(candidate).lower() != expected_hash.lower():
                        hash_mismatches.append(relative_path)
                except OSError:
                    errors.append("file_unreadable")
            elif isinstance(expected_md5, str) and re.fullmatch(r"[a-fA-F0-9]{32}", expected_md5):
                try:
                    if _md5(candidate).lower() != expected_md5.lower():
                        md5_mismatches.append(relative_path)
                except OSError:
                    errors.append("file_unreadable")

    if errors:
        return ModelAvailability(
            model_id, revision, "invalid_manifest", False, "MULTI", errors=tuple(dict.fromkeys(errors)),
            component_ids=tuple(component_ids), expected_bytes=expected_bytes,
        )
    if size_mismatches:
        return ModelAvailability(
            model_id, revision, "size_mismatch", False, "MULTI", size_mismatches=tuple(size_mismatches),
            component_ids=tuple(component_ids), expected_bytes=expected_bytes,
        )
    if hash_mismatches or md5_mismatches:
        return ModelAvailability(
            model_id, revision, "hash_mismatch", False, "MULTI", hash_mismatches=tuple(hash_mismatches + md5_mismatches),
            component_ids=tuple(component_ids), expected_bytes=expected_bytes,
        )
    if missing_files:
        return ModelAvailability(
            model_id, revision, "missing_files", False, "MULTI", missing_files=tuple(missing_files),
            component_ids=tuple(component_ids), expected_bytes=expected_bytes,
        )
    return ModelAvailability(
        model_id, revision, "ready", True, "MULTI", component_ids=tuple(component_ids), expected_bytes=expected_bytes
    )
