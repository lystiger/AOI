"""
Preprocessing helpers for AOI PCB images.

YOLOv8 performs its own preprocessing internally during training and normal
prediction calls. These functions exist for reproducible notebook exploration,
offline analysis, and smoke tests.
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Literal

import cv2
import numpy as np


def load_image(path: str | Path) -> np.ndarray:
    """Load an image from disk as a BGR uint8 array."""
    image_path = Path(path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"OpenCV could not decode image: {image_path}")
    return image


def resize_letterbox(
    image: np.ndarray,
    target: int = 640,
    pad_value: int = 114,
) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Resize without distortion and pad to a square canvas."""
    if target < 1:
        raise ValueError("target must be >= 1")
    height, width = image.shape[:2]
    if height < 1 or width < 1:
        raise ValueError("image must have positive height and width")

    scale = min(target / height, target / width)
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))

    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
    pad_w = (target - new_width) // 2
    pad_h = (target - new_height) // 2

    if image.ndim == 2:
        canvas = np.full((target, target), pad_value, dtype=np.uint8)
        canvas[pad_h : pad_h + new_height, pad_w : pad_w + new_width] = resized
    else:
        channels = image.shape[2]
        canvas = np.full((target, target, channels), pad_value, dtype=np.uint8)
        canvas[pad_h : pad_h + new_height, pad_w : pad_w + new_width] = resized

    return canvas, scale, (pad_w, pad_h)


def to_greyscale(image: np.ndarray) -> np.ndarray:
    """Convert a BGR image to single-channel greyscale."""
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def greyscale_to_rgb(grey: np.ndarray) -> np.ndarray:
    """Convert a single-channel greyscale image back to 3 channels."""
    return cv2.cvtColor(grey, cv2.COLOR_GRAY2BGR)


def normalise(image: np.ndarray) -> np.ndarray:
    """Map uint8 pixels from [0,255] to float32 [0,1]."""
    if image.dtype != np.uint8:
        raise TypeError(f"Expected uint8 input, got {image.dtype}")
    return image.astype(np.float32) / 255.0


def denormalise(image: np.ndarray) -> np.ndarray:
    """Map float image values in [0,1] back to uint8."""
    return (np.clip(image, 0.0, 1.0) * 255).astype(np.uint8)


def channel_stats(image: np.ndarray) -> dict[str, float]:
    """Compute per-channel mean and std for a normalised image."""
    if image.dtype != np.float32:
        raise TypeError("Pass a normalised float32 image")

    stats: dict[str, float] = {}
    channel_names = ("B", "G", "R") if image.ndim == 3 else ("L",)
    for index, name in enumerate(channel_names):
        channel = image[:, :, index] if image.ndim == 3 else image
        stats[f"{name}_mean"] = float(np.mean(channel))
        stats[f"{name}_std"] = float(np.std(channel))
    return stats


def augment_flip(image: np.ndarray, direction: Literal["h", "v", "both"] = "h") -> np.ndarray:
    """Flip an image horizontally, vertically, or both."""
    codes = {"h": 1, "v": 0, "both": -1}
    return cv2.flip(image, codes[direction])


def augment_rotate(image: np.ndarray, angle: float = 90.0) -> np.ndarray:
    """Rotate around the centre, keep content, and resize back to input size."""
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])
    new_width = int(height * sin + width * cos)
    new_height = int(height * cos + width * sin)
    matrix[0, 2] += (new_width / 2) - width / 2
    matrix[1, 2] += (new_height / 2) - height / 2

    rotated = cv2.warpAffine(
        image,
        matrix,
        (new_width, new_height),
        borderValue=(114, 114, 114),
    )
    return cv2.resize(rotated, (width, height), interpolation=cv2.INTER_LINEAR)


def augment_brightness(image: np.ndarray, factor: float = 1.2) -> np.ndarray:
    """Change brightness by scaling the V channel in HSV space."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2] * factor, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def random_augment(image: np.ndarray, seed: int | None = None) -> np.ndarray:
    """Apply a deterministic random augmentation sequence when ``seed`` is set."""
    rng = random.Random(seed)
    augmented = image.copy()
    if rng.random() > 0.5:
        augmented = augment_flip(augmented, rng.choice(["h", "v"]))
    if rng.random() > 0.5:
        augmented = augment_rotate(augmented, rng.choice([90.0, 180.0, 270.0]))
    if rng.random() > 0.3:
        augmented = augment_brightness(augmented, rng.uniform(0.7, 1.4))
    return augmented


def preprocess_for_display(path: str | Path, target: int = 640) -> dict[str, object]:
    """Return intermediate preprocessing stages for notebook inspection."""
    original = load_image(path)
    resized, scale, padding = resize_letterbox(original, target)
    greyscale = to_greyscale(resized)
    normalised = normalise(resized)
    return {
        "original": original,
        "resized": resized,
        "greyscale": greyscale,
        "normalised": normalised,
        "scale": scale,
        "padding": padding,
    }


def preprocess_for_inference(path: str | Path, target: int = 640) -> np.ndarray:
    """Prepare an RGB float32 image for custom inference loops."""
    image = load_image(path)
    resized, _, _ = resize_letterbox(image, target)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    return normalise(rgb)
