"""Self-contained smoke tests for the AOI ML pipeline."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _make_dummy_pcb_image(height: int = 480, width: int = 640) -> np.ndarray:
    image = np.full((height, width, 3), 30, dtype=np.uint8)
    image[:, :] = (30, 80, 30)
    for row in range(5):
        for col in range(8):
            x, y = 60 + col * 75, 60 + row * 80
            cv2.rectangle(image, (x, y), (x + 20, y + 12), (200, 200, 200), -1)
    for cx, cy in [(30, 30), (width - 30, 30), (30, height - 30)]:
        cv2.circle(image, (cx, cy), 10, (30, 165, 210), -1)
    return image


def test_load_image() -> None:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
    cv2.imwrite(str(tmp_path), _make_dummy_pcb_image())

    from ml.pipeline.preprocess import load_image

    image = load_image(tmp_path)
    assert image.shape == (480, 640, 3)
    assert image.dtype == np.uint8
    tmp_path.unlink()
    print("  PASS  load_image")


def test_load_image_missing() -> None:
    from ml.pipeline.preprocess import load_image

    try:
        load_image("/nonexistent/path/image.png")
        raise AssertionError("Expected FileNotFoundError")
    except FileNotFoundError:
        pass
    print("  PASS  load_image (missing file)")


def test_resize_letterbox() -> None:
    from ml.pipeline.preprocess import resize_letterbox

    image = _make_dummy_pcb_image(480, 640)
    resized, scale, (pad_w, pad_h) = resize_letterbox(image, target=640)
    assert resized.shape == (640, 640, 3)
    assert resized.dtype == np.uint8
    assert 0.0 < scale <= 1.0
    assert pad_w >= 0 and pad_h >= 0
    print("  PASS  resize_letterbox")


def test_resize_square_input() -> None:
    from ml.pipeline.preprocess import resize_letterbox

    image = _make_dummy_pcb_image(640, 640)
    resized, scale, _ = resize_letterbox(image, 640)
    assert resized.shape == (640, 640, 3)
    assert scale == 1.0
    print("  PASS  resize_letterbox (square input)")


def test_greyscale() -> None:
    from ml.pipeline.preprocess import to_greyscale

    image = _make_dummy_pcb_image()
    grey = to_greyscale(image)
    assert grey.ndim == 2
    assert grey.dtype == np.uint8
    assert to_greyscale(grey).shape == grey.shape
    print("  PASS  to_greyscale")


def test_normalise() -> None:
    from ml.pipeline.preprocess import channel_stats, denormalise, normalise

    image = _make_dummy_pcb_image()
    normalised = normalise(image)
    assert normalised.dtype == np.float32
    assert normalised.min() >= 0.0 and normalised.max() <= 1.0

    round_trip = denormalise(normalised)
    assert round_trip.dtype == np.uint8
    assert np.max(np.abs(round_trip.astype(int) - image.astype(int))) <= 1

    stats = channel_stats(normalised)
    for key in ("B_mean", "G_mean", "R_mean", "B_std", "G_std", "R_std"):
        assert key in stats
        assert 0.0 <= stats[key] <= 1.0
    print("  PASS  normalise / denormalise / channel_stats")


def test_normalise_wrong_dtype() -> None:
    from ml.pipeline.preprocess import normalise

    bad = np.zeros((10, 10, 3), dtype=np.float32)
    try:
        normalise(bad)
        raise AssertionError("Expected TypeError")
    except TypeError:
        pass
    print("  PASS  normalise (wrong dtype guard)")


def test_augmentations() -> None:
    from ml.pipeline.preprocess import augment_brightness, augment_flip, augment_rotate, random_augment

    image = _make_dummy_pcb_image()
    assert augment_flip(image, "h").shape == image.shape
    assert augment_flip(image, "v").shape == image.shape
    assert augment_rotate(image, 90.0).shape == image.shape
    bright = augment_brightness(image, 1.3)
    assert bright.shape == image.shape
    assert bright.dtype == np.uint8
    assert random_augment(image, seed=42).shape == image.shape
    print("  PASS  augmentations")


def test_preprocess_for_display() -> None:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
    cv2.imwrite(str(tmp_path), _make_dummy_pcb_image())

    from ml.pipeline.preprocess import preprocess_for_display

    result = preprocess_for_display(tmp_path)
    assert result["resized"].shape == (640, 640, 3)
    assert result["greyscale"].ndim == 2
    assert result["normalised"].dtype == np.float32
    tmp_path.unlink()
    print("  PASS  preprocess_for_display")


def test_preprocess_for_inference() -> None:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
    cv2.imwrite(str(tmp_path), _make_dummy_pcb_image())

    from ml.pipeline.preprocess import preprocess_for_inference

    result = preprocess_for_inference(tmp_path)
    assert result.shape == (640, 640, 3)
    assert result.dtype == np.float32
    assert result.max() <= 1.0
    tmp_path.unlink()
    print("  PASS  preprocess_for_inference")


def test_dataset_verify_missing() -> None:
    from ml.pipeline.dataset import verify

    counts = verify(Path("/nonexistent/dataset/path"))
    assert all(value == 0 for value in counts.values())
    print("  PASS  dataset.verify (missing path)")


def run_all() -> None:
    tests = [
        test_load_image,
        test_load_image_missing,
        test_resize_letterbox,
        test_resize_square_input,
        test_greyscale,
        test_normalise,
        test_normalise_wrong_dtype,
        test_augmentations,
        test_preprocess_for_display,
        test_preprocess_for_inference,
        test_dataset_verify_missing,
    ]

    passed = 0
    failed = 0
    print("\n-- ML Pipeline Self-Tests --")
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {test_fn.__name__}: {exc}")
            failed += 1

    print(f"\n  {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
