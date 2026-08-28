"""Image URL, path, and base64 conversion helpers."""

from __future__ import annotations

import base64
import io
import os
import re

import requests
from PIL import Image


def image_path_to_base64(
    image_path: str,
    max_width: int = 256,
    max_height: int = 256,
    quality: int = 85,
    max_b64_length: int = 65535,
) -> str | None:
    shared_root = os.environ.get("SHARED_ROOT", "/app/platform")
    shared_root = os.environ.get("SHARED_CONFIG_ROOT", shared_root)
    with open(os.path.join(shared_root, image_path.lstrip("/")), "rb") as image_file:
        img = Image.open(image_file).convert("RGB")
        img.thumbnail((max_width, max_height))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
        base64_string = f"data:image/jpeg;base64,{base64_image}"
        if len(base64_string) > max_b64_length:
            return None
        return base64_string


def image_url_to_base64(
    image_url: str,
    max_width: int = 256,
    max_height: int = 256,
    quality: int = 85,
    max_b64_length: int = 65535,
) -> str | None:
    try:
        response = requests.get(image_url, timeout=120)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        img = Image.open(io.BytesIO(response.content)).convert("RGB")
        img.thumbnail((max_width, max_height))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
        base64_string = f"data:{content_type};base64,{base64_image}"
        if len(base64_string) > max_b64_length:
            return None
        return base64_string
    except Exception:
        return None


def image_to_base64(image: Image.Image) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    image_bytes = buffered.getvalue()
    image_b64 = base64.b64encode(image_bytes).decode()
    return f"data:image/jpeg;base64,{image_b64}"


def is_url(string: str) -> bool:
    return bool(re.match(r"^https?://", string))


def is_path(string: str) -> bool:
    return bool(re.match(r"^/", string))


def resize_base64_image(
    base64_string: str,
    max_width: int = 256,
    max_height: int = 256,
    quality: int = 85,
    max_b64_length: int = 65535,
) -> str | None:
    try:
        if base64_string.startswith("data:"):
            header, base64_data = base64_string.split(",", 1)
        else:
            base64_data = base64_string
            header = "data:image/jpeg;base64"

        image_data = base64.b64decode(base64_data)
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        img.thumbnail((max_width, max_height))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        resized_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        result = f"{header},{resized_base64}"
        return result if len(result) <= max_b64_length else None
    except Exception:
        return None
