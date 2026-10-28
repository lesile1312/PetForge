import builtins
from dataclasses import FrozenInstanceError
from importlib import import_module

import pytest


def _device_api():
    try:
        return import_module("petforge_worker.device")
    except ModuleNotFoundError:
        pytest.fail("worker device probe is not implemented")


def _mock_host(monkeypatch, *, architecture="AMD64", total_gib=16, available_gib=8):
    api = _device_api()
    monkeypatch.setattr(api.platform, "system", lambda: "Windows")
    monkeypatch.setattr(api.platform, "machine", lambda: architecture)
    monkeypatch.setattr(
        api,
        "_memory_status",
        lambda: (total_gib * 1024**3, available_gib * 1024**3),
    )
    return api


def test_16_gib_windows_x64_supports_cpu_reference_without_gpu_scan(monkeypatch):
    api = _mock_host(monkeypatch)
    monkeypatch.setattr(
        api,
        "_query_nvidia_gpu",
        lambda: pytest.fail("GPU scan ran without explicit check_gpu=True"),
    )

    profile = api.probe_device()

    assert profile.cpu_reference_supported is True
    assert profile.total_ram_bytes == 16 * 1024**3
    assert profile.gpu_name is None
    assert profile.unsupported_reasons == ()


def test_explicit_gpu_check_reports_name_vram_and_driver(monkeypatch):
    api = _mock_host(monkeypatch)
    monkeypatch.setattr(
        api,
        "_query_nvidia_gpu",
        lambda: ("NVIDIA GeForce RTX 4060 Laptop GPU", 8188 * 1024**2, "581.29"),
    )

    profile = api.probe_device(check_gpu=True)

    assert profile.gpu_name == "NVIDIA GeForce RTX 4060 Laptop GPU"
    assert profile.gpu_memory_bytes == 8188 * 1024**2
    assert profile.gpu_driver_version == "581.29"


def test_non_x64_windows_reports_unsupported_architecture(monkeypatch):
    api = _mock_host(monkeypatch, architecture="ARM64")

    profile = api.probe_device()

    assert profile.cpu_reference_supported is False
    assert "unsupported_architecture:arm64" in profile.unsupported_reasons


def test_less_than_16_gib_reports_cpu_reference_limit(monkeypatch):
    api = _mock_host(monkeypatch, total_gib=15)

    profile = api.probe_device()

    assert profile.cpu_reference_supported is False
    assert "ram_below_16_gib_reference" in profile.unsupported_reasons


def test_device_profile_is_immutable_and_serializes_snake_case(monkeypatch):
    api = _mock_host(monkeypatch)
    profile = api.probe_device()

    with pytest.raises(FrozenInstanceError):
        profile.total_ram_bytes = 1

    assert "total_ram_bytes" in profile.to_dict()
    assert "totalRamBytes" not in profile.to_dict()
