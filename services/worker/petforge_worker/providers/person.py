from __future__ import annotations

from pathlib import Path

from PIL import Image

from .base import PersonCandidate


_POSE_NAMES = {
    0: "nose",
    1: "left_eye_inner",
    2: "left_eye",
    3: "left_eye_outer",
    4: "right_eye_inner",
    5: "right_eye",
    6: "right_eye_outer",
    7: "left_ear",
    8: "right_ear",
    11: "left_shoulder",
    12: "right_shoulder",
    13: "left_elbow",
    14: "right_elbow",
    15: "left_wrist",
    16: "right_wrist",
    23: "left_hip",
    24: "right_hip",
    25: "left_knee",
    26: "right_knee",
    27: "left_ankle",
    28: "right_ankle",
    29: "left_heel",
    30: "right_heel",
    31: "left_foot",
    32: "right_foot",
}


class MediaPipePersonDetector:
    """Pose-based person boxes and normalized landmarks for explicit selection."""

    def __init__(self, model_path: Path, num_poses: int = 4):
        if not Path(model_path).is_file():
            raise FileNotFoundError("pose_landmarker_weights_missing")
        if num_poses < 1 or num_poses > 8:
            raise ValueError("invalid_num_poses")
        self.model_path = Path(model_path)
        self.num_poses = num_poses
        self._landmarker = None

    def _load(self):
        if self._landmarker is not None:
            return self._landmarker
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        options = vision.PoseLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=vision.RunningMode.IMAGE,
            num_poses=self.num_poses,
            min_pose_detection_confidence=0.35,
            min_pose_presence_confidence=0.35,
            min_tracking_confidence=0.35,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        return self._landmarker

    def detect(self, source_path: Path) -> list[PersonCandidate]:
        import numpy as np
        import mediapipe as mp

        with Image.open(source_path) as source_image:
            rgba = source_image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            background.alpha_composite(rgba)
            image = np.asarray(background.convert("RGB"))
            background.close()
            rgba.close()
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
        result = self._load().detect(mp_image)
        candidates: list[PersonCandidate] = []
        for pose in result.pose_landmarks or []:
            points: dict[str, tuple[float, ...]] = {}
            visible: list[tuple[float, float]] = []
            scores: list[float] = []
            for index, landmark in enumerate(pose):
                name = _POSE_NAMES.get(index)
                if not name:
                    continue
                x, y = float(landmark.x), float(landmark.y)
                if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                    continue
                confidence = float(landmark.visibility or landmark.presence or 0.0)
                point = (x, y, confidence)
                points[name] = point
                if confidence >= 0.2:
                    visible.append((x, y))
                    scores.append(confidence)
            if len(visible) < 5:
                continue
            left = max(0.0, min(point[0] for point in visible))
            top = max(0.0, min(point[1] for point in visible))
            right = min(1.0, max(point[0] for point in visible))
            bottom = min(1.0, max(point[1] for point in visible))
            if right <= left or bottom <= top:
                continue
            candidates.append(
                PersonCandidate(
                    bbox_xywh_norm=(left, top, right - left, bottom - top),
                    landmarks_norm=points,
                    confidence=sum(scores) / len(scores),
                )
            )
        return candidates
