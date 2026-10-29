import builtins
import builtins
from importlib import import_module
from pathlib import Path

import pytest
from PIL import Image


def _api():
    try:
        return import_module("petforge_worker.providers.portrait")
    except ModuleNotFoundError:
        pytest.fail("portrait generator is not implemented")


def test_fake_generator_writes_candidate_and_explicit_inference_provenance(tmp_path):
    api = _api()
    source = tmp_path / "reference.png"
    Image.new("RGBA", (80, 120), (255, 0, 0, 255)).save(source)
    request = api.PortraitRequest(
        source_path=source,
        selected_crop_xywh_norm=(0.0, 0.0, 1.0, 1.0),
        style_preset="warm_chibi",
        clothing_description=None,
        inferred_regions=("lower_body", "shoes"),
    )
    device = api.DeviceProfile("Windows", "x86_64", 24, 12, None, None, None, True, ())

    candidate = api.DeterministicFakePortraitGenerator().generate(request, device, tmp_path / "out")

    assert candidate.image_path.is_file()
    assert candidate.mask_path.is_file()
    assert Image.open(candidate.image_path).mode == "RGBA"
    assert candidate.inferred_regions == ("lower_body", "shoes")
    assert candidate.provenance["generator_kind"] == "deterministic_fake"
    assert candidate.provenance["source_reference_sha256"]
    assert "source_path" not in candidate.provenance


def test_fake_generator_is_deterministic_for_same_seed_and_input(tmp_path):
    api = _api()
    source = tmp_path / "reference.png"
    Image.new("RGB", (20, 30), "#dd9988").save(source)
    request = api.PortraitRequest(source, (0.0, 0.0, 1.0, 1.0), "warm_chibi", None, ())
    device = api.DeviceProfile("Windows", "x86_64", 24, 12, None, None, None, True, ())
    generator = api.DeterministicFakePortraitGenerator(seed=77)

    first = generator.generate(request, device, tmp_path / "one")
    second = generator.generate(request, device, tmp_path / "two")

    assert Image.open(first.image_path).tobytes() == Image.open(second.image_path).tobytes()


def test_warm_chibi_prompt_demands_cartoon_style_and_complete_standing_pose():
    api = _api()
    request = api.PortraitRequest(
        source_path=Path("photo.png"),
        selected_crop_xywh_norm=(0.0, 0.0, 1.0, 1.0),
        style_preset="warm_chibi",
        clothing_description=None,
        inferred_regions=(),
        pose_description="front-facing neutral idle stand, both feet flat on the ground",
    )

    prompt, prompt_2, negative, negative_2 = api._build_portrait_prompts(request)

    assert "2D hand-drawn kawaii chibi" in prompt
    assert "both feet flat on the ground" in prompt_2
    assert "photorealistic" in negative
    assert "cropped" in negative_2
    assert "raised leg" in negative_2

    action_request = api.PortraitRequest(
        source_path=Path("photo.png"),
        selected_crop_xywh_norm=(0.0, 0.0, 1.0, 1.0),
        style_preset="warm_chibi",
        clothing_description=None,
        inferred_regions=(),
        pose_description="comfortable low squat, looking down at a smartphone",
    )
    _, action_prompt, _, action_negative = api._build_portrait_prompts(action_request)
    assert "comfortable low squat" in action_prompt
    assert "kneeling" not in action_negative


def test_local_generator_checks_all_model_files_before_importing_runtime(tmp_path, monkeypatch):
    api = _api()
    model_root = tmp_path / "models"
    for relative in (
        "sdxl/sd_xl_base_1.0.safetensors",
        "sdxl-config/model_index.json",
        "ip-adapter/models/image_encoder/config.json",
        "ip-adapter/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors",
    ):
        path = model_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    device = api.DeviceProfile("Windows", "x86_64", 16, 8, None, None, None, True, ())
    generator = api.LocalSDXLPortraitGenerator(model_root, lambda image: image, device_mode="cpu")
    original_import = builtins.__import__

    def reject_runtime_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in {"torch", "diffusers", "transformers"}:
            raise AssertionError("heavy model runtime loaded before file preflight")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_runtime_import)
    with pytest.raises(api.ProviderError, match="portrait_model_files_missing"):
        generator._load(device)
    assert not (model_root / "ip-adapter/models/image_encoder/model.safetensors").exists()


def test_local_generator_checks_all_model_files_before_importing_runtime(tmp_path, monkeypatch):
    api = _api()
    model_root = tmp_path / "models"
    for relative in (
        "sdxl/sd_xl_base_1.0.safetensors",
        "sdxl-config/model_index.json",
        "ip-adapter/models/image_encoder/config.json",
        "ip-adapter/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors",
    ):
        path = model_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    device = api.DeviceProfile("Windows", "x86_64", 16, 8, None, None, None, True, ())
    generator = api.LocalSDXLPortraitGenerator(model_root, lambda image: image, device_mode="cpu")
    original_import = builtins.__import__

    def reject_runtime_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in {"torch", "diffusers", "transformers"}:
            raise AssertionError("heavy model runtime loaded before file preflight")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_runtime_import)
    with pytest.raises(api.ProviderError, match="portrait_model_files_missing"):
        generator._load(device)
    assert not (model_root / "ip-adapter/models/image_encoder/model.safetensors").exists()
