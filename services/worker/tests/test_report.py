from __future__ import annotations

import json
from pathlib import Path

import pytest

from petforge_worker.corpus import EvalResult
from petforge_worker.report import write_eval_report


def test_report_contains_only_redacted_metrics(tmp_path: Path) -> None:
    output = tmp_path / "reports" / "p0.json"
    source_path = tmp_path / "private" / "Alice Example.jpg"
    result = EvalResult(
        case_id="case_01234567",
        model_id="petforge-cartoon-v0",
        device_id="cuda-0",
        elapsed_ms=1234,
        peak_memory_bytes=2_000_000,
        correction_count=2,
        stages={"preflight": "passed", "generation": "needs_review"},
        error_code="generation_failed",
        private_context={
            "source_path": str(source_path),
            "subject_name": "Alice Example",
            "prompt": "Alice in a white dress",
            "exif": {"GPSLatitude": "1.2,3.4"},
            "error_detail": "failed at C:" + chr(92) + "Users" + chr(92) + "Alice" + chr(92) + "private" + chr(92) + "photo.jpg",
            "image_bytes": b"private pixels",
        },
    )

    saved = write_eval_report([result], output)
    text = saved.read_text(encoding="utf-8")
    report = json.loads(text)
    serialized = report["results"][0]

    assert serialized == {
        "case_id": "case_01234567",
        "model_id": "petforge-cartoon-v0",
        "device_id": "cuda-0",
        "elapsed_ms": 1234,
        "peak_memory_bytes": 2_000_000,
        "correction_count": 2,
        "stages": {"preflight": "passed", "generation": "needs_review"},
        "error_code": "generation_failed",
    }
    win_private_path = "C:" + chr(92) + "Users" + chr(92)
    for secret in (str(source_path), "Alice Example", "white dress", "GPSLatitude", "private pixels", win_private_path):
        assert secret not in text


def test_report_rejects_untrusted_error_text_as_error_code(tmp_path: Path) -> None:
    result = EvalResult(
        case_id="case_01234567",
        model_id="petforge-cartoon-v0",
        device_id="cpu",
        elapsed_ms=10,
        peak_memory_bytes=100,
        correction_count=0,
        stages={"generation": "failed"},
        error_code="failed at C:" + chr(92) + "Users" + chr(92) + "Alice" + chr(92) + "photo.jpg",
    )

    with pytest.raises(ValueError, match="invalid_error_code"):
        write_eval_report([result], tmp_path / "report.json")


def test_report_rejects_unknown_stage_outcomes(tmp_path: Path) -> None:
    result = EvalResult(
        case_id="case_01234567",
        model_id="petforge-cartoon-v0",
        device_id="cpu",
        elapsed_ms=10,
        peak_memory_bytes=100,
        correction_count=0,
        stages={"generation": "failed: C:" + chr(92) + "Users" + chr(92) + "Alice"},
    )

    with pytest.raises(ValueError, match="invalid_stage_outcome"):
        write_eval_report([result], tmp_path / "report.json")


def test_report_rejects_non_string_identifiers(tmp_path: Path) -> None:
    result = EvalResult(
        case_id=123,
        model_id="petforge-cartoon-v0",
        device_id="cpu",
        elapsed_ms=10,
        peak_memory_bytes=100,
        correction_count=0,
        stages={},
    )

    with pytest.raises(ValueError, match="invalid_case_id"):
        write_eval_report([result], tmp_path / "report.json")


def test_schema_only_allows_redacted_report_fields() -> None:
    schema_path = Path(__file__).parents[1] / "petforge_worker" / "evaluation_schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    result_schema = schema["properties"]["results"]["items"]
    assert result_schema["additionalProperties"] is False
    assert set(result_schema["properties"]) == {
        "case_id",
        "model_id",
        "device_id",
        "elapsed_ms",
        "peak_memory_bytes",
        "correction_count",
        "stages",
        "error_code",
    }
