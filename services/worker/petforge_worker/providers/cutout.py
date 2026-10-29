from __future__ import annotations

import hashlib
import math
import os
import shutil
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageChops

from .base import CutoutResult, PersonCandidate


MaskPredictor = Callable[[Image.Image], Image.Image]


def _sha256(path: Path) -> bytes:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").digest()


class AlphaCutoutProvider:
    """Crop a selected person with margin, then store an alpha cutout and mask."""

    def __init__(self, mask_predictor: MaskPredictor, padding_ratio: float = 0.16):
        if not math.isfinite(padding_ratio) or padding_ratio < 0 or padding_ratio > 0.5:
            raise ValueError("invalid_cutout_padding")
        self.mask_predictor = mask_predictor
        self.padding_ratio = padding_ratio

    def cutout(self, source_path: Path, selected_person: PersonCandidate, output_dir: Path) -> CutoutResult:
        try:
            with Image.open(source_path) as source_image:
                source = source_image.convert("RGB")
        except (OSError, ValueError):
            return CutoutResult(False, error_code="source_unreadable")

        source_width, source_height = source.size
        x, y, width, height = selected_person.bbox_xywh_norm
        if not all(math.isfinite(value) for value in (x, y, width, height)) or min(width, height) <= 0:
            source.close()
            return CutoutResult(False, error_code="invalid_person_bounds")
        left = math.floor(x * source_width)
        top = math.floor(y * source_height)
        right = math.ceil((x + width) * source_width)
        bottom = math.ceil((y + height) * source_height)
        pad_x = math.ceil((right - left) * self.padding_ratio)
        pad_y = math.ceil((bottom - top) * self.padding_ratio)
        left, top = max(0, left - pad_x), max(0, top - pad_y)
        right, bottom = min(source_width, right + pad_x), min(source_height, bottom + pad_y)
        if left >= right or top >= bottom:
            source.close()
            return CutoutResult(False, error_code="invalid_person_bounds")

        crop = source.crop((left, top, right, bottom))
        source.close()
        try:
            mask = self.mask_predictor(crop)
            if not isinstance(mask, Image.Image) or mask.size != crop.size:
                return CutoutResult(False, error_code="invalid_mask_dimensions")
            alpha = mask.convert("L")
            if alpha.getbbox() is None:
                alpha.close()
                return CutoutResult(False, error_code="empty_person_mask")
            cutout = crop.convert("RGBA")
            cutout.putalpha(alpha)
            output = Path(output_dir)
            output.mkdir(parents=True, exist_ok=True)
            cutout_path, mask_path = output / "cutout.png", output / "mask.png"
            cutout.save(cutout_path, format="PNG", optimize=False)
            alpha.save(mask_path, format="PNG", optimize=False)
            alpha_bounds = alpha.getbbox()
            return CutoutResult(
                ready=True,
                cutout_path=cutout_path,
                mask_path=mask_path,
                source_size=(source_width, source_height),
                source_bounds_xyxy=(left, top, right, bottom),
                source_to_cutout=(
                    (1.0, 0.0, float(-left)),
                    (0.0, 1.0, float(-top)),
                    (0.0, 0.0, 1.0),
                ),
                alpha_bounds_xyxy=alpha_bounds,
            )
        except (OSError, ValueError, RuntimeError):
            return CutoutResult(False, error_code="cutout_failed")
        finally:
            crop.close()
            try:
                mask.close()
            except (UnboundLocalError, AttributeError):
                pass
            try:
                cutout.close()
            except (UnboundLocalError, AttributeError):
                pass


class RemBgBiRefNetPortrait:
    """Explicitly load the local BiRefNet portrait session; never use rembg defaults."""

    def __init__(self, model_path: Path, providers: list[str] | None = None):
        if not Path(model_path).is_file():
            raise FileNotFoundError("birefnet_portrait_weights_missing")
        self.model_path = Path(model_path)
        self.providers = providers or ["CPUExecutionProvider"]
        self._session = None

    def _load(self):
        if self._session is not None:
            return self._session
        from rembg import new_session

        model_home = self.model_path.parent
        model_home.mkdir(parents=True, exist_ok=True)
        os.environ["U2NET_HOME"] = str(model_home)
        rembg_model = model_home / "models" / "birefnet-portrait" / "birefnet-portrait.onnx"
        rembg_model.parent.mkdir(parents=True, exist_ok=True)
        try:
            source_hash = _sha256(self.model_path)
            if rembg_model.is_file():
                if os.path.samefile(self.model_path, rembg_model):
                    return self._cache_session(new_session)
                if source_hash != _sha256(rembg_model):
                    backup = rembg_model.with_name(f"{rembg_model.name}.preserved-{rembg_model.stat().st_size}")
                    suffix = 1
                    while backup.exists():
                        backup = rembg_model.with_name(
                            f"{rembg_model.name}.preserved-{rembg_model.stat().st_size}-{suffix}"
                        )
                        suffix += 1
                    rembg_model.replace(backup)
            if not rembg_model.exists():
                try:
                    os.link(self.model_path, rembg_model)
                except OSError:
                    shutil.copy2(self.model_path, rembg_model)
            if _sha256(rembg_model) != source_hash:
                raise RuntimeError("birefnet_local_cache_hash_mismatch")
        except OSError as error:
            raise RuntimeError("birefnet_local_cache_prepare_failed") from error

        return self._cache_session(new_session)

    def _cache_session(self, new_session):
        self._session = new_session("birefnet-portrait", providers=self.providers)
        return self._session

    def __call__(self, image: Image.Image) -> Image.Image:
        from rembg import remove

        return remove(image, session=self._load(), only_mask=True)


def rembg_model_path(model_root: Path) -> Path:
    return Path(model_root) / "rembg" / "BiRefNet-portrait-epoch_150.onnx"
