from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageChops

from .base import LayerAsset, LayerSet, PortraitCandidate


_REQUIRED = ("torso", "left_arm", "right_arm", "left_leg", "right_leg", "face", "hair", "eyes")


def _point(landmarks: dict[str, tuple[float, ...]], name: str, size: tuple[int, int]):
    value = landmarks.get(name)
    if value is None or len(value) < 2:
        return None
    x, y = float(value[0]), float(value[1])
    confidence = float(value[2]) if len(value) > 2 else 0.0
    if not (0 <= x <= 1 and 0 <= y <= 1 and 0 <= confidence <= 1):
        return None
    return x * size[0], y * size[1], confidence


class GeometricLayerSegmenter:
    """Seed pose-part textures from landmarks, retaining confidence and gaps explicitly."""

    def segment(
        self,
        candidate: PortraitCandidate,
        landmarks_norm: dict[str, tuple[float, ...]],
        output_dir: Path,
    ) -> LayerSet:
        with Image.open(candidate.image_path) as image_file:
            image = image_file.convert("RGBA")
        size = image.size
        alpha = image.getchannel("A")
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        masks: dict[str, tuple[Image.Image, float, bool]] = {}

        def add_mask(layer_id: str, mask: Image.Image, confidence: float, inferred: bool = False) -> None:
            clipped = ImageChops.multiply(mask, alpha)
            mask.close()
            if clipped.getbbox() is None:
                clipped.close()
                return
            masks[layer_id] = (clipped, max(0.0, min(1.0, confidence)), inferred)

        shoulder_points = [_point(landmarks_norm, f"{side}_shoulder", size) for side in ("left", "right")]
        hip_points = [_point(landmarks_norm, f"{side}_hip", size) for side in ("left", "right")]
        if all(shoulder_points + hip_points):
            torso_mask = Image.new("L", size, 0)
            points = [item[:2] for item in (shoulder_points[0], shoulder_points[1], hip_points[1], hip_points[0])]
            ImageDraw.Draw(torso_mask).polygon(points, fill=255)
            add_mask("torso", torso_mask, min(item[2] for item in shoulder_points + hip_points))

        for side in ("left", "right"):
            for part, joints in (
                (f"{side}_arm", (f"{side}_shoulder", f"{side}_elbow", f"{side}_wrist")),
                (f"{side}_leg", (f"{side}_hip", f"{side}_knee", f"{side}_ankle")),
            ):
                points = [_point(landmarks_norm, name, size) for name in joints]
                if not all(points):
                    continue
                thickness = max(6, round(min(size) * (0.09 if part.endswith("arm") else 0.1)))
                mask = Image.new("L", size, 0)
                draw = ImageDraw.Draw(mask)
                draw.line([item[:2] for item in points], fill=255, width=thickness, joint="curve")
                radius = thickness / 2
                for point in points:
                    x, y = point[:2]
                    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
                add_mask(part, mask, min(item[2] for item in points))

        nose = _point(landmarks_norm, "nose", size)
        left_ear = _point(landmarks_norm, "left_ear", size)
        right_ear = _point(landmarks_norm, "right_ear", size)
        if nose:
            shoulders = [point for point in shoulder_points if point]
            if left_ear and right_ear:
                head_width = abs(right_ear[0] - left_ear[0]) * 1.65
                head_confidence = min(left_ear[2], right_ear[2], nose[2])
            elif len(shoulders) == 2:
                head_width = abs(shoulders[1][0] - shoulders[0][0]) * 0.6
                head_confidence = min(nose[2], shoulders[0][2], shoulders[1][2]) * 0.35
            else:
                head_width = max(8.0, size[0] * 0.25)
                head_confidence = nose[2] * 0.2
            head_width = max(8.0, head_width)
            head_height = head_width * 1.12
            nx, ny = nose[:2]
            face_box = (
                nx - head_width * 0.31,
                ny - head_height * 0.42,
                nx + head_width * 0.31,
                ny + head_height * 0.43,
            )
            face_mask = Image.new("L", size, 0)
            ImageDraw.Draw(face_mask).ellipse(face_box, fill=255)
            add_mask("face", face_mask, head_confidence, inferred=True)

            hair_outer = Image.new("L", size, 0)
            outer_box = (
                nx - head_width * 0.56,
                ny - head_height * 0.62,
                nx + head_width * 0.56,
                ny + head_height * 0.5,
            )
            ImageDraw.Draw(hair_outer).ellipse(outer_box, fill=255)
            face_for_hair = Image.new("L", size, 0)
            ImageDraw.Draw(face_for_hair).ellipse(face_box, fill=255)
            hair_mask = ImageChops.subtract(hair_outer, face_for_hair)
            face_for_hair.close()
            add_mask("hair", hair_mask, head_confidence * 0.75, inferred=True)

            eyes_mask = Image.new("L", size, 0)
            eyes = [_point(landmarks_norm, name, size) for name in ("left_eye", "right_eye")]
            eye_draw = ImageDraw.Draw(eyes_mask)
            if all(eyes):
                radius = max(2, round(head_width * 0.055))
                for eye in eyes:
                    ex, ey = eye[:2]
                    eye_draw.ellipse((ex - radius, ey - radius, ex + radius, ey + radius), fill=255)
                add_mask("eyes", eyes_mask, min(item[2] for item in eyes), inferred=False)
            else:
                eye_y = ny - head_height * 0.09
                eye_box = (
                    nx - head_width * 0.23,
                    eye_y - head_width * 0.045,
                    nx + head_width * 0.23,
                    eye_y + head_width * 0.045,
                )
                eye_draw.ellipse(eye_box, fill=255)
                add_mask("eyes", eyes_mask, head_confidence * 0.5, inferred=True)

        assets: dict[str, LayerAsset] = {}
        for layer_id, (mask, confidence, inferred) in masks.items():
            texture = image.copy()
            texture.putalpha(mask)
            path = output / f"{layer_id}.png"
            texture.save(path, format="PNG", optimize=False)
            texture.close()
            assets[layer_id] = LayerAsset(path=path, confidence=confidence, inferred=inferred)
            mask.close()
        image.close()
        alpha.close()
        missing = tuple(layer_id for layer_id in _REQUIRED if layer_id not in assets)
        return LayerSet(assets=assets, missing_layers=missing)
