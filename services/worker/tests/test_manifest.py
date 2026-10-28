import hashlib
import json
from importlib import import_module

import pytest


def _manifest_api():
    try:
        return import_module("petforge_worker.manifest")
    except ModuleNotFoundError:
        pytest.fail("model manifest validation is not implemented")


def _write_manifest(tmp_path, *, license_data=None, expected_hash=None, file_path="weights/model.bin"):
    model_root = tmp_path / "models"
    model_root.mkdir()
    expected_hash = expected_hash or hashlib.sha256(b"model weights").hexdigest()
    model = {
        "id": "p0-test-model",
        "source_url": "https://example.org/models/p0-test-model",
        "revision": "deadbeef",
        "license": license_data if license_data is not None else {
            "spdx_id": "MIT",
            "terms_url": "https://example.org/license",
            "weights_redistributable": True,
        },
        "files": [{"path": file_path, "sha256": expected_hash}],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"schema_version": 1, "active_model_id": model["id"], "models": [model]}),
        encoding="utf-8",
    )
    return manifest_path, model_root


def test_missing_model_weights_are_reported(tmp_path):
    api = _manifest_api()
    manifest_path, model_root = _write_manifest(tmp_path)

    result = api.validate_manifest(manifest_path, model_root)

    assert result.ready is False
    assert result.status == "missing_files"
    assert result.missing_files == ("weights/model.bin",)


def test_weight_hash_mismatch_is_reported(tmp_path):
    api = _manifest_api()
    manifest_path, model_root = _write_manifest(tmp_path)
    weight_path = model_root / "weights" / "model.bin"
    weight_path.parent.mkdir()
    weight_path.write_bytes(b"wrong weights")

    result = api.validate_manifest(manifest_path, model_root)

    assert result.ready is False
    assert result.status == "hash_mismatch"
    assert result.hash_mismatches == ("weights/model.bin",)


def test_missing_license_metadata_makes_model_unavailable(tmp_path):
    api = _manifest_api()
    manifest_path, model_root = _write_manifest(tmp_path, license_data=None)
    weight_path = model_root / "weights" / "model.bin"
    weight_path.parent.mkdir()
    weight_path.write_bytes(b"model weights")

    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["models"][0].pop("license")
    manifest_path.write_text(json.dumps(document), encoding="utf-8")

    result = api.validate_manifest(manifest_path, model_root)

    assert result.ready is False
    assert result.status == "invalid_manifest"
    assert "license_metadata_missing" in result.errors


def test_valid_local_weights_and_license_report_ready(tmp_path):
    api = _manifest_api()
    manifest_path, model_root = _write_manifest(tmp_path)
    weight_path = model_root / "weights" / "model.bin"
    weight_path.parent.mkdir()
    weight_path.write_bytes(b"model weights")

    result = api.validate_manifest(manifest_path, model_root)

    assert result.ready is True
    assert result.status == "ready"
    assert result.license_id == "MIT"


def test_manifest_rejects_path_traversal(tmp_path):
    api = _manifest_api()
    manifest_path, model_root = _write_manifest(tmp_path, file_path="../outside.bin")

    result = api.validate_manifest(manifest_path, model_root)

    assert result.ready is False
    assert result.status == "invalid_manifest"
    assert "unsafe_file_path" in result.errors
