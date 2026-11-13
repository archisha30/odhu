"""Tests for the photo checks, using the real sample images in /samples."""

import io
from pathlib import Path

from PIL import Image

from app.services import image_check

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def score(name: str) -> float:
    return image_check.sharpness(Image.open(SAMPLES / name))


def test_sharp_samples_pass_and_blurry_sample_fails():
    for name in ["01_electricity_bill_kn.png", "03_bank_letter_en.png", "04_bank_sms_screenshot.png"]:
        assert score(name) > image_check.MIN_SHARPNESS * 2, name  # comfortably above the line
    assert score("06_blurry_photo.png") < image_check.MIN_SHARPNESS


def test_big_photo_is_shrunk_to_jpeg():
    big = Image.new("RGB", (4000, 3000), "white")
    buffer = io.BytesIO()
    big.save(buffer, format="PNG")

    data, mime, _ = image_check.prepare_image(buffer.getvalue(), "image/png")

    assert mime == "image/jpeg"
    assert max(Image.open(io.BytesIO(data)).size) == image_check.MAX_SIDE


def test_small_photo_is_sent_unchanged():
    original = (SAMPLES / "04_bank_sms_screenshot.png").read_bytes()

    data, mime, sharpness = image_check.prepare_image(original, "image/png")

    assert data == original and mime == "image/png"
    assert sharpness is not None


def test_unopenable_image_is_passed_through_without_a_score():
    data, mime, sharpness = image_check.prepare_image(b"not really an image", "image/heic")

    assert (data, mime, sharpness) == (b"not really an image", "image/heic", None)
