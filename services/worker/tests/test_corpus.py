from __future__ import annotations

import json
from pathlib import Path

import pytest

from petforge_worker.corpus import CorpusError, load_eval_cases


def _write_manifest(root: Path, cases: list[dict[str, object]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "eval-cases.json").write_text(
        json.dumps({"schema_version": 1, "cases": cases}),
        encoding="utf-8",
    )


def _case(
    case_id: str = "case_01234567",
    *,
    subject_type: str = "real_person",
    consent: dict[str, object] | None = None,
    image: str = "images/sample.png",
) -> dict[str, object]:
    result: dict[str, object] = {
        "case_id": case_id,
        "image": image,
        "subject_type": subject_type,
    }
    if consent is not None:
        result["consent"] = consent
    return result


def test_refuses_real_photo_without_explicit_recorded_consent(tmp_path: Path) -> None:
    image = tmp_path / "images" / "sample.png"
    image.parent.mkdir()
    image.write_bytes(b"local photo")
    _write_manifest(tmp_path, [_case()])

    with pytest.raises(CorpusError, match="consent_required"):
        load_eval_cases(tmp_path)


def test_accepts_real_photo_with_local_evaluation_consent(tmp_path: Path) -> None:
    image = tmp_path / "images" / "sample.png"
    image.parent.mkdir()
    image.write_bytes(b"local photo")
    consent = {"evaluation": True, "recorded_at": "2026-10-28T00:00:00Z"}
    _write_manifest(tmp_path, [_case(consent=consent)])

    cases = load_eval_cases(tmp_path)

    assert len(cases) == 1
    assert cases[0].case_id == "case_01234567"
    assert cases[0].is_real_person is True
    assert cases[0].likeness_approved is True
    assert cases[0].image_path == image.resolve()


def test_synthetic_case_does_not_claim_approved_likeness(tmp_path: Path) -> None:
    image = tmp_path / "images" / "sample.png"
    image.parent.mkdir()
    image.write_bytes(b"synthetic image")
    _write_manifest(tmp_path, [_case(subject_type="synthetic")])

    case = load_eval_cases(tmp_path)[0]

    assert case.is_real_person is False
    assert case.likeness_approved is False


def test_open_licensed_illustration_supplements_technical_cases_only(tmp_path: Path) -> None:
    image = tmp_path / "images" / "sample.png"
    image.parent.mkdir()
    image.write_bytes(b"licensed illustration")
    case_data = _case(subject_type="licensed_illustration")
    case_data["license"] = {
        "spdx_id": "CC-BY-4.0",
        "source_url": "https://example.org/license",
    }
    _write_manifest(tmp_path, [case_data])

    case = load_eval_cases(tmp_path)[0]

    assert case.subject_type == "licensed_illustration"
    assert case.is_real_person is False
    assert case.likeness_approved is False


def test_open_licensed_illustration_requires_license_metadata(tmp_path: Path) -> None:
    _write_manifest(tmp_path, [_case(subject_type="licensed_illustration")])

    with pytest.raises(CorpusError, match="license_metadata_required"):
        load_eval_cases(tmp_path)


def test_rejects_paths_escaping_private_corpus(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.png"
    outside.write_bytes(b"not in corpus")
    _write_manifest(
        tmp_path,
        [_case(consent={"evaluation": True, "recorded_at": "2026-10-28"}, image="../outside.png")],
    )

    with pytest.raises(CorpusError, match="unsafe_image_path"):
        load_eval_cases(tmp_path)


def test_rejects_windows_drive_relative_paths(tmp_path: Path) -> None:
    _write_manifest(tmp_path, [_case(subject_type="synthetic", image="C:private.png")])

    with pytest.raises(CorpusError, match="unsafe_image_path"):
        load_eval_cases(tmp_path)


def test_rejects_duplicate_pseudonymous_ids(tmp_path: Path) -> None:
    image = tmp_path / "images" / "sample.png"
    image.parent.mkdir()
    image.write_bytes(b"local photo")
    consent = {"evaluation": True, "recorded_at": "2026-10-28T00:00:00Z"}
    _write_manifest(tmp_path, [_case(consent=consent), _case(consent=consent)])

    with pytest.raises(CorpusError, match="duplicate_case_id"):
        load_eval_cases(tmp_path)


def test_rejects_ids_that_are_not_pseudonymous(tmp_path: Path) -> None:
    image = tmp_path / "images" / "sample.png"
    image.parent.mkdir()
    image.write_bytes(b"synthetic image")
    _write_manifest(tmp_path, [_case(case_id="Alice Example", subject_type="synthetic")])

    with pytest.raises(CorpusError, match="invalid_case_id"):
        load_eval_cases(tmp_path)
