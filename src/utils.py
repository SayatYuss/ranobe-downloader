import os
import re
import time
from urllib.parse import urlsplit, urlparse
from PIL import Image
from io import BytesIO
import requests

def sanitize_filename(name: str) -> str:
    """Создает безопасное имя файла"""
    return re.sub(r'[\\/*?:"<>|]', '', name).strip()

def convert_to_webp(image_bytes: bytes) -> bytes:
    """Конвертирует изображение в формат WEBP"""
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            img = img.convert("RGB")
            webp_io = BytesIO()
            img.save(webp_io, format='WEBP')
            return webp_io.getvalue()
    except Exception as e:
        raise RuntimeError(f"Ошибка конвертации изображения: {e}")

def get_slug(novel_url: str) -> str:
    """Извлекает slug ранобэ из URL """
    parsed = urlparse(novel_url)
    path = parsed.path.strip('/')

    # Разбиваем путь и берём последний сегмент
    parts = path.split('/')
    last_segment = parts[-1]

    # Удаляем ID, если есть, и оставляем только slug
    match = re.match(r'(?:\d+--)?(.+)', last_segment)
    if match:
        return match.group(1)
    else:
        raise ValueError("Не удалось извлечь slug из URL")
