from __future__ import annotations

from pathlib import Path

from PIL import Image

from petforge_worker.preflight import ImageLimits, preflight_image


def test_rejects_unsupported_file_type(tmp_path: Path) -> None:
    source = tmp_path / "portrait.bmp"
    source.write_bytes(b"not an image")

    result = preflight_image(source, tmp_path / "clean.bmp", ImageLimits())

    assert result.ready is False
    assert result.error_code == "unsupported_type"
    assert not (tmp_path / "clean.bmp").exists()


def test_rejects_file_over_upload_limit_before_decode(tmp_path: Path) -> None:
    source = tmp_path / "portrait.png"
    source.write_bytes(b"x" * 11)

    result = preflight_image(
        source,
        tmp_path / "clean.png",
        ImageLimits(max_bytes=10, max_dimension=100, max_pixels=10_000),
    )

    assert result.error_code == "file_too_large"


def test_rejects_corrupt_supported_image(tmp_path: Path) -> None:
    source = tmp_path / "portrait.png"
    source.write_bytes(b"broken png data")

    result = preflight_image(source, tmp_path / "clean.png", ImageLimits())

    assert result.error_code == "invalid_image"


def test_rejects_excessive_dimensions(tmp_path: Path) -> None:
    source = tmp_path / "wide.png"
    Image.new("RGBA", (20, 10), (10, 20, 30, 255)).save(source)

    result = preflight_image(
        source,
        tmp_path / "clean.png",
        ImageLimits(max_bytes=100_000, max_dimension=16, max_pixels=1_000),
    )

    assert result.error_code == "image_too_large"


def test_rejects_excessive_pixel_count(tmp_path: Path) -> None:
    source = tmp_path / "many-pixels.png"
    Image.new("RGB", (20, 20), (10, 20, 30)).save(source)

    result = preflight_image(
        source,
        tmp_path / "clean.png",
        ImageLimits(max_bytes=100_000, max_dimension=100, max_pixels=300),
    )

    assert result.error_code == "image_too_large"


def test_transposes_orientation_and_removes_exif(tmp_path: Path) -> None:
    source = tmp_path / "sideways.jpg"
    output = tmp_path / "safe.jpg"
    image = Image.new("RGB", (20, 10), (180, 120, 90))
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private location metadata"
    image.save(source, exif=exif)

    result = preflight_image(
        source,
        output,
        ImageLimits(max_bytes=100_000, max_dimension=100, max_pixels=10_000),
    )

    assert result.ready is True
    assert (result.width, result.height) == (10, 20)
    with Image.open(output) as sanitized:
        assert sanitized.size == (10, 20)
        assert 274 not in sanitized.getexif()
        assert 270 not in sanitized.getexif()
        assert sanitized.info.get("exif") in (None, b"")


def test_rejects_output_path_that_overwrites_source(tmp_path: Path) -> None:
    source = tmp_path / "portrait.png"
    Image.new("RGBA", (10, 10), (10, 20, 30, 255)).save(source)

    result = preflight_image(source, source, ImageLimits())

    assert result.error_code == "output_path_invalid"
