import json
from pathlib import Path

from petforge_worker.action_pose import ActionPreview
from petforge_worker.corpus import EvalResult
from petforge_worker.p0_gate import evaluate_p0, load_local_p0_evidence, write_p0_gate_report


_ACTIONS = ("idle", "run_left", "run_right", "wave_smile", "phone_crouch")
_GIB = 1024**3
_LICENSES = [
    {"component_id": "sdxl", "license_name": "CreativeML Open RAIL++-M", "terms_url": "https://example.org/sdxl", "weights_redistributable": False},
    {"component_id": "sdxl-base-1.0", "license_name": "CreativeML Open RAIL++-M", "terms_url": "https://example.org/sdxl", "weights_redistributable": False},
    {"component_id": "ip-adapter-plus-sdxl-vit-h", "license_name": "Apache-2.0", "terms_url": "https://example.org/adapter", "weights_redistributable": True},
    {"component_id": "birefnet-portrait-cutout", "license_name": "MIT", "terms_url": "https://example.org/birefnet", "weights_redistributable": True},
    {"component_id": "mediapipe-pose-full", "license_name": "Apache-2.0", "terms_url": "https://example.org/pose", "weights_redistributable": True},
]


def _result(case_number: int, *, device: str = "cpu", accepted: bool = False) -> EvalResult:
    case_id = f"case_{case_number:08x}"
    cpu = device == "cpu"
    context = {
        "subject_type": "real_person",
        "photo_consent_confirmed": True,
        "variation_tags": [["full_body", "indoor", "portrait"][case_number % 3]],
        "owner_approved_character": accepted,
        "character_reference_id": f"{case_number:024x}" if accepted else None,
        "privacy_preflight_passed": True,
        "device_profile": {
            "os_name": "Windows",
            "architecture": "x86_64",
            "total_ram_bytes": 16 * _GIB,
            "gpu_name": None if cpu else "NVIDIA GeForce RTX 4060",
            "gpu_memory_bytes": None if cpu else 8 * _GIB,
        },
        "model_evidence": {"model_revision": "p0-test", "licenses": _LICENSES},
    }
    stages = {
        "preflight": "passed",
        "detection": "passed",
        "cutout": "passed",
        "generation": "passed",
        "candidate_pose": "passed",
        "layer_segmentation": "passed",
        "review": "passed" if accepted else "needs_review",
    }
    return EvalResult(
        case_id,
        "local-model",
        device,
        5_000,
        4 * _GIB,
        1,
        stages,
        private_context=context,
        stage_elapsed_ms={stage: 500 for stage in stages},
        peak_gpu_memory_bytes=None if cpu else 7 * _GIB,
    )


def _previews(results: list[EvalResult]) -> list[ActionPreview]:
    previews = []
    for result in results[:2]:
        context = result.private_context or {}
        character_id = str(context["character_reference_id"])
        for action in _ACTIONS:
            previews.append(
                ActionPreview(
                    action,
                    "ready",
                    (Path("frame.png"),),
                    60,
                    2.0,
                    character_reference_id=character_id,
                    reviewed=True,
                    case_id=result.case_id,
                )
            )
    return previews


def _complete_inputs() -> tuple[list[EvalResult], list[ActionPreview]]:
    results = [_result(number, device="cuda" if number == 5 else "cpu", accepted=number < 2) for number in range(6)]
    return results, _previews(results)


def test_gate_passes_only_with_six_consented_varied_samples_two_approved_characters_and_ten_reviewed_motions() -> None:
    results, previews = _complete_inputs()
    report = evaluate_p0(results, previews)
    assert report.status == "pass"
    assert report.real_case_count == 6
    assert report.approved_character_count == 2
    assert report.reviewed_action_count == 10


def test_gate_marks_missing_sample_and_machine_evidence_incomplete() -> None:
    results, previews = _complete_inputs()
    report = evaluate_p0(results[:3], previews[:5])
    assert report.status == "incomplete_samples"
    assert "six_consented_real_cases" in report.missing_evidence
    assert "supported_discrete_gpu_run" in report.missing_evidence
    assert "ten_reviewed_action_previews" in report.missing_evidence


def test_gate_rejects_missing_model_license_or_failed_action_evidence() -> None:
    results, previews = _complete_inputs()
    context = dict(results[0].private_context or {})
    context["model_evidence"] = {"licenses": []}
    bad_result = EvalResult(
        results[0].case_id, results[0].model_id, results[0].device_id, results[0].elapsed_ms,
        results[0].peak_memory_bytes, results[0].correction_count, results[0].stages,
        private_context=context, stage_elapsed_ms=results[0].stage_elapsed_ms,
    )
    rejected = list(results)
    rejected[0] = bad_result
    bad_previews = list(previews)
    bad_previews[0] = ActionPreview("idle", "needs_fix", (), 60, 2.0, defects=("silhouette_clipped",), reviewed=True,
                                    case_id=results[0].case_id, character_reference_id="000000000000000000000000")
    report = evaluate_p0(rejected, bad_previews)
    assert report.status == "fail"
    assert "model_license_evidence_missing" in report.failure_codes
    assert "reviewed_action_failed" in report.failure_codes


def test_gate_report_omits_local_paths_and_names(tmp_path: Path) -> None:
    results, previews = _complete_inputs()
    report_path = write_p0_gate_report(evaluate_p0(results, previews), tmp_path / "p0-gate.json")
    contents = report_path.read_text(encoding="utf-8")
    assert "C:\\Users" not in contents
    assert "example-person-name" not in contents


def test_local_evidence_includes_bounded_joint_correction_count(tmp_path: Path) -> None:
    revision = tmp_path / "cases" / "case_0123456789abcdef" / "revisions" / "rev_1"
    revision.mkdir(parents=True)
    evidence = {
        "schema_version": 1,
        "case_id": "case_0123456789abcdef",
        "model_id": "p0-local",
        "device_profile": {"gpu_name": None},
        "elapsed_ms": 1,
        "peak_memory_bytes": 1,
        "correction_count": 0,
        "stages": {},
    }
    (revision / "p0-eval-evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
    actions = revision / "p0-actions"
    actions.mkdir()
    (actions / "manifest.json").write_text(json.dumps({"schema_version": 1, "correction_count": 2, "actions": []}), encoding="utf-8")

    results, previews = load_local_p0_evidence(tmp_path)

    assert previews == []
    assert results[0].correction_count == 2
