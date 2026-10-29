import json
from importlib import import_module
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from petforge_worker.benchmark import (
    DeterministicFakeCutoutProvider,
    DeterministicFakeLayerSegmenter,
    DeterministicFakePersonDetector,
    DeterministicFakePortraitGenerator,
    run_case,
)
from petforge_worker.corpus import EvalCase
from petforge_worker.providers.base import LayerAsset, LayerSet, PortraitCandidate
from petforge_worker.rig_seed import Landmark, seed_rig
from petforge_worker.action_pose import ActionPreview


def _api():
    try:
        return import_module("petforge_worker.cli")
    except ModuleNotFoundError:
        pytest.fail("photo worker CLI is not implemented")


def test_manual_crop_requires_four_integer_pixel_values():
    api = _api()
    assert api._crop_arg("1,2,300,400") == (1, 2, 300, 400)
    with pytest.raises(ValueError, match="crop_must_be_x_y_width_height"):
        api._crop_arg("1,2,3")


def test_generate_requires_explicit_local_photo_consent_before_models(tmp_path, capsys):
    api = _api()
    args = api._parser().parse_args(["generate", "--input", str(tmp_path / "not-read.jpg")])

    result = api._generate(args)

    assert result == 2
    assert "Pass --consent" in capsys.readouterr().err


def test_cli_parser_keeps_person_choice_and_manual_crop_mutually_exclusive(tmp_path):
    api = _api()
    with pytest.raises(SystemExit):
        api._parser().parse_args(
            ["generate", "--input", str(tmp_path / "photo.jpg"), "--person-index", "0", "--crop", "0,0,10,10"]
        )


def test_landmark_corrections_are_normalized_bounded_and_unique():
    api = _api()

    corrections = api._parse_landmark_corrections(["left_wrist=0.02,-0.03", "right_ankle=0,0.05"])

    assert [(item.name, item.dx, item.dy) for item in corrections] == [
        ("left_wrist", 0.02, -0.03),
        ("right_ankle", 0.0, 0.05),
    ]
    with pytest.raises(ValueError, match="invalid_landmark_correction"):
        api._parse_landmark_corrections(["left_wrist=0.051,0"])
    with pytest.raises(ValueError, match="invalid_landmark_correction"):
        api._parse_landmark_corrections(["left_wrist=0,0", "left_wrist=0,0"])


def test_rig_manifest_keeps_all_asset_paths_relative_and_splits_eyes(tmp_path):
    api = _api()
    image_path = tmp_path / "candidate.png"
    mask_path = tmp_path / "mask.png"
    Image.new("RGBA", (64, 96), (210, 180, 160, 255)).save(image_path)
    Image.new("L", (64, 96), 255).save(mask_path)
    layer_paths = {}
    for name in ("torso", "left_arm", "right_arm", "left_leg", "right_leg", "face", "hair", "eyes"):
        path = tmp_path / "layers" / f"{name}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        layer = Image.new("RGBA", (64, 96), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        if name == "eyes":
            draw.ellipse((25, 18, 28, 21), fill=(25, 20, 20, 255))
            draw.ellipse((36, 18, 39, 21), fill=(25, 20, 20, 255))
        else:
            draw.rectangle((20, 20, 22, 22), fill=(210, 180, 160, 255))
        layer.save(path)
        layer_paths[name] = path
    candidate = PortraitCandidate(image_path, mask_path)
    layers = LayerSet({name: LayerAsset(path, 0.9) for name, path in layer_paths.items()})
    names = (
        "nose", "left_eye", "right_eye", "left_ear", "right_ear", "left_shoulder", "right_shoulder",
        "left_elbow", "right_elbow", "left_wrist", "right_wrist", "left_hip", "right_hip",
        "left_knee", "right_knee", "left_ankle", "right_ankle",
    )
    points = (
        (.5, .2), (.42, .2), (.58, .2), (.35, .2), (.65, .2), (.36, .3), (.64, .3), (.32, .4), (.68, .4),
        (.28, .5), (.72, .5), (.42, .6), (.58, .6), (.4, .76), (.6, .76), (.38, .94), (.62, .94),
    )
    rig = seed_rig(candidate, [Landmark(name, x, y, 0.9) for name, (x, y) in zip(names, points)], layers=layers)
    output = tmp_path / "p0-actions"
    relative_manifest = api._write_rig_manifest(candidate, rig, output / "rig" / "source", output)
    manifest = json.loads((output / relative_manifest).read_text(encoding="utf-8"))

    assert not Path(relative_manifest).is_absolute()
    assert not Path(manifest["base_body"]).is_absolute()
    assert (output / manifest["base_body"]).is_file()
    assert (output / manifest["layers"]["eyes"]["path"]).is_file()
    with Image.open(output / manifest["base_body"]) as base_body:
        assert base_body.getchannel("A").getpixel((26, 19)) == 0


@pytest.mark.parametrize("action_id", ["wave_smile", "phone_crouch"])
def test_complex_action_cannot_be_ready_without_its_runtime_pose_rig(action_id):
    api = _api()
    preview = ActionPreview(action_id, "ready", (), 60, 2.4)

    result = api._require_generated_pose_rig(preview, {})

    assert result.status == "needs_fix"
    assert "key_pose_rig_unavailable" in result.issues


def _pending_candidate(tmp_path: Path) -> Path:
    source = tmp_path / "consented-source.png"
    Image.new("RGB", (64, 96), "#f0d0c0").save(source)
    case = EvalCase("case_0123456789abcdef", source, "real_person", True, True)
    result = run_case(
        case,
        detector=DeterministicFakePersonDetector(),
        cutout=DeterministicFakeCutoutProvider(),
        generator=DeterministicFakePortraitGenerator(),
        segmenter=DeterministicFakeLayerSegmenter(),
        output_root=tmp_path / "evaluations",
    )
    assert result.error_code is None
    return Path(result.private_context["candidate_directory"])


def test_candidate_review_accepts_existing_pending_candidate_without_regeneration(tmp_path):
    api = _api()
    candidate_dir = _pending_candidate(tmp_path)
    candidate_before = (candidate_dir / "generated" / "candidate.png").read_bytes()
    args = api._parser().parse_args([
        "review-candidate", "--candidate-dir", str(candidate_dir), "--decision", "accept"
    ])

    result = api._review_candidate(args)

    case_root = tmp_path / "evaluations" / "cases" / "case_0123456789abcdef"
    accepted = json.loads((case_root / "accepted.json").read_text(encoding="utf-8"))
    revision_dir = case_root / accepted["revision"]
    candidate = json.loads((revision_dir / "p0-candidate.json").read_text(encoding="utf-8"))
    evidence = json.loads((revision_dir / "p0-eval-evidence.json").read_text(encoding="utf-8"))

    assert result == 0
    assert candidate["state"] == "revisions" and candidate["accepted"] is True
    assert evidence["owner_approved_character"] is True
    assert evidence["stages"]["review"] == "passed"
    assert (revision_dir / "generated" / "candidate.png").read_bytes() == candidate_before


def test_candidate_review_rejection_is_preserved_and_fails_p0_gate(tmp_path):
    api = _api()
    candidate_dir = _pending_candidate(tmp_path)
    args = api._parser().parse_args([
        "review-candidate", "--candidate-dir", str(candidate_dir), "--decision", "reject"
    ])

    result = api._review_candidate(args)

    case_root = tmp_path / "evaluations" / "cases" / "case_0123456789abcdef"
    rejected_dir = next((case_root / "rejected").iterdir())
    evidence = json.loads((rejected_dir / "p0-eval-evidence.json").read_text(encoding="utf-8"))
    gate_results, previews = api.load_local_p0_evidence(tmp_path / "evaluations")
    gate = api.evaluate_p0(gate_results, previews)

    assert result == 0
    assert evidence["stages"]["review"] == "rejected"
    assert evidence["owner_approved_character"] is False
    assert (rejected_dir / "generated" / "candidate.png").is_file()
    assert "character_review_rejected" in gate.failure_codes


def test_candidate_rig_ignores_detector_landmarks_outside_joint_contract(tmp_path):
    api = _api()
    candidate_dir = _pending_candidate(tmp_path)
    pose_path = candidate_dir / "candidate-pose.json"
    pose = json.loads(pose_path.read_text(encoding="utf-8"))
    pose["landmarks_norm"]["left_eye_inner"] = [0.48, 0.17, 0.9]
    pose["landmarks_norm"]["left_heel"] = [0.42, 0.95, 0.8]
    pose_path.write_text(json.dumps(pose), encoding="utf-8")

    _, _, rig = api._load_reviewable_candidate(candidate_dir)

    assert rig.status == "ready"
    assert "left_eye_inner" not in rig.joints
    assert "left_heel" not in rig.joints
