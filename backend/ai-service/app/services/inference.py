"""
app/services/inference.py
─────────────────────────────────────────────────────────────────────────────
Shared inference utilities (image loading, validation, preprocessing).

These helper functions are used by multiple tools to avoid code duplication.
The tools themselves don't need to know how to open images or validate paths.
"""

import os
from pathlib import Path
from typing import Optional
from loguru import logger


def validate_image_path(image_path: Optional[str]) -> tuple[bool, str]:
    """
    Check whether an image path exists and is readable.

    Args:
        image_path: Path string from user input (can be None)

    Returns:
        (is_valid, error_message) — error_message is empty string if valid
    """
    if image_path is None:
        return True, ""  # None is allowed (user may not provide an image)

    path = Path(image_path)

    if not path.exists():
        return False, f"Image file not found: {image_path}"

    if not path.is_file():
        return False, f"Path is not a file: {image_path}"

    supported_extensions = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
    if path.suffix.lower() not in supported_extensions:
        return False, (
            f"Unsupported image format '{path.suffix}'. "
            f"Supported: {supported_extensions}"
        )

    return True, ""


def load_image_for_display(image_path: Optional[str]):
    """
    Load an image using Pillow for display or preprocessing.
    Returns None if image_path is None or loading fails.

    In mock mode this is not called (models don't need real images).
    In real mode, models call this to get a PIL.Image object.
    """
    if image_path is None:
        return None

    try:
        from PIL import Image
        img = Image.open(image_path).convert("RGB")
        logger.debug(f"Loaded image: {image_path} | size={img.size}")
        return img
    except Exception as e:
        logger.error(f"Failed to load image '{image_path}': {e}")
        return None


def get_device() -> str:
    """
    Detect the best available device for PyTorch inference.

    Returns:
        "cuda" if an NVIDIA GPU is available, otherwise "cpu"

    Note: torch is NOT imported at module level because it's a heavy
    dependency that shouldn't crash the service if not installed.
    Real inference mode will call this at model load time.
    """
    try:
        # pyrefly: ignore [missing-import]
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info(f"GPU detected: {gpu_name} ({vram_gb:.1f} GB VRAM)")
        else:
            logger.warning("No GPU detected — inference will run on CPU (slow).")
        return device
    except ImportError:
        logger.warning("PyTorch not installed — returning 'cpu'")
        return "cpu"
