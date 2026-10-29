from importlib import import_module

import pytest
from PIL import Image, ImageDraw


def _api():
    try:
        return import_module("petforge_worker.providers.layers")
    except ModuleNotFoundError:
        pytest.fail("semantic layer provider is not implemented")


def test_layer_extraction_returns_body_face_hair_eye_assets_and_confidence(tmp_path):
    api = _api()
    candidate_path = tmp_path / "candidate.png"
    image = Image.new("RGBA", (128, 192), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((38, 8, 90, 61), fill="#efc2ad")
    draw.rectangle((46, 50, 81, 123), fill="#8c6b53")
    draw.line((48, 61, 25, 106), fill="#8c6b53", width=12)
    draw.line((78, 61, 104, 105), fill="#8c6b53", width=12)
    draw.line((53, 119, 46, 183), fill="#8c6b53", width=14)
    draw.line((75, 119, 83, 183), fill="#8c6b53", width=14)
    image.save(candidate_path)
    candidate = api.PortraitCandidate(
        image_path=candidate_path,
        mask_path=candidate_path,
        inferred_regions=("lower_body",),
        provenance={"model_revision": "test"},
    )
    landmarks = {
        "nose": (0.5, 0.2, 0.9),
        "left_eye": (0.45, 0.18, 0.95),
        "right_eye": (0.55, 0.18, 0.95),
        "left_shoulder": (0.4, 0.34, 0.9),
        "right_shoulder": (0.6, 0.34, 0.9),
        "left_elbow": (0.2, 0.53, 0.9),
        "right_elbow": (0.8, 0.53, 0.9),
        "left_wrist": (0.13, 0.65, 0.9),
        "right_wrist": (0.87, 0.65, 0.9),
        "left_hip": (0.42, 0.62, 0.9),
        "right_hip": (0.58, 0.62, 0.9),
        "left_knee": (0.4, 0.8, 0.9),
        "right_knee": (0.6, 0.8, 0.9),
        "left_ankle": (0.35, 0.95, 0.9),
        "right_ankle": (0.65, 0.95, 0.9),
    }

    layers = api.GeometricLayerSegmenter().segment(candidate, landmarks, tmp_path / "layers")

    required = {"torso", "left_arm", "right_arm", "left_leg", "right_leg", "face", "hair", "eyes"}
    assert required <= set(layers.assets)
    for layer_id in required:
        asset = layers.assets[layer_id]
        assert asset.path.is_file()
        assert 0.0 <= asset.confidence <= 1.0
        assert Image.open(asset.path).mode == "RGBA"
    assert layers.assets["torso"].confidence >= 0.5
    assert layers.assets["eyes"].confidence == pytest.approx(0.95)
    assert layers.assets["eyes"].inferred is False


def test_layer_extraction_reports_missing_landmark_layers_without_inventing_confidence(tmp_path):
    api = _api()
    path = tmp_path / "candidate.png"
    Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(path)
    candidate = api.PortraitCandidate(path, path, (), {})

    layers = api.GeometricLayerSegmenter().segment(candidate, {}, tmp_path / "layers")

    assert layers.assets == {}
    assert layers.missing_layers
    assert set(layers.missing_layers) >= {"left_arm", "right_arm", "left_leg", "right_leg"}
