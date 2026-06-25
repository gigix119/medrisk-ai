"""Secure image decoding and validation.

Validation never trusts the filename extension or the client-declared content type alone -
the actual bytes are decoded with Pillow and cross-checked. EXIF and any other embedded
metadata is dropped by construction: the validated output is a freshly built RGB pixel
buffer (`Image.frombytes`), never the original `PIL.Image` object Pillow parsed the upload
into, so no `.info` dict (EXIF, ICC profiles, ...) can leak forward into preprocessing,
the response, or the database.
"""

from __future__ import annotations

import hashlib
import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from medrisk_inference.config import InferenceConfig
from medrisk_inference.constants import SUPPORTED_IMAGE_FORMATS
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
from medrisk_inference.types import ValidatedImage

_CONTENT_TYPE_BY_FORMAT = {
    "PNG": {"image/png"},
    "JPEG": {"image/jpeg", "image/jpg"},
}


def validate_image_bytes(
    data: bytes,
    *,
    config: InferenceConfig,
    declared_content_type: str | None = None,
) -> ValidatedImage:
    if not data:
        raise UploadEmptyError("Uploaded file is empty.")
    if len(data) > config.max_upload_bytes:
        raise UploadTooLargeError(
            f"Upload of {len(data)} bytes exceeds the {config.max_upload_bytes}-byte limit."
        )

    image = _decode(data, max_pixels=config.max_image_pixels)

    # Format is checked before frame count: a file in an unsupported format should be
    # rejected for that reason regardless of whether it happens to be animated too.
    declared_format = image.format or ""
    if declared_format not in SUPPORTED_IMAGE_FORMATS:
        raise UnsupportedImageFormatError(
            f"Unsupported image format: {declared_format!r}. "
            f"Supported formats: {SUPPORTED_IMAGE_FORMATS}."
        )

    if getattr(image, "n_frames", 1) > 1:
        raise ImageMultiFrameNotSupportedError("Animated/multi-frame images are not supported.")

    if declared_content_type is not None:
        allowed_content_types = _CONTENT_TYPE_BY_FORMAT.get(declared_format, set())
        if declared_content_type.lower() not in allowed_content_types:
            raise ImageMimeMismatchError(
                f"Declared content type {declared_content_type!r} does not match the "
                f"decoded image format {declared_format!r}."
            )

    width, height = image.size
    if (
        width < config.min_image_width
        or height < config.min_image_height
        or width > config.max_image_width
        or height > config.max_image_height
    ):
        raise ImageDimensionsInvalidError(
            f"Image dimensions {width}x{height} are outside the allowed range "
            f"[{config.min_image_width}x{config.min_image_height}, "
            f"{config.max_image_width}x{config.max_image_height}]."
        )
    if width * height > config.max_image_pixels:
        raise ImagePixelLimitExceededError(
            f"Image has {width * height} pixels, exceeding the limit of "
            f"{config.max_image_pixels}."
        )

    oriented = ImageOps.exif_transpose(image) or image
    rgb_source = oriented.convert("RGB")
    # Rebuild from a raw pixel buffer so no .info (EXIF, ICC profile, ...) survives.
    fresh_rgb = Image.frombytes("RGB", rgb_source.size, rgb_source.tobytes())

    return ValidatedImage(
        rgb_image_bytes=fresh_rgb.tobytes(),
        width=fresh_rgb.width,
        height=fresh_rgb.height,
        mode="RGB",
        declared_format=declared_format,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )


def _decode(data: bytes, *, max_pixels: int) -> Image.Image:
    # Pillow's own decompression-bomb guard only fires above its (large) default
    # threshold unless we point it at our own configured limit first.
    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            probe = Image.open(BytesIO(data))
            probe.verify()

            image = Image.open(BytesIO(data))
            image.load()
    except Image.DecompressionBombError as exc:
        raise ImagePixelLimitExceededError(
            f"Image rejected as a decompression bomb: {exc}"
        ) from exc
    except Warning as exc:
        raise ImagePixelLimitExceededError(
            f"Image rejected as a likely decompression bomb: {exc}"
        ) from exc
    except UnidentifiedImageError as exc:
        raise ImageDecodeFailedError(f"Could not identify image format: {exc}") from exc
    except OSError as exc:
        raise ImageDecodeFailedError(f"Image could not be decoded: {exc}") from exc
    return image
