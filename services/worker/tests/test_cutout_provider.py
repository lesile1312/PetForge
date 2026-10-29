from importlib import import_module
import sys
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw


def _api():
    try:
        return import_module("petforge_worker.providers.cutout")
    except ModuleNotFoundError:
        pytest.fail("portrait cutout provider is not implemented")


def test_cutout_is_transparent_padded_and_maps_to_original_coordinates(tmp_path):
    api = _api()
    source = tmp_path / "source.png"
    image = Image.new("RGB", (100, 80), "white")
    ImageDraw.Draw(image).rectangle((35, 15, 64, 69), fill="black")
    image.save(source)
    person = api.PersonCandidate(
        bbox_xywh_norm=(0.35, 0.1875, 0.3, 0.6875),
        landmarks_norm={},
        confidence=0.9,
    )

    def mask_predictor(crop):
        mask = Image.new("L", crop.size, 0)
        ImageDraw.Draw(mask).rectangle((crop.width // 4, crop.height // 8, crop.width * 3 // 4, crop.height * 7 // 8), fill=255)
        return mask

    result = api.AlphaCutoutProvider(mask_predictor=mask_predictor, padding_ratio=0.2).cutout(
        source, person, tmp_path / "cutout"
    )

    cutout = Image.open(result.cutout_path).convert("RGBA")
    mask = Image.open(result.mask_path).convert("L")
    assert result.source_size == (100, 80)
    assert result.source_bounds_xyxy == (29, 4, 71, 80)
    assert result.source_to_cutout == ((1.0, 0.0, -29.0), (0.0, 1.0, -4.0), (0.0, 0.0, 1.0))
    assert cutout.size == (42, 76)
    assert mask.size == cutout.size
    assert cutout.getchannel("A").getextrema() == (0, 255)
    assert cutout.getchannel("A").tobytes() == mask.tobytes()


def test_cutout_preserves_source_and_rejects_opaque_or_wrong_sized_mask(tmp_path):
    api = _api()
    source = tmp_path / "source.png"
    Image.new("RGB", (20, 30), "#ffccaa").save(source)
    before = source.read_bytes()
    person = api.PersonCandidate((0.1, 0.1, 0.8, 0.8), {}, 0.5)
    result = api.AlphaCutoutProvider(mask_predictor=lambda image: Image.new("L", (1, 1), 255)).cutout(
        source, person, tmp_path / "bad"
    )

    assert result.error_code == "invalid_mask_dimensions"
    assert source.read_bytes() == before


def test_birefnet_uses_verified_local_weights_without_fetching(monkeypatch, tmp_path):
    api = _api()
    model = tmp_path / "BiRefNet-portrait-epoch_150.onnx"
    model.write_bytes(b"verified local model")
    calls = []

    def new_session(name, **kwargs):
        cache_model = tmp_path / "models" / name / f"{name}.onnx"
        calls.append((name, kwargs, cache_model.read_bytes() if cache_model.is_file() else None))
        return object()

    monkeypatch.setitem(sys.modules, "rembg", SimpleNamespace(new_session=new_session))
    predictor = api.RemBgBiRefNetPortrait(model)

    session = predictor._load()

    assert session is not None
    assert calls == [("birefnet-portrait", {"providers": ["CPUExecutionProvider"]}, b"verified local model")]
