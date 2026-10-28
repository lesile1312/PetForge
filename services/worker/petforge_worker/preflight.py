from __future__ import annotations

import os
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


_FORMATS_BY_SUFFIX = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}


@dataclass(frozen=True, slots=True)
class ImageLimits:
    max_bytes: int = 10 * 1024 * 1024
    max_dimension: int = 8192
    max_pixels: int = 80_000_000

    def __post_init__(self) -> None:
        if min(self.max_bytes, self.max_dimension, self.max_pixels) <= 0:
            raise ValueError("image_limits_must_be_positive")


@dataclass(frozen=True, slots=True)
class PreflightResult:
    ready: bool
    width: int | None = None
    height: int | None = None
    image_format: str | None = None
    sanitized_path: Path | None = None
    error_code: str | None = None


def _rejected(code: str) -> PreflightResult:
    return PreflightResult(ready=False, error_code=code)


def preflight_image(
    source_path: Path,
    output_path: Path,
    limits: ImageLimits,
) -> PreflightResult:
    """Validate and re-encode a photo with orientation applied and metadata removed."""
    source = Path(source_path)
    output = Path(output_path)
    try:
        source_resolved = source.resolve(strict=True)
    except OSError:
        return _rejected("source_unreadable")
    if not source_resolved.is_file():
        return _rejected("source_unreadable")

    source_format = _FORMATS_BY_SUFFIX.get(source.suffix.lower())
    output_format = _FORMATS_BY_SUFFIX.get(output.suffix.lower())
    if source_format is None or output_format != source_format:
        return _rejected("unsupported_type")
    try:
        if source_resolved == output.resolve():
            return _rejected("output_path_invalid")
        size_bytes = source_resolved.stat().st_size
    except OSError:
        return _rejected("source_unreadable")
    if size_bytes > limits.max_bytes:
        return _rejected("file_too_large")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source_resolved) as image:
                if image.format != source_format:
                    return _rejected("unsupported_type")
                width, height = image.size
                if (
                    width <= 0
                    or height <= 0
                    or width > limits.max_dimension
                    or height > limits.max_dimension
                    or width * height > limits.max_pixels
                ):
                    return _rejected("image_too_large")
                image.load()
                oriented = ImageOps.exif_transpose(image)
                final_width, final_height = oriented.size
                mode = "RGB" if source_format == "JPEG" else ("RGBA" if "A" in oriented.getbands() else "RGB")
                sanitized = oriented.convert(mode)
                sanitized.info.clear()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        return _rejected("image_too_large")
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        return _rejected("invalid_image")

    temporary_path: Path | None = None
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.stem}.preflight.",
            suffix=output.suffix,
            dir=output.parent,
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        sanitized.save(temporary_path, format=source_format, exif=b"")
        os.replace(temporary_path, output)
    except (OSError, ValueError):
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        return _rejected("output_write_failed")
    finally:
        sanitized.close()

    return PreflightResult(
        ready=True,
        width=final_width,
        height=final_height,
        image_format=source_format,
        sanitized_path=output,
    )
