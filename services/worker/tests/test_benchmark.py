import json
from importlib import import_module
from pathlib import Path

import pytest
from PIL import Image

from petforge_worker.corpus import EvalCase


def _api():
    try:
        return import_module("petforge_worker.benchmark")
    except ModuleNotFoundError:
        pytest.fail("photo benchmark pipeline is not implemented")


def _case(path: Path) -> EvalCase:
    return EvalCase("case_0123456789abcdef", path, "synthetic", False, False)


class _NeverCalled:
    def detect(self, *_args):
        raise AssertionError("invalid source must stop before detection")


def test_corrupt_source_is_rejected_before_detection_or_model_load(tmp_path):
    api = _api()
    source = tmp_path / "bad.png"
    source.write_bytes(b"not an image")
    detector = _NeverCalled()
    generator = _NeverCalled()

    result = api.run_case(
        _case(source),
        detector=detector,
        cutout=_NeverCalled(),
        generator=generator,
        segmenter=_NeverCalled(),
        output_root=tmp_path / "out",
    )

    assert result.error_code == "invalid_image"
    assert result.stages["preflight"] == "failed"
    assert result.stages["detection"] == "skipped"
    assert result.stage_elapsed_ms["preflight"] >= 0


def test_failed_revision_keeps_previous_accepted_candidate_and_intermediates(tmp_path):
    api = _api()
    source = tmp_path / "photo.png"
    Image.new("RGB", (64, 96), "#f0d0c0").save(source)
    root = tmp_path / "out"
    detector = api.DeterministicFakePersonDetector()
    cutout = api.DeterministicFakeCutoutProvider()
    segmenter = api.DeterministicFakeLayerSegmenter()
    good_generator = api.DeterministicFakePortraitGenerator()
    case = _case(source)

    accepted = api.run_case(
        case,
        detector=detector,
        cutout=cutout,
        generator=good_generator,
        segmenter=segmenter,
        output_root=root,
        reviewer=lambda _candidate: True,
    )
    accepted_path = root / "cases" / case.case_id / "accepted.json"
    prior_pointer = accepted_path.read_bytes()
    assert accepted.stages["review"] == "passed"
    assert accepted.stage_elapsed_ms["generation"] >= 0
    assert accepted.peak_memory_bytes >= 0

    failed = api.run_case(
        case,
        detector=detector,
        cutout=cutout,
        generator=api.FailingPortraitGenerator(),
        segmenter=segmenter,
        output_root=root,
        reviewer=lambda _candidate: True,
    )

    assert failed.error_code == "generation_failed"
    assert accepted_path.read_bytes() == prior_pointer
    assert list((root / "cases" / case.case_id / "failed").rglob("cutout.png"))


def test_unreviewed_candidate_is_preserved_but_not_marked_accepted(tmp_path):
    api = _api()
    source = tmp_path / "photo.png"
    Image.new("RGB", (64, 96), "#f0d0c0").save(source)
    case = _case(source)

    result = api.run_case(
        case,
        detector=api.DeterministicFakePersonDetector(),
        cutout=api.DeterministicFakeCutoutProvider(),
        generator=api.DeterministicFakePortraitGenerator(),
        segmenter=api.DeterministicFakeLayerSegmenter(),
        output_root=tmp_path / "out",
    )

    case_root = tmp_path / "out" / "cases" / case.case_id
    assert result.stages["review"] == "needs_review"
    assert not (case_root / "accepted.json").exists()
    revision_dir = next((case_root / "pending").iterdir())
    candidate = json.loads((revision_dir / "p0-candidate.json").read_text(encoding="utf-8"))
    evidence = json.loads((revision_dir / "p0-eval-evidence.json").read_text(encoding="utf-8"))
    assert candidate["character_reference_id"] == evidence["character_reference_id"]
    assert candidate["revision_id"].startswith("rev_")
    assert (revision_dir / "generated" / "provenance.json").is_file()


def test_cancellation_is_recorded_and_candidate_is_not_promoted(tmp_path):
    api = _api()
    source = tmp_path / "photo.png"
    Image.new("RGB", (64, 96), "#f0d0c0").save(source)
    cancel = api.CancelToken()
    cancel.cancel()
    case = _case(source)

    result = api.run_case(
        case,
        detector=api.DeterministicFakePersonDetector(),
        cutout=api.DeterministicFakeCutoutProvider(),
        generator=api.DeterministicFakePortraitGenerator(),
        segmenter=api.DeterministicFakeLayerSegmenter(),
        output_root=tmp_path / "out",
        cancel=cancel,
        reviewer=lambda _candidate: True,
    )

    assert result.error_code == "generation_cancelled"
    assert result.stages["review"] == "skipped"
    assert not (tmp_path / "out" / "cases" / case.case_id / "accepted.json").exists()


def test_keyboard_interrupt_during_generation_preserves_cutout_and_report_data(tmp_path):
    api = _api()
    source = tmp_path / "photo.png"
    Image.new("RGB", (64, 96), "#f0d0c0").save(source)

    class InterruptingGenerator:
        model_id = "interrupt-test-model"

        def generate(self, _request, _device, output_dir, _cancel):
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "partial-step.bin").write_bytes(b"partial")
            raise KeyboardInterrupt

    case = _case(source)
    result = api.run_case(
        case,
        detector=api.DeterministicFakePersonDetector(),
        cutout=api.DeterministicFakeCutoutProvider(),
        generator=InterruptingGenerator(),
        segmenter=api.DeterministicFakeLayerSegmenter(),
        output_root=tmp_path / "out",
        reviewer=lambda _candidate: True,
    )

    failed_dir = Path(result.private_context["candidate_directory"])
    evidence = json.loads((failed_dir / "p0-eval-evidence.json").read_text(encoding="utf-8"))
    assert result.error_code == "generation_cancelled"
    assert result.stages["generation"] == "rejected"
    assert (failed_dir / "cutout" / "cutout.png").is_file()
    assert (failed_dir / "generated" / "partial-step.bin").read_bytes() == b"partial"
    assert evidence["error_code"] == "generation_cancelled"
    assert not (tmp_path / "out" / "cases" / case.case_id / "accepted.json").exists()


def test_visible_full_body_joints_are_not_mislabeled_as_inferred():
    api = _api()
    person = api.PersonCandidate(
        bbox_xywh_norm=(0.14, 0.20, 0.74, 0.60),
        landmarks_norm={
            name: (0.5, y, 0.9)
            for name, y in {
                "left_hip": 0.55,
                "right_hip": 0.55,
                "left_knee": 0.72,
                "right_knee": 0.72,
                "left_ankle": 0.94,
                "right_ankle": 0.94,
            }.items()
        },
        confidence=0.9,
    )

    assert api._infer_regions(person) == ()


def test_missing_lower_body_landmarks_are_labeled_inferred():
    api = _api()
    person = api.PersonCandidate(
        bbox_xywh_norm=(0.2, 0.1, 0.6, 0.6),
        landmarks_norm={"left_shoulder": (0.4, 0.3, 0.9), "right_shoulder": (0.6, 0.3, 0.9)},
        confidence=0.9,
    )

    assert set(api._infer_regions(person)) == {"lower_body", "lower_clothing", "feet", "lower_body_pose"}
