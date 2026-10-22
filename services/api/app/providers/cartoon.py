from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps


def cartoonize_png(source: bytes) -> bytes:
    """Create a clean, locally processed comic-style sprite and keep its alpha."""
    with Image.open(BytesIO(source)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGBA")

    alpha = image.getchannel("A")
    rgb = image.convert("RGB")
    work_size = (max(1, image.width // 3), max(1, image.height // 3))
    rgb = rgb.resize(work_size, Image.Resampling.LANCZOS)
    rgb = ImageEnhance.Color(rgb).enhance(1.42)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.24)
    rgb = rgb.filter(ImageFilter.MedianFilter(size=5))

    color_blocks = rgb.quantize(colors=12, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
    edges = ImageOps.grayscale(rgb.filter(ImageFilter.FIND_EDGES))
    edges = edges.point(lambda value: 128 if value >= 18 else 255)
    edges = edges.filter(ImageFilter.GaussianBlur(radius=0.35))
    outlined = ImageChops.multiply(color_blocks, Image.merge("RGB", (edges, edges, edges)))
    outlined = outlined.resize(image.size, Image.Resampling.LANCZOS).convert("RGBA")
    outlined.putalpha(alpha)

    expanded_alpha = alpha.filter(ImageFilter.MaxFilter(size=11))
    sticker_edge = ImageChops.subtract(expanded_alpha, alpha)
    sticker = Image.new("RGBA", image.size, (250, 249, 242, 0))
    sticker.putalpha(sticker_edge)
    finished = Image.new("RGBA", image.size, (0, 0, 0, 0))
    finished.alpha_composite(sticker)
    finished.alpha_composite(outlined)

    output = BytesIO()
    finished.save(output, format="PNG", optimize=True)
    return output.getvalue()
