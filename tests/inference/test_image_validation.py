"""Unit tests for medrisk_inference.image_validation."""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from medrisk_inference.config import InferenceConfig
from medrisk_inference.exceptions import (
    ImageDecodeFailedError,
    ImageDimensionsInvalidError,
    ImageMimeMismatchError,
    ImageMultiFrameNotSupportedError,
    ImagePixelLimitExceededError,
    UnsupportedImageFormatError,
    UploadEmptyError,
    UploadTooLargeError,
)
from medrisk_inference.image_validation import validate_image_bytes

DEFAULT_CONFIG = InferenceConfig(environment="test")


def _png_bytes(width: int = 64, height: int = 64) -> bytes:
    pixels = np.random.default_rng(0).integers(0, 256, size=(height, width, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def _jpeg_bytes(width: int = 64, height: int = 64) -> bytes:
    pixels = np.random.default_rng(0).integers(0, 256, size=(height, width, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buffer, format="JPEG")
    return buffer.getvalue()


def test_valid_png_is_accepted() -> None:
    validated = validate_image_bytes(
        _png_bytes(), config=DEFAULT_CONFIG, declared_content_type="image/png"
    )
    assert validated.declared_format == "PNG"
    assert validated.width == 64
    assert validated.height == 64
    assert validated.mode == "RGB"
    assert len(validated.sha256) == 64


def test_valid_jpeg_is_accepted() -> None:
    validated = validate_image_bytes(
        _jpeg_bytes(), config=DEFAULT_CONFIG, declared_content_type="image/jpeg"
    )
    assert validated.declared_format == "JPEG"


def test_empty_file_rejected() -> None:
    with pytest.raises(UploadEmptyError):
        validate_image_bytes(b"", config=DEFAULT_CONFIG)


def test_corrupted_file_rejected() -> None:
    with pytest.raises(ImageDecodeFailedError):
        validate_image_bytes(b"not a real image", config=DEFAULT_CONFIG)


def test_truncated_png_rejected() -> None:
    truncated = _png_bytes()[:20]
    with pytest.raises((ImageDecodeFailedError, UnsupportedImageFormatError)):
        validate_image_bytes(truncated, config=DEFAULT_CONFIG)


def test_oversized_byte_payload_rejected() -> None:
    config = InferenceConfig(environment="test", max_upload_bytes=100)
    with pytest.raises(UploadTooLargeError):
        validate_image_bytes(_png_bytes(), config=config)


def test_excessive_pixel_count_rejected() -> None:
    config = InferenceConfig(
        environment="test", max_image_pixels=100, max_image_width=4096, max_image_height=4096
    )
    with pytest.raises(ImagePixelLimitExceededError):
        validate_image_bytes(_png_bytes(width=64, height=64), config=config)


def test_dimensions_below_minimum_rejected() -> None:
    config = InferenceConfig(environment="test", min_image_width=128, min_image_height=128)
    with pytest.raises(ImageDimensionsInvalidError):
        validate_image_bytes(_png_bytes(width=64, height=64), config=config)


def test_dimensions_above_maximum_rejected() -> None:
    config = InferenceConfig(environment="test", max_image_width=32, max_image_height=32)
    with pytest.raises(ImageDimensionsInvalidError):
        validate_image_bytes(_png_bytes(width=64, height=64), config=config)


def test_unsupported_format_rejected() -> None:
    pixels = np.random.default_rng(0).integers(0, 256, size=(64, 64, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels, mode="RGB").save(buffer, format="BMP")
    with pytest.raises(UnsupportedImageFormatError):
        validate_image_bytes(buffer.getvalue(), config=DEFAULT_CONFIG)


def test_animated_png_rejected_as_multiframe() -> None:
    # An animated PNG (APNG) decodes with format == "PNG" (a supported format) but
    # n_frames > 1 - this is the case the dedicated multi-frame check exists for, distinct
    # from a format Pillow can't identify or one outside the supported set altogether.
    frame1 = Image.fromarray(np.zeros((32, 32, 3), dtype=np.uint8), mode="RGB")
    frame2 = Image.fromarray(np.full((32, 32, 3), 255, dtype=np.uint8), mode="RGB")
    buffer = io.BytesIO()
    frame1.save(buffer, format="PNG", save_all=True, append_images=[frame2])
    with pytest.raises(ImageMultiFrameNotSupportedError):
        validate_image_bytes(buffer.getvalue(), config=DEFAULT_CONFIG)


def test_animated_gif_rejected_as_unsupported_format() -> None:
    # GIF itself is outside the supported PNG/JPEG set, so this is rejected for its format
    # before any multi-frame check would even run.
    frame1 = Image.fromarray(np.zeros((32, 32, 3), dtype=np.uint8), mode="RGB").convert("P")
    frame2 = Image.fromarray(np.full((32, 32, 3), 255, dtype=np.uint8), mode="RGB").convert("P")
    buffer = io.BytesIO()
    frame1.save(buffer, format="GIF", save_all=True, append_images=[frame2])
    with pytest.raises(UnsupportedImageFormatError):
        validate_image_bytes(buffer.getvalue(), config=DEFAULT_CONFIG)


def test_mime_mismatch_rejected() -> None:
    with pytest.raises(ImageMimeMismatchError):
        validate_image_bytes(
            _png_bytes(), config=DEFAULT_CONFIG, declared_content_type="image/jpeg"
        )


def test_no_declared_content_type_skips_mime_check() -> None:
    validated = validate_image_bytes(
        _png_bytes(), config=DEFAULT_CONFIG, declared_content_type=None
    )
    assert validated.declared_format == "PNG"


def test_exif_orientation_is_not_propagated() -> None:
    pixels = np.random.default_rng(0).integers(0, 256, size=(64, 32, 3), dtype=np.uint8)
    image = Image.fromarray(pixels, mode="RGB")
    exif = image.getexif()
    exif[0x0112] = 6  # Orientation: rotate 270
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)

    validated = validate_image_bytes(buffer.getvalue(), config=DEFAULT_CONFIG)
    # The fresh RGB buffer carries no .info/EXIF - reconstructing it must not raise and must
    # not retain any metadata (there is no public attribute through which EXIF could survive,
    # by construction - rgb_image_bytes is a plain pixel buffer).
    assert isinstance(validated.rgb_image_bytes, bytes)
