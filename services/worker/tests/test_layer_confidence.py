from pathlib import Path

from PIL import Image, ImageDraw

from petforge_worker.providers.base import PortraitCandidate
from petforge_worker.providers.layers import GeometricLayerSegmenter


def test_layer_confidence_preserves_low_confidence_and_missing_limbs(tmp_path: Path) -> None:
    image_path = tmp_path / "candidate.png"
    mask_path = tmp_path / "mask.png"
    image = Image.new("RGBA", (128, 192), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((44, 8, 84, 48), fill=(240, 180, 150, 255))
    draw.rectangle((40, 45, 88, 120), fill=(180, 110, 210, 255))
    draw.rectangle((48, 118, 62, 185), fill=(250, 230, 210, 255))
    draw.rectangle((67, 118, 82, 185), fill=(250, 230, 210, 255))
    image.save(image_path)
    image.getchannel("A").save(mask_path)
    candidate = PortraitCandidate(image_path, mask_path)
    landmarks = {
        "nose": (0.50, 0.14, 0.95),
        "left_shoulder": (0.36, 0.30, 0.45),
        "right_shoulder": (0.64, 0.30, 0.92),
        "left_hip": (0.41, 0.59, 0.95),
        "right_hip": (0.60, 0.59, 0.95),
        "left_elbow": (0.30, 0.42, 0.90),
        "left_wrist": (0.26, 0.53, 0.90),
        "right_elbow": (0.70, 0.42, 0.90),
        "right_wrist": (0.74, 0.53, 0.90),
        "left_knee": (0.43, 0.76, 0.90),
        "left_ankle": (0.43, 0.94, 0.90),
        "right_knee": (0.61, 0.76, 0.90),
        "right_ankle": (0.61, 0.94, 0.90),
    }

    layers = GeometricLayerSegmenter().segment(candidate, landmarks, tmp_path / "layers")

    assert layers.assets["torso"].confidence == 0.45
    assert layers.assets["torso"].inferred is False
    assert "face" in layers.assets and layers.assets["face"].inferred is True
    assert "hair" in layers.assets and layers.assets["hair"].confidence < 0.45
    assert "eyes" in layers.assets and layers.assets["eyes"].inferred is True
    assert layers.missing_layers == ()


def test_layer_segmenter_reports_absent_limb_layers(tmp_path: Path) -> None:
    image_path = tmp_path / "candidate.png"
    mask_path = tmp_path / "mask.png"
    Image.new("RGBA", (64, 96), (0, 0, 0, 0)).save(image_path)
    Image.new("L", (64, 96), 0).save(mask_path)
    layers = GeometricLayerSegmenter().segment(
        PortraitCandidate(image_path, mask_path), {"nose": (0.5, 0.2, 0.9)}, tmp_path / "layers"
    )
    assert layers.missing_layers == ("torso", "left_arm", "right_arm", "left_leg", "right_leg", "face", "hair", "eyes")
