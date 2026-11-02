"""Optional EPUB image optimization; never changes downloaded originals."""
from __future__ import annotations

from io import BytesIO


def optimize_image(data: bytes, media_type: str, *, quality: int = 85,
                   max_width: int = 1600) -> tuple[bytes, str, str]:
    """Return (data, MIME, extension), preserving the original if not smaller.

    GIF and images with meaningful transparency are kept unchanged. Opaque PNG
    images are converted to JPEG; JPEG and static WebP are recompressed in place.
    """
    if not 1 <= quality <= 100 or max_width < 1:
        raise ValueError("Invalid image optimization settings")
    extensions = {"image/jpeg": "jpg", "image/png": "png",
                  "image/gif": "gif", "image/webp": "webp"}
    if media_type not in extensions:
        raise ValueError(f"Unsupported image type: {media_type}")
    if media_type == "image/gif":
        return data, media_type, "gif"

    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError(
            "Optimized images require Pillow: pip install 'ranobe-downloader[images]'"
        ) from exc

    with Image.open(BytesIO(data)) as source:
        if getattr(source, "n_frames", 1) > 1:
            return data, media_type, extensions[media_type]

        if media_type == "image/png":
            if source.format != "PNG":
                raise ValueError("Expected PNG image")
            if source.mode in ("RGBA", "LA") or "transparency" in source.info:
                rgba = source.convert("RGBA")
                if rgba.getchannel("A").getextrema()[0] < 250:
                    return data, media_type, "png"
                background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                image = Image.alpha_composite(background, rgba).convert("RGB")
            else:
                image = source.convert("RGB")
            output_format = "JPEG"
            output_mime, output_ext = "image/jpeg", "jpg"
        elif media_type == "image/jpeg":
            if source.format != "JPEG":
                raise ValueError("Expected JPEG image")
            image = source.convert("RGB")
            output_format = "JPEG"
            output_mime, output_ext = "image/jpeg", "jpg"
        else:
            if source.format != "WEBP":
                raise ValueError("Expected WebP image")
            if "A" in source.getbands():
                alpha = source.convert("RGBA").getchannel("A")
                if alpha.getextrema()[0] < 255:
                    return data, media_type, "webp"
            image = source.convert("RGB")
            output_format = "WEBP"
            output_mime, output_ext = "image/webp", "webp"

        if image.width > max_width:
            from PIL import Image as PILImage
            height = max(1, round(image.height * max_width / image.width))
            image = image.resize((max_width, height), PILImage.Resampling.LANCZOS)

        output = BytesIO()
        if output_format == "JPEG":
            image.save(output, format=output_format, quality=quality, optimize=True, progressive=True)
        else:
            image.save(output, format=output_format, quality=quality, method=6)
        optimized = output.getvalue()
        if len(optimized) < len(data):
            return optimized, output_mime, output_ext
        return data, media_type, extensions[media_type]
