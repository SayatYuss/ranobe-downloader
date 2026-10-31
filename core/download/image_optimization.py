"""Optional EPUB image optimization; never changes downloaded originals."""
from __future__ import annotations

from io import BytesIO


def optimize_image(data: bytes, media_type: str, *, quality: int = 85,
                   max_width: int = 1600) -> tuple[bytes, str, str]:
    """Return (data, MIME, extension). Preserve source if conversion isn't smaller."""
    if not 1 <= quality <= 100 or max_width < 1:
        raise ValueError("Invalid image optimization settings")
    if media_type != "image/png":
        return data, media_type, {"image/jpeg": "jpg", "image/webp": "webp",
                                  "image/gif": "gif", "image/png": "png"}[media_type]
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError(
            "Optimized images require Pillow: pip install 'ranobe-downloader[images]'"
        ) from exc

    with Image.open(BytesIO(data)) as source:
        if source.format != "PNG":
            raise ValueError("Expected PNG image")
        if source.mode in ("RGBA", "LA") or "transparency" in source.info:
            rgba = source.convert("RGBA")
            # Preserve meaningful transparency; tiny alpha variations can be flattened.
            if rgba.getchannel("A").getextrema()[0] < 250:
                return data, media_type, "png"
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            rgb = Image.alpha_composite(background, rgba).convert("RGB")
        else:
            rgb = source.convert("RGB")
        if rgb.width > max_width:
            from PIL import Image as PILImage
            height = max(1, round(rgb.height * max_width / rgb.width))
            rgb = rgb.resize((max_width, height), PILImage.Resampling.LANCZOS)
        output = BytesIO()
        rgb.save(output, format="JPEG", quality=quality, optimize=True)
        optimized = output.getvalue()
        if len(optimized) < len(data):
            return optimized, "image/jpeg", "jpg"
        return data, "image/png", "png"
