from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .providers.base import LayerSet, PortraitCandidate


_REQUIRED_LAYERS = frozenset({"torso", "left_arm", "right_arm", "left_leg", "right_leg", "face", "hair", "eyes"})
_ACTION_JOINTS = frozenset(
    {
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
    }
)
_JOINTS = frozenset(
    {
        "nose",
        "left_eye",
        "right_eye",
        "left_ear",
        "right_ear",
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
    }
)
SUPPORTED_JOINTS = _JOINTS
_CORRECTION_LIMIT = 0.05
_EDITABLE_CONFIDENCE = 0.65


@dataclass(frozen=True, slots=True)
class Landmark:
    name: str
    x: float
    y: float
    confidence: float


@dataclass(frozen=True, slots=True)
class LandmarkCorrection:
    name: str
    dx: float
    dy: float


@dataclass(frozen=True, slots=True)
class Joint:
    x: float
    y: float
    confidence: float
    editable: bool

    @property
    def xy(self) -> tuple[float, float]:
        return self.x, self.y


@dataclass(frozen=True, slots=True)
class RigSeed:
    status: str
    character_reference_id: str
    joints: dict[str, Joint]
    feet_baseline: float | None
    layer_refs: dict[str, Path]
    missing_layers: tuple[str, ...]
    missing_joints: tuple[str, ...]
    editable_joints: tuple[str, ...]
    issues: tuple[str, ...]


def _reference_id(candidate: PortraitCandidate) -> str:
    digest = hashlib.sha256()
    with Path(candidate.image_path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:24]


def seed_rig(
    candidate: PortraitCandidate,
    landmarks: list[Landmark],
    corrections: list[LandmarkCorrection] | None = None,
    *,
    layers: LayerSet | None = None,
) -> RigSeed:
    correction_by_name: dict[str, LandmarkCorrection] = {}
    for correction in corrections or []:
        if correction.name not in _JOINTS or correction.name in correction_by_name:
            raise ValueError("invalid_landmark_correction")
        if not (-1 <= correction.dx <= 1 and -1 <= correction.dy <= 1):
            raise ValueError("invalid_landmark_correction")
        correction_by_name[correction.name] = correction

    if layers is None:
        stored_layers = candidate.provenance.get("layers")
        layers = stored_layers if isinstance(stored_layers, LayerSet) else LayerSet({})
    layer_refs = {name: asset.path for name, asset in layers.assets.items() if name in _REQUIRED_LAYERS}
    missing_layers = tuple(sorted((_REQUIRED_LAYERS - layer_refs.keys()) | set(layers.missing_layers)))
    joints: dict[str, Joint] = {}
    seen: set[str] = set()
    for landmark in landmarks:
        if landmark.name not in _JOINTS or landmark.name in seen:
            raise ValueError("invalid_landmark_name")
        seen.add(landmark.name)
        if not all(0 <= value <= 1 for value in (landmark.x, landmark.y, landmark.confidence)):
            raise ValueError("landmark_out_of_bounds")
        correction = correction_by_name.get(landmark.name)
        dx = max(-_CORRECTION_LIMIT, min(_CORRECTION_LIMIT, correction.dx)) if correction else 0.0
        dy = max(-_CORRECTION_LIMIT, min(_CORRECTION_LIMIT, correction.dy)) if correction else 0.0
        x = min(1.0, max(0.0, landmark.x + dx))
        y = min(1.0, max(0.0, landmark.y + dy))
        joints[landmark.name] = Joint(
            x,
            y,
            landmark.confidence,
            editable=landmark.confidence < _EDITABLE_CONFIDENCE and correction is None,
        )
    unknown_corrections = set(correction_by_name) - seen
    if unknown_corrections:
        raise ValueError("correction_landmark_missing")

    ankle_values = [joints[name].y for name in ("left_ankle", "right_ankle") if name in joints]
    feet_baseline = sum(ankle_values) / len(ankle_values) if ankle_values else None
    missing_joints = tuple(sorted(_ACTION_JOINTS - joints.keys()))
    editable = tuple(sorted(name for name, joint in joints.items() if joint.editable))
    issues: list[str] = []
    if missing_layers:
        issues.append("missing_required_layers")
    if missing_joints:
        issues.append("required_joints_missing")
    if editable:
        issues.append("low_confidence_joints")
    if feet_baseline is None:
        issues.append("feet_baseline_missing")
    return RigSeed(
        status="unsupported" if missing_layers or missing_joints else "ready",
        character_reference_id=_reference_id(candidate),
        joints=joints,
        feet_baseline=feet_baseline,
        layer_refs=layer_refs,
        missing_layers=missing_layers,
        missing_joints=missing_joints,
        editable_joints=editable,
        issues=tuple(issues),
    )
