from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from io import BytesIO
import os
from threading import Lock

import numpy as np
from PIL import Image, ImageFilter, ImageOps


class BackgroundRemovalProvider(ABC):
    name = "abstract"

    @abstractmethod
    def remove_background(self, image_bytes: bytes) -> tuple[bytes, int, int]: ...


class ProviderUnavailableError(RuntimeError):
    """A selected local AI provider is not installed or configured."""


class RembgBackgroundRemovalProvider(BackgroundRemovalProvider):
    """Local ONNX foreground segmentation using rembg; no image leaves this machine."""

    name = "rembg:birefnet-portrait"

    def __init__(self, model_name: str = "birefnet-portrait") -> None:
        self.model_name = model_name
        self._session = None
        self._lock = Lock()

    def _get_session(self):
        if self._session is not None:
            return self._session
        with self._lock:
            if self._session is not None:
                return self._session
            os.environ.setdefault("OMP_NUM_THREADS", "4")
            try:
                from rembg import new_session
            except ImportError as error:
                raise ProviderUnavailableError(
                    "本地 AI 抠图依赖尚未安装。请在项目目录运行 scripts/setup-ai.ps1。"
                ) from error
            try:
                self._session = new_session(self.model_name)
            except Exception as error:
                raise ProviderUnavailableError(
                    f"无法加载本地抠图模型 {self.model_name}。请检查网络后重试首次模型下载。"
                ) from error
        return self._session

    def remove_background(self, image_bytes: bytes) -> tuple[bytes, int, int]:
        from PIL import ImageOps

        with Image.open(BytesIO(image_bytes)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGBA")
            normalized = BytesIO()
            image.save(normalized, format="PNG")

        try:
            from rembg import remove
        except ImportError as error:
            raise ProviderUnavailableError(
                "本地 AI 抠图依赖尚未安装。请在项目目录运行 scripts/setup-ai.ps1。"
            ) from error
        result = remove(normalized.getvalue(), session=self._get_session())
        if isinstance(result, Image.Image):
            cutout = result.convert("RGBA")
        else:
            with Image.open(BytesIO(result)) as opened:
                cutout = opened.convert("RGBA")

        alpha = cutout.getchannel("A")
        bounds = alpha.point(lambda value: 255 if value > 8 else 0).getbbox()
        if bounds is None:
            raise ValueError("没有识别到清晰的人物主体，请换一张人物更明显的图片。")

        left, top, right, bottom = bounds
        padding_x = max(4, round((right - left) * 0.06))
        padding_y = max(4, round((bottom - top) * 0.06))
        crop = (
            max(0, left - padding_x),
            max(0, top - padding_y),
            min(cutout.width, right + padding_x),
            min(cutout.height, bottom + padding_y),
        )
        cutout = cutout.crop(crop)
        output = BytesIO()
        cutout.save(output, format="PNG", optimize=True)
        return output.getvalue(), cutout.width, cutout.height


class EdgeMatteProvider(BackgroundRemovalProvider):
    """Remove a connected near-uniform border color; not a semantic segmentation model."""

    name = "edge-matte"
    MAX_ANALYSIS_SIDE = 960
    COLOR_DISTANCE = 48.0
    FEATHER_RADIUS = 1.2
    PADDING_RATIO = 0.06

    def remove_background(self, image_bytes: bytes) -> tuple[bytes, int, int]:
        with Image.open(BytesIO(image_bytes)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGBA")

        original_alpha = np.asarray(image.getchannel("A"))
        if np.min(original_alpha) < 255:
            alpha = Image.fromarray(original_alpha, mode="L")
        else:
            width, height = image.size
            ratio = min(1.0, self.MAX_ANALYSIS_SIDE / max(width, height))
            analysis_size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
            sample = image.convert("RGB").resize(analysis_size, Image.Resampling.BILINEAR)
            pixels = np.asarray(sample, dtype=np.int16)
            border = np.concatenate((pixels[0], pixels[-1], pixels[:, 0], pixels[:, -1]), axis=0)
            background = np.median(border, axis=0)
            distance = np.sqrt(np.sum((pixels - background) ** 2, axis=2))
            candidate = distance <= self.COLOR_DISTANCE
            height_small, width_small = candidate.shape
            visited = np.zeros(candidate.shape, dtype=bool)
            queue: deque[tuple[int, int]] = deque()
            for x in range(width_small):
                if candidate[0, x]:
                    visited[0, x] = True
                    queue.append((0, x))
                if candidate[height_small - 1, x] and not visited[height_small - 1, x]:
                    visited[height_small - 1, x] = True
                    queue.append((height_small - 1, x))
            for y in range(height_small):
                if candidate[y, 0] and not visited[y, 0]:
                    visited[y, 0] = True
                    queue.append((y, 0))
                if candidate[y, width_small - 1] and not visited[y, width_small - 1]:
                    visited[y, width_small - 1] = True
                    queue.append((y, width_small - 1))
            while queue:
                y, x = queue.popleft()
                for next_y, next_x in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if (
                        0 <= next_y < height_small
                        and 0 <= next_x < width_small
                        and candidate[next_y, next_x]
                        and not visited[next_y, next_x]
                    ):
                        visited[next_y, next_x] = True
                        queue.append((next_y, next_x))

            mask = Image.fromarray(np.where(visited, 0, 255).astype(np.uint8), mode="L")
            if analysis_size != (width, height):
                mask = mask.resize((width, height), Image.Resampling.BILINEAR)
            alpha = mask.filter(ImageFilter.GaussianBlur(self.FEATHER_RADIUS))

        image.putalpha(alpha)
        bbox = alpha.point(lambda value: 255 if value > 10 else 0).getbbox()
        if bbox is None:
            raise ValueError("No visible subject was found. Try a clear subject against a simple background.")
        left, top, right, bottom = bbox
        subject_width, subject_height = right - left, bottom - top
        pad_x = max(2, round(subject_width * self.PADDING_RATIO))
        pad_y = max(2, round(subject_height * self.PADDING_RATIO))
        crop_box = (
            max(0, left - pad_x),
            max(0, top - pad_y),
            min(image.width, right + pad_x),
            min(image.height, bottom + pad_y),
        )
        result = image.crop(crop_box)
        output = BytesIO()
        result.save(output, format="PNG", optimize=True)
        return output.getvalue(), result.width, result.height


class MockBackgroundRemovalProvider(BackgroundRemovalProvider):
    """Explicit no-op adapter for deployments without an image library or provider."""

    name = "mock"

    def remove_background(self, image_bytes: bytes) -> tuple[bytes, int, int]:
        with Image.open(BytesIO(image_bytes)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGBA")
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue(), image.width, image.height
