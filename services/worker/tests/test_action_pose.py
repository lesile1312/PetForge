from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from petforge_worker.action_pose import ActionPoseCandidate, _motion_angles, generate_action_pose, render_action_preview
from petforge_worker.device import DeviceProfile
from petforge_worker.pose_control import POSE_TEMPLATES, write_openpose_control
from petforge_worker.providers.base import LayerAsset, LayerSet, PortraitCandidate
from petforge_worker.rig_seed import Landmark, seed_rig


def _rig(tmp_path: Path):
    image_path, mask_path = tmp_path / "candidate.png", tmp_path / "mask.png"
    Image.new("RGBA", (64, 96), (255, 255, 255, 255)).save(image_path)
    Image.new("L", (64, 96), 255).save(mask_path)
    layers = LayerSet({key: LayerAsset(tmp_path / f"{key}.png", 0.9) for key in (
        "torso", "left_arm", "right_arm", "left_leg", "right_leg", "face", "hair", "eyes"
    )})
    candidate = PortraitCandidate(image_path, mask_path, provenance={"layers": layers})
    names = ("nose", "left_shoulder", "right_shoulder", "left_elbow", "left_wrist", "right_elbow",
             "right_wrist", "left_hip", "right_hip", "left_knee", "left_ankle", "right_knee", "right_ankle")
    points = ((.5,.15),(.35,.3),(.65,.3),(.3,.45),(.25,.55),(.7,.45),(.75,.55),(.42,.6),(.58,.6),(.43,.75),(.41,.94),(.59,.75),(.61,.94))
    rig = seed_rig(candidate, [Landmark(name, x, y, .9) for name, (x,y) in zip(names, points)])
    return candidate, rig


def test_action_pose_only_accepts_reference_conditioned_gestures_and_keeps_identity(tmp_path: Path) -> None:
    candidate, rig = _rig(tmp_path)
    requests = []
    class FakeGenerator:
        def generate(self, request, device, output_dir, cancel=None):
            requests.append(request)
            assert request.source_path == candidate.image_path
            assert request.pose_description
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            image_path, mask_path = Path(output_dir) / "pose.png", Path(output_dir) / "mask.png"
            Image.new("RGBA", (64, 96), (255, 255, 255, 255)).save(image_path)
            Image.new("L", (64, 96), 255).save(mask_path)
            return PortraitCandidate(image_path, mask_path)
    class FakeDetector:
        def detect(self, image_path):
            return [type("Person", (), {"landmarks_norm": {"left_wrist": (.25, .2, .9), "right_wrist": (.75, .55, .9), "left_knee": (.4, .7, .9), "right_knee": (.6, .7, .9)}, "confidence": .9})()]
    device = DeviceProfile(
        os_name="Windows",
        architecture="AMD64",
        total_ram_bytes=16_000_000_000,
        available_ram_bytes=8_000_000_000,
        gpu_name=None,
        gpu_memory_bytes=None,
        gpu_driver_version=None,
        cpu_reference_supported=True,
        unsupported_reasons=(),
    )
    pose = generate_action_pose(
        candidate,
        rig,
        "wave_smile",
        generator=FakeGenerator(),
        detector=FakeDetector(),
        device=device,
        output_dir=tmp_path / "wave",
    )
    assert pose.action_id == "wave_smile"
    assert pose.character_reference_id == rig.character_reference_id
    assert pose.landmarks_norm["left_wrist"][1] == .2
    assert pose.image_path.is_file()
    assert requests[0].pose_control_image.is_file()
    assert requests[0].pose_control_image.parent == tmp_path / "wave"


def test_pose_controls_are_full_body_openpose_maps(tmp_path: Path) -> None:
    control_paths = {
        action: write_openpose_control(action, (128, 192), tmp_path / f"{action}.png")
        for action in POSE_TEMPLATES
    }

    assert set(control_paths) == {"idle", "wave_smile", "phone_crouch"}
    maps = {}
    for action, path in control_paths.items():
        with Image.open(path) as control:
            assert control.size == (128, 192)
            assert control.mode == "RGB"
            maps[action] = control.tobytes()
    assert len(set(maps.values())) == len(maps)


def test_unknown_or_mismatched_action_key_pose_is_rejected(tmp_path: Path) -> None:
    candidate, rig = _rig(tmp_path)
    with pytest.raises(ValueError, match="unsupported_action"):
        render_action_preview(candidate, rig, "mirror", output_dir=tmp_path / "preview")
    wrong_pose = ActionPoseCandidate(rig.character_reference_id, "phone_crouch", {}, candidate.image_path)
    with pytest.raises(ValueError, match="matching_key_pose_required"):
        render_action_preview(candidate, rig, "wave_smile", key_pose=wrong_pose, output_dir=tmp_path / "preview")


def test_five_action_previews_emit_original_scale_frames_at_60hz_target(tmp_path: Path) -> None:
    candidate, rig = _rig(tmp_path)
    wave = ActionPoseCandidate(rig.character_reference_id, "wave_smile", {}, candidate.image_path)
    phone = ActionPoseCandidate(rig.character_reference_id, "phone_crouch", {}, candidate.image_path)
    previews = [
        render_action_preview(candidate, rig, action, key_pose=key, output_dir=tmp_path / action)
        for action, key in (("idle", None), ("run_left", None), ("run_right", None), ("wave_smile", wave), ("phone_crouch", phone))
    ]
    assert all(preview.status == "ready" and preview.fps_target == 60 for preview in previews)
    assert all(preview.frame_paths and all(path.is_file() for path in preview.frame_paths) for preview in previews)
    assert all(Image.open(preview.frame_paths[0]).size == (64, 96) for preview in previews)


def test_phone_pose_has_brief_tap_gestures_during_long_hold() -> None:
    tap = _motion_angles("phone_crouch", 1.15 / 5.0)
    rest = _motion_angles("phone_crouch", 1.8 / 5.0)
    assert abs(tap["right_arm"] - rest["right_arm"]) > 0.8


def test_key_pose_transition_fades_alpha_instead_of_unioning_two_silhouettes(tmp_path: Path) -> None:
    base_candidate, _ = _rig(tmp_path)
    layers = base_candidate.provenance["layers"]
    image_path, mask_path = tmp_path / "transition-source.png", tmp_path / "transition-mask.png"
    source_image = Image.new("RGBA", (64, 96), (0, 0, 0, 0))
    ImageDraw.Draw(source_image).rectangle((5, 5, 20, 20), fill=(255, 0, 0, 255))
    source_image.save(image_path)
    source_image.getchannel("A").save(mask_path)
    candidate = PortraitCandidate(image_path, mask_path, provenance={"layers": layers})
    rig_dir = tmp_path / "rig"
    rig_dir.mkdir()
    _, rig = _rig(rig_dir)
    from petforge_worker.rig_seed import Landmark, seed_rig

    rig = seed_rig(candidate, [
        Landmark(name, joint.x, joint.y, joint.confidence) for name, joint in rig.joints.items()
    ])
    pose_path = tmp_path / "transition-pose.png"
    pose_image = Image.new("RGBA", (64, 96), (0, 0, 0, 0))
    ImageDraw.Draw(pose_image).rectangle((43, 5, 58, 20), fill=(0, 0, 255, 255))
    pose_image.save(pose_path)
    key_pose = ActionPoseCandidate(rig.character_reference_id, "wave_smile", {}, pose_path)

    preview = render_action_preview(
        candidate,
        rig,
        "wave_smile",
        key_pose=key_pose,
        output_dir=tmp_path / "transition",
    )

    with Image.open(preview.frame_paths[4]) as frame:
        alpha = frame.getchannel("A")
        assert 80 <= alpha.getpixel((10, 10)) <= 110
        assert 145 <= alpha.getpixel((50, 10)) <= 175
