from pathlib import Path

from PIL import Image
import pytest

from petforge_worker.providers.base import LayerAsset, LayerSet, PortraitCandidate
from petforge_worker.rig_seed import Landmark, LandmarkCorrection, seed_rig


def _candidate(tmp_path: Path, *, omit: tuple[str, ...] = ()) -> PortraitCandidate:
    image = tmp_path / "candidate.png"
    mask = tmp_path / "mask.png"
    Image.new("RGBA", (100, 200), (255, 255, 255, 255)).save(image)
    Image.new("L", (100, 200), 255).save(mask)
    layer_ids = {"torso", "left_arm", "right_arm", "left_leg", "right_leg", "face", "hair", "eyes"}
    layers = LayerSet(
        assets={layer_id: LayerAsset(tmp_path / f"{layer_id}.png", 0.9) for layer_id in layer_ids - set(omit)},
    )
    return PortraitCandidate(image, mask, provenance={"layers": layers})


def _landmarks() -> list[Landmark]:
    return [
        Landmark("nose", 0.50, 0.14, 0.9),
        Landmark("left_shoulder", 0.35, 0.30, 0.8),
        Landmark("right_shoulder", 0.65, 0.30, 0.8),
        Landmark("left_elbow", 0.28, 0.45, 0.8),
        Landmark("left_wrist", 0.25, 0.56, 0.8),
        Landmark("right_elbow", 0.72, 0.45, 0.8),
        Landmark("right_wrist", 0.75, 0.56, 0.8),
        Landmark("left_hip", 0.42, 0.59, 0.8),
        Landmark("right_hip", 0.58, 0.59, 0.8),
        Landmark("left_knee", 0.43, 0.76, 0.8),
        Landmark("left_ankle", 0.41, 0.95, 0.8),
        Landmark("right_knee", 0.59, 0.76, 0.8),
        Landmark("right_ankle", 0.61, 0.93, 0.8),
    ]


def test_seed_rig_uses_normalized_joints_and_stable_character_reference(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    first = seed_rig(candidate, _landmarks())
    second = seed_rig(candidate, _landmarks())
    assert first.status == "ready"
    assert first.character_reference_id == second.character_reference_id
    assert first.joints["left_wrist"].xy == (0.25, 0.56)
    assert first.feet_baseline == 0.94
    assert first.layer_refs["torso"] == tmp_path / "torso.png"


def test_seed_rig_manual_correction_verifies_low_confidence_joint_within_bounds(tmp_path: Path) -> None:
    landmarks = _landmarks()
    landmarks[4] = Landmark("left_wrist", 0.25, 0.56, 0.2)
    rig = seed_rig(
        _candidate(tmp_path),
        landmarks,
        [LandmarkCorrection("left_wrist", dx=0.5, dy=-0.5)],
    )
    assert rig.status == "ready"
    assert rig.joints["left_wrist"].xy == (0.30, 0.51)
    assert rig.joints["left_wrist"].confidence == 0.2
    assert rig.joints["left_wrist"].editable is False
    assert "left_wrist" not in rig.editable_joints


def test_seed_rig_rejects_non_normalized_landmarks_and_reports_missing_layers(tmp_path: Path) -> None:
    bad = _landmarks()
    bad[0] = Landmark("nose", 1.5, -0.2, 0.9)
    candidate = _candidate(tmp_path, omit=("left_leg",))
    with pytest.raises(ValueError, match="landmark_out_of_bounds"):
        seed_rig(candidate, bad)
    rig = seed_rig(candidate, _landmarks())
    assert rig.status == "unsupported"
    assert "missing_required_layers" in rig.issues
    assert "left_leg" in rig.missing_layers


def test_seed_rig_rejects_missing_joints_used_by_continuous_actions(tmp_path: Path) -> None:
    landmarks = [item for item in _landmarks() if item.name != "right_wrist"]

    rig = seed_rig(_candidate(tmp_path), landmarks)

    assert rig.status == "unsupported"
    assert rig.missing_joints == ("right_wrist",)
    assert "required_joints_missing" in rig.issues
