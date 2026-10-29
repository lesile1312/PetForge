from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


POSE_TEMPLATES: dict[str, dict[str, tuple[float, float]]] = {
    "idle": {
        "nose": (0.50, 0.10), "neck": (0.50, 0.22),
        "right_shoulder": (0.62, 0.28), "right_elbow": (0.66, 0.42), "right_wrist": (0.68, 0.55),
        "left_shoulder": (0.38, 0.28), "left_elbow": (0.34, 0.42), "left_wrist": (0.32, 0.55),
        "mid_hip": (0.50, 0.59), "right_hip": (0.56, 0.59), "right_knee": (0.57, 0.76),
        "right_ankle": (0.58, 0.93), "left_hip": (0.44, 0.59), "left_knee": (0.43, 0.76),
        "left_ankle": (0.42, 0.93), "right_eye": (0.48, 0.095), "left_eye": (0.52, 0.095),
        "right_ear": (0.45, 0.11), "left_ear": (0.55, 0.11),
    },
    "wave_smile": {
        "nose": (0.50, 0.10), "neck": (0.50, 0.22),
        "right_shoulder": (0.62, 0.28), "right_elbow": (0.72, 0.21), "right_wrist": (0.77, 0.12),
        "left_shoulder": (0.38, 0.28), "left_elbow": (0.34, 0.42), "left_wrist": (0.32, 0.55),
        "mid_hip": (0.50, 0.59), "right_hip": (0.56, 0.59), "right_knee": (0.57, 0.76),
        "right_ankle": (0.58, 0.93), "left_hip": (0.44, 0.59), "left_knee": (0.43, 0.76),
        "left_ankle": (0.42, 0.93), "right_eye": (0.48, 0.095), "left_eye": (0.52, 0.095),
        "right_ear": (0.45, 0.11), "left_ear": (0.55, 0.11),
    },
    "phone_crouch": {
        "nose": (0.50, 0.18), "neck": (0.50, 0.31),
        "right_shoulder": (0.62, 0.35), "right_elbow": (0.59, 0.45), "right_wrist": (0.53, 0.55),
        "left_shoulder": (0.38, 0.35), "left_elbow": (0.41, 0.45), "left_wrist": (0.47, 0.55),
        "mid_hip": (0.50, 0.57), "right_hip": (0.57, 0.57), "right_knee": (0.70, 0.76),
        "right_ankle": (0.63, 0.90), "left_hip": (0.43, 0.57), "left_knee": (0.30, 0.76),
        "left_ankle": (0.37, 0.90), "right_eye": (0.48, 0.18), "left_eye": (0.52, 0.18),
        "right_ear": (0.45, 0.19), "left_ear": (0.55, 0.19),
    },
}

_EDGES = (
    ("neck", "right_shoulder"), ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
    ("neck", "left_shoulder"), ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
    ("neck", "mid_hip"), ("mid_hip", "right_hip"), ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"), ("mid_hip", "left_hip"), ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"), ("neck", "nose"), ("nose", "right_eye"), ("right_eye", "right_ear"),
    ("nose", "left_eye"), ("left_eye", "left_ear"),
)
_COLORS = (
    (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0),
    (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
    (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85),
)


def write_openpose_control(action_id: str, size: tuple[int, int], output_path: Path) -> Path:
    if action_id not in POSE_TEMPLATES:
        raise ValueError("unsupported_pose_control_action")
    width, height = size
    if width < 16 or height < 16:
        raise ValueError("invalid_pose_control_size")
    points = POSE_TEMPLATES[action_id]
    image = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(image)
    thickness = max(2, round(min(size) * 0.035))
    radius = max(2, round(thickness * 0.52))

    def pixel(name: str) -> tuple[int, int]:
        x, y = points[name]
        return round(x * (width - 1)), round(y * (height - 1))

    for color_index, (start, end) in enumerate(_EDGES):
        draw.line((pixel(start), pixel(end)), fill=_COLORS[color_index], width=thickness)
    for color_index, (start, end) in enumerate(_EDGES):
        for name in (start, end):
            x, y = pixel(name)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=_COLORS[color_index])

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=False)
    image.close()
    return path
