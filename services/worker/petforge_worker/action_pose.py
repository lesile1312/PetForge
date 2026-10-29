from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from .device import DeviceProfile
from .providers.base import CancelToken, LayerSet, PortraitCandidate, PortraitRequest
from .rig_seed import Joint, RigSeed


_ACTIONS = {"idle", "run_left", "run_right", "wave_smile", "phone_crouch"}
_GENERATED_POSES = {
    "wave_smile": "same outfit and same face, standing full-body, gently waving with one raised hand and a small relaxed smile",
    "phone_crouch": "same outfit and same face, comfortable low squat, neck relaxed and eyes looking down at a smartphone held with both hands",
}
_DURATIONS = {"idle": 6.0, "run_left": 1.2, "run_right": 1.2, "wave_smile": 2.4, "phone_crouch": 5.0}
_FRAME_COUNTS = {"idle": 12, "run_left": 16, "run_right": 16, "wave_smile": 16, "phone_crouch": 24}


@dataclass(frozen=True, slots=True)
class ActionPoseCandidate:
    character_reference_id: str
    action_id: str
    landmarks_norm: dict[str, tuple[float, ...]]
    image_path: Path
    issues: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ActionPreview:
    action_id: str
    status: str
    frame_paths: tuple[Path, ...]
    fps_target: int
    duration_seconds: float
    issues: tuple[str, ...] = ()
    character_reference_id: str = ""
    reviewed: bool = False
    defects: tuple[str, ...] = ()
    case_id: str = ""


def _required_pose_issues(action_id: str, landmarks: dict[str, tuple[float, ...]]) -> tuple[str, ...]:
    issues: list[str] = []
    required = {"left_shoulder", "right_shoulder", "left_wrist", "right_wrist"}
    if action_id == "phone_crouch":
        required.update({"left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"})
    if required - landmarks.keys():
        return ("generated_pose_landmarks_missing",)
    if any(len(landmarks[name]) < 3 or landmarks[name][2] < 0.25 for name in required):
        return ("generated_pose_confidence_low",)
    if action_id == "wave_smile":
        raised = any(
            landmarks[f"{side}_wrist"][1] < landmarks[f"{side}_shoulder"][1] - 0.035 for side in ("left", "right")
        )
        if not raised:
            issues.append("wave_hand_not_raised")
    if action_id == "phone_crouch":
        bend_angles: list[float] = []
        for side in ("left", "right"):
            hip = landmarks[f"{side}_hip"]
            knee = landmarks[f"{side}_knee"]
            ankle = landmarks[f"{side}_ankle"]
            a = (hip[0] - knee[0], hip[1] - knee[1])
            b = (ankle[0] - knee[0], ankle[1] - knee[1])
            denom = math.hypot(*a) * math.hypot(*b)
            if denom == 0:
                bend_angles.append(180.0)
            else:
                bend_angles.append(math.degrees(math.acos(max(-1.0, min(1.0, (a[0] * b[0] + a[1] * b[1]) / denom)))))
        if min(bend_angles) > 155:
            issues.append("crouch_knees_not_bent")
    return tuple(issues)


def generate_action_pose(
    candidate: PortraitCandidate,
    rig: RigSeed,
    action_id: str,
    *,
    generator,
    detector,
    device: DeviceProfile,
    output_dir: Path,
    cancel: CancelToken | None = None,
) -> ActionPoseCandidate:
    if action_id not in _GENERATED_POSES:
        raise ValueError("unsupported_generated_action")
    if rig.status != "ready":
        raise ValueError("rig_unsupported")
    if _reference_id(candidate) != rig.character_reference_id:
        raise ValueError("character_reference_mismatch")
    seed_material = f"{rig.character_reference_id}:{action_id}".encode("ascii")
    seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:4], "big") & 0x7FFFFFFF
    request = PortraitRequest(
        source_path=Path(candidate.image_path),
        selected_crop_xywh_norm=(0.0, 0.0, 1.0, 1.0),
        style_preset="warm_chibi",
        clothing_description=None,
        inferred_regions=candidate.inferred_regions,
        seed=seed,
        pose_description=_GENERATED_POSES[action_id],
    )
    generated = generator.generate(request, device, Path(output_dir), cancel)
    people = detector.detect(generated.image_path)
    person = max(people, key=lambda item: item.confidence) if people else None
    landmarks = person.landmarks_norm if person else {}
    issues = _required_pose_issues(action_id, landmarks)
    return ActionPoseCandidate(rig.character_reference_id, action_id, landmarks, generated.image_path, issues)


def _reference_id(candidate: PortraitCandidate) -> str:
    digest = hashlib.sha256()
    with Path(candidate.image_path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:24]


def _joint_point(
    rig: RigSeed, name: str, size: tuple[int, int], *, mirrored: bool = False
) -> tuple[float, float] | None:
    joint = rig.joints.get(name)
    if joint is None:
        return None
    x = (1.0 - joint.x) if mirrored else joint.x
    return x * size[0], joint.y * size[1]


def _line_mask(size: tuple[int, int], start: tuple[float, float], middle: tuple[float, float], end: tuple[float, float], thickness: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.line((start, middle, end), fill=255, width=thickness, joint="curve")
    radius = thickness / 2
    for x, y in (start, middle, end):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    return mask


def _limb_source(
    image: Image.Image, rig: RigSeed, limb: str, *, mirrored: bool = False
) -> tuple[Image.Image | None, tuple[float, float] | None, Image.Image | None]:
    side, kind = limb.split("_")
    root_name, mid_name, tip_name = ((f"{side}_shoulder", f"{side}_elbow", f"{side}_wrist") if kind == "arm" else (f"{side}_hip", f"{side}_knee", f"{side}_ankle"))
    points = [_joint_point(rig, name, image.size, mirrored=mirrored) for name in (root_name, mid_name, tip_name)]
    if not all(points):
        return None, None, None
    root, middle, tip = points
    asset = rig.layer_refs.get(limb)
    try:
        if asset and asset.is_file():
            with Image.open(asset) as layer_file:
                layer = layer_file.convert("RGBA")
            if mirrored:
                mirrored_layer = ImageOps.mirror(layer)
                layer.close()
                layer = mirrored_layer
            mask = layer.getchannel("A")
        else:
            thickness = max(3, round(min(image.size) * (0.075 if kind == "arm" else 0.085)))
            mask = _line_mask(image.size, root, middle, tip, thickness)
            layer = image.copy()
            image_alpha = image.getchannel("A")
            limb_alpha = ImageChops.multiply(image_alpha, mask)
            layer.putalpha(limb_alpha)
            image_alpha.close()
            limb_alpha.close()
        return layer, root, mask
    except OSError:
        return None, None, None


def _motion_angles(action_id: str, phase: float) -> dict[str, float]:
    cycle = math.sin(phase * math.tau)
    if action_id.startswith("run_"):
        direction = -1 if action_id == "run_left" else 1
        return {
            "left_arm": direction * cycle * 28,
            "right_arm": -direction * cycle * 28,
            "left_leg": -direction * cycle * 34,
            "right_leg": direction * cycle * 34,
        }
    if action_id == "wave_smile":
        return {"right_arm": 0.0, "left_arm": math.sin(phase * math.tau) * 8}
    if action_id == "phone_crouch":
        elapsed = phase * _DURATIONS[action_id]
        tap = max(math.exp(-((elapsed - tap_time) / 0.16) ** 2) for tap_time in (1.15, 2.65, 3.85))
        return {
            "left_arm": math.sin(phase * math.tau) * 1.5 + tap * 0.8,
            "right_arm": -math.sin(phase * math.tau) * 1.5 - tap * 1.3,
        }
    return {"left_arm": math.sin(phase * math.tau) * 1.2, "right_arm": -math.sin(phase * math.tau) * 1.2}


def _render_rig_frame(image: Image.Image, rig: RigSeed, action_id: str, phase: float, *, mirrored: bool) -> Image.Image:
    source = ImageOps.mirror(image) if mirrored else image.copy()
    width, height = source.size
    source_alpha = source.getchannel("A")
    limb_data: list[tuple[str, Image.Image, tuple[float, float], Image.Image]] = []
    removed = Image.new("L", source.size, 0)
    for limb in ("left_leg", "right_leg", "left_arm", "right_arm"):
        layer, pivot, mask = _limb_source(source, rig, limb, mirrored=mirrored)
        if layer is None or pivot is None or mask is None:
            continue
        next_removed = ImageChops.lighter(removed, mask)
        removed.close()
        removed = next_removed
        limb_data.append((limb, layer, pivot, mask))
    base_alpha = ImageChops.subtract(source_alpha, removed)
    base = source.copy()
    base.putalpha(base_alpha)
    angles = _motion_angles(action_id, phase)
    for limb, layer, pivot, _mask in sorted(limb_data, key=lambda item: 0 if item[0].endswith("leg") else 1):
        angle = angles.get(limb, 0.0)
        moved = layer.rotate(angle, resample=Image.Resampling.BICUBIC, center=pivot, expand=False)
        base.alpha_composite(moved)
        moved.close()
        layer.close()
    if not limb_data:
        base.close()
        base = source.copy()
    if action_id.startswith("run_"):
        bob = round(abs(math.sin(phase * math.tau)) * min(3, max(1, height * 0.006)))
        frame = Image.new("RGBA", source.size, (0, 0, 0, 0))
        frame.alpha_composite(base, (0, -bob))
        base.close()
        base = frame
    elif action_id == "idle":
        bob = round(math.sin(phase * math.tau) * min(1, max(0, height * 0.002)))
        if bob:
            frame = Image.new("RGBA", source.size, (0, 0, 0, 0))
            frame.alpha_composite(base, (0, -bob))
            base.close()
            base = frame
    for _, _, _, mask in limb_data:
        mask.close()
    source.close()
    source_alpha.close()
    removed.close()
    base_alpha.close()
    return base


def render_action_preview(
    candidate: PortraitCandidate,
    rig: RigSeed,
    action_id: str,
    key_pose: ActionPoseCandidate | None = None,
    *,
    output_dir: Path | None = None,
    case_id: str = "",
) -> ActionPreview:
    if action_id not in _ACTIONS:
        raise ValueError("unsupported_action")
    if rig.status != "ready":
        return ActionPreview(
            action_id, "unsupported", (), 60, _DURATIONS[action_id], rig.issues, rig.character_reference_id,
            case_id=case_id,
        )
    complex_action = action_id in _GENERATED_POSES
    if complex_action:
        if key_pose is None or key_pose.action_id != action_id or key_pose.character_reference_id != rig.character_reference_id:
            raise ValueError("matching_key_pose_required")
    if _reference_id(candidate) != rig.character_reference_id:
        raise ValueError("character_reference_mismatch")
    issues = list(key_pose.issues if key_pose else ())
    if rig.editable_joints:
        issues.append("low_confidence_joints_editable")
    status = "needs_fix" if issues else "ready"
    root = Path(output_dir) if output_dir is not None else Path(candidate.image_path).parent / "action-previews" / action_id
    root.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    with Image.open(candidate.image_path) as candidate_file:
        image = candidate_file.convert("RGBA")
    key_image: Image.Image | None = None
    if complex_action and key_pose and Path(key_pose.image_path).is_file():
        with Image.open(key_pose.image_path) as key_file:
            key_image = key_file.convert("RGBA")
        if key_image.size != image.size:
            key_image = ImageOps.contain(key_image, image.size, method=Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", image.size, (0, 0, 0, 0))
            canvas.alpha_composite(key_image, ((image.width - key_image.width) // 2, (image.height - key_image.height) // 2))
            key_image.close()
            key_image = canvas
    elif complex_action:
        status = "needs_fix"
        issues.append("key_pose_image_missing")

    frame_count = _FRAME_COUNTS[action_id]
    for index in range(frame_count):
        phase = index / frame_count
        frame = _render_rig_frame(image, rig, action_id, phase, mirrored=(action_id == "run_left"))
        if key_image is not None:
            if action_id == "wave_smile":
                blend = 0.0 if phase < 0.15 or phase > 0.88 else min(1.0, (phase - 0.15) / 0.16, (0.88 - phase) / 0.12)
            else:
                blend = 0.0 if phase < 0.12 or phase > 0.92 else min(1.0, (phase - 0.12) / 0.12, (0.92 - phase) / 0.12)
            if blend > 0:
                mixed = Image.blend(frame, key_image, min(0.92, blend))
                frame.close()
                frame = mixed
        frame_path = root / f"frame-{index:03d}.png"
        frame.save(frame_path, format="PNG", optimize=False)
        frame.close()
        frames.append(frame_path)
    if key_image:
        key_image.close()
    image.close()
    return ActionPreview(
        action_id,
        status,
        tuple(frames),
        60,
        _DURATIONS[action_id],
        tuple(dict.fromkeys(issues)),
        rig.character_reference_id,
        case_id=case_id,
    )
