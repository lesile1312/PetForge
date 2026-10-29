import hashlib
import json
from importlib import import_module
from pathlib import Path

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


def test_component_manifest_reports_licenses_sizes_and_missing_weights(tmp_path):
    api = _manifest_api()
    model_root = tmp_path / "models"
    model_root.mkdir()
    model = {
        "id": "p0-composite",
        "revision": "p0-2026-10-29",
        "components": [
            {
                "id": "portrait",
                "source_url": "https://models.example.org/portrait",
                "revision": "0123456789abcdef0123456789abcdef01234567",
                "license": {
                    "license_name": "Example Research Terms",
                    "terms_url": "https://models.example.org/terms",
                    "weights_redistributable": False,
                },
                "files": [
                    {
                        "path": "portrait/weights.bin",
                        "download_url": "https://models.example.org/portrait/weights.bin",
                        "size_bytes": 16,
                        "sha256": hashlib.sha256(b"sixteen-byte-file").hexdigest(),
                    }
                ],
            }
        ],
    }
    manifest_path = tmp_path / "manifest-v2.json"
    manifest_path.write_text(
        json.dumps({"schema_version": 2, "active_model_id": model["id"], "models": [model]}),
        encoding="utf-8",
    )

    result = api.validate_manifest(manifest_path, model_root)

    assert result.ready is False
    assert result.status == "missing_files"
    assert result.component_ids == ("portrait",)
    assert result.expected_bytes == 16
    assert result.missing_files == ("portrait/weights.bin",)
    assert result.license_id == "MULTI"


def test_component_manifest_checks_file_size_and_hash(tmp_path):
    api = _manifest_api()
    model_root = tmp_path / "models"
    model_root.mkdir()
    weight = model_root / "portrait" / "weights.bin"
    weight.parent.mkdir()
    weight.write_bytes(b"wrong-size")
    model = {
        "id": "p0-composite",
        "revision": "p0-2026-10-29",
        "components": [
            {
                "id": "portrait",
                "source_url": "https://models.example.org/portrait",
                "revision": "0123456789abcdef0123456789abcdef01234567",
                "license": {"spdx_id": "MIT", "terms_url": "https://models.example.org/license", "weights_redistributable": True},
                "files": [
                    {
                        "path": "portrait/weights.bin",
                        "download_url": "https://models.example.org/portrait/weights.bin",
                        "size_bytes": 16,
                        "sha256": hashlib.sha256(b"sixteen-byte-file").hexdigest(),
                    }
                ],
            }
        ],
    }
    manifest_path = tmp_path / "manifest-v2.json"
    manifest_path.write_text(
        json.dumps({"schema_version": 2, "active_model_id": model["id"], "models": [model]}),
        encoding="utf-8",
    )

    result = api.validate_manifest(manifest_path, model_root)

    assert result.ready is False
    assert result.status == "size_mismatch"
    assert result.size_mismatches == ("portrait/weights.bin",)


def test_component_manifest_rejects_unpinned_or_unlicensed_component(tmp_path):
    api = _manifest_api()
    manifest_path, model_root = _write_manifest(tmp_path)
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    model = document["models"][0]
    model.pop("license")
    model.pop("files")
    model["components"] = [
        {
            "id": "bad",
            "source_url": "http://insecure.example.org/weights",
            "revision": "main",
            "license": {},
            "files": [{"path": "../outside.bin", "download_url": "http://bad", "size_bytes": 1, "sha256": "x"}],
        }
    ]
    document["schema_version"] = 2
    manifest_path.write_text(json.dumps(document), encoding="utf-8")

    result = api.validate_manifest(manifest_path, model_root)

    assert result.ready is False
    assert result.status == "invalid_manifest"
    assert "component_source_url_must_use_https" in result.errors
    assert "component_revision_missing_or_unpinned" in result.errors
    assert "component_license_id_missing" in result.errors
    assert "unsafe_file_path" in result.errors


def test_p0_source_manifest_has_pinned_component_metadata_and_no_repo_weights(tmp_path):
    api = _manifest_api()
    repo_root = Path(__file__).resolve().parents[3]
    manifest_path = repo_root / "models" / "manifest.json"

    result = api.validate_manifest(manifest_path, tmp_path)

    assert result.status == "missing_files"
    assert result.component_ids == (
        "sdxl-base-1.0",
        "ip-adapter-plus-sdxl-vit-h",
        "birefnet-portrait-cutout",
        "mediapipe-pose-full",
    )
    assert result.expected_bytes > 11_000_000_000
    assert len(result.missing_files) >= 19
    assert all(not (repo_root / "models" / path).is_file() for path in ("sdxl/sd_xl_base_1.0.safetensors",))


def test_sdxl_second_tokenizer_uses_the_pinned_upstream_repository():
    repo_root = Path(__file__).resolve().parents[3]
    document = json.loads((repo_root / "models" / "manifest.json").read_text(encoding="utf-8"))
    components = document["models"][0]["components"]
    sdxl = next(component for component in components if component["id"] == "sdxl-base-1.0")
    merges = next(item for item in sdxl["files"] if item["path"] == "sdxl-config/tokenizer_2/merges.txt")

    assert "/stabilityai/stable-diffusion-xl-base-1.0/resolve/" in merges["download_url"]
    assert merges["download_url"].endswith("/tokenizer_2/merges.txt?download=true")
