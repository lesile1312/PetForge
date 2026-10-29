from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Protocol

from ..device import DeviceProfile


class ProviderError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class PersonSelectionError(ProviderError):
    pass


class GenerationCancelled(ProviderError):
    def __init__(self):
        super().__init__("generation_cancelled")


@dataclass(frozen=True, slots=True)
class PersonCandidate:
    bbox_xywh_norm: tuple[float, float, float, float]
    landmarks_norm: dict[str, tuple[float, ...]]
    confidence: float


@dataclass(frozen=True, slots=True)
class CutoutResult:
    ready: bool
    cutout_path: Path | None = None
    mask_path: Path | None = None
    source_size: tuple[int, int] | None = None
    source_bounds_xyxy: tuple[int, int, int, int] | None = None
    source_to_cutout: tuple[tuple[float, float, float], ...] | None = None
    alpha_bounds_xyxy: tuple[int, int, int, int] | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class PortraitCandidate:
    image_path: Path
    mask_path: Path
    inferred_regions: tuple[str, ...] = ()
    provenance: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LayerAsset:
    path: Path
    confidence: float
    inferred: bool = False


@dataclass(frozen=True, slots=True)
class LayerSet:
    assets: dict[str, LayerAsset]
    missing_layers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PortraitRequest:
    source_path: Path
    selected_crop_xywh_norm: tuple[float, float, float, float]
    style_preset: str
    clothing_description: str | None
    inferred_regions: tuple[str, ...]
    seed: int = 0
    pose_description: str | None = None
    pose_control_image: Path | None = None


class CancelToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self.cancelled:
            raise GenerationCancelled()


class CutoutProvider(Protocol):
    def cutout(self, source_path: Path, selected_person: PersonCandidate, output_dir: Path) -> CutoutResult: ...


class PersonDetector(Protocol):
    def detect(self, source_path: Path) -> list[PersonCandidate]: ...


class LayerSegmenter(Protocol):
    def segment(
        self,
        candidate: PortraitCandidate,
        landmarks_norm: dict[str, tuple[float, ...]],
        output_dir: Path,
    ) -> LayerSet: ...


class PortraitGenerator(Protocol):
    model_id: str

    def generate(
        self,
        request: PortraitRequest,
        device: DeviceProfile,
        output_dir: Path,
        cancel: CancelToken | None = None,
    ) -> PortraitCandidate: ...


def resolve_person_selection(
    candidates: list[PersonCandidate],
    *,
    index: int | None = None,
    crop_xywh_px: tuple[int, int, int, int] | None = None,
    image_size: tuple[int, int],
) -> PersonCandidate:
    if index is not None:
        if index < 0 or index >= len(candidates):
            raise PersonSelectionError("invalid_person_index")
        return candidates[index]
    if len(candidates) == 1 and crop_xywh_px is None:
        return candidates[0]
    if len(candidates) > 1 and crop_xywh_px is None:
        raise PersonSelectionError("person_selection_required")
    if crop_xywh_px is None:
        raise PersonSelectionError("person_not_detected")

    width, height = image_size
    x, y, crop_width, crop_height = crop_xywh_px
    if (
        width <= 0
        or height <= 0
        or any(not isinstance(value, int) or isinstance(value, bool) for value in crop_xywh_px)
        or x < 0
        or y < 0
        or crop_width <= 0
        or crop_height <= 0
        or x + crop_width > width
        or y + crop_height > height
    ):
        raise PersonSelectionError("invalid_manual_crop")
    return PersonCandidate(
        bbox_xywh_norm=(x / width, y / height, crop_width / width, crop_height / height),
        landmarks_norm={},
        confidence=0.0,
    )
