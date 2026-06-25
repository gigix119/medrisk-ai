# Image input contract

What `POST /api/v1/predictions/histopathology` accepts, in what order it is checked, and exactly what does and does not survive validation. Implemented in [medrisk_inference/image_validation.py](../medrisk_inference/image_validation.py); orchestrated (upload streaming, the strict-shape check) in [app/services/prediction.py](../app/services/prediction.py) and [medrisk_inference/service.py](../medrisk_inference/service.py).

## Request shape

`multipart/form-data` with:

| Field | Required | Notes |
|---|---|---|
| `file` | yes | The image. |
| `include_explanation` | no, default `false` | Form boolean. Generates a Grad-CAM overlay if `true`. |
| `client_reference` | no | Free-text, max 100 characters, stored verbatim and echoed back. **Must not contain patient-identifying information** — the API has no way to detect or strip it. |

## Validation order

Each step raises a distinct, stable error code on failure (see the table in [inference-architecture.md](inference-architecture.md#error-codes)) and short-circuits — a request never pays for steps after the first failure:

1. **Streamed size cap** (`read_upload_within_limit`, `app/services/prediction.py`). The upload is read in 64 KiB chunks; the running total is checked against `MAX_UPLOAD_BYTES` (default 5 MiB) on every chunk, so an oversized upload is rejected *before* it is ever fully buffered in memory. `Content-Length` is never trusted on its own — a client can misreport it.
2. **Non-empty.** A zero-byte body is `UPLOAD_EMPTY`, distinct from a too-large one.
3. **Decode, under a decompression-bomb guard.** `Image.MAX_IMAGE_PIXELS` is set to the configured `MAX_IMAGE_PIXELS` (default ~16.7 megapixels) before Pillow ever touches the bytes, and `Image.DecompressionBombWarning` is promoted to an error (`warnings.simplefilter("error", ...)`) so a crafted file that *would* decode — just into something enormous — is rejected rather than silently allowed through Pillow's default (much larger) threshold. `probe.verify()` runs first (structural check without fully decoding pixel data), then a second `Image.open(...).load()` actually decodes.
4. **Format.** Only `PNG` and `JPEG` (`SUPPORTED_IMAGE_FORMATS`) are accepted, checked against Pillow's own format sniffing (`image.format`), not the filename extension.
5. **Multi-frame rejection.** Animated PNG/GIF (`n_frames > 1`) is rejected. This check runs *after* the format check deliberately: an animated file in an unsupported format is reported as `UNSUPPORTED_IMAGE_FORMAT`, not `IMAGE_MULTIFRAME_NOT_SUPPORTED` — the more specific, more useful reason wins.
6. **Declared-MIME-vs-actual-format cross-check.** If the client sent a `Content-Type` header, it must match the format Pillow actually decoded (`image/png` ↔ `PNG`, `image/jpeg`/`image/jpg` ↔ `JPEG`). A mismatched declaration is rejected (`IMAGE_MIME_MISMATCH`) rather than silently trusted or silently ignored.
7. **Dimension bounds.** Width and height must each fall within `[MIN_IMAGE_WIDTH, MAX_IMAGE_WIDTH]` / `[MIN_IMAGE_HEIGHT, MAX_IMAGE_HEIGHT]` (defaults 32–4096 px).
8. **Pixel-count bound.** `width * height` must not exceed `MAX_IMAGE_PIXELS`, independent of the decompression-bomb check in step 3 (a legitimately-sized file can still describe more pixels than the configured ceiling allows).
9. **Strict model input shape** (`service.py::validate_upload`, only when `STRICT_MODEL_INPUT_SHAPE=true`, the default). Width and height must *exactly* equal the active model's `input_width`/`input_height` — no resize-to-fit. This is a patch classifier, evaluated on a fixed input size; silently resizing an arbitrary upload to fit would feed it data outside the distribution its metrics describe.

## What happens to the image after validation

- **EXIF orientation is applied, then discarded.** `ImageOps.exif_transpose()` rotates/flips the pixel data to match the orientation the EXIF tag describes — so a sideways phone photo still classifies right-side-up — but the EXIF tag itself does not survive.
- **Every other metadata field is dropped by construction, not by filtering.** The validated output is built via `Image.frombytes("RGB", size, rgb_source.tobytes())` — a brand-new image object made only from raw pixel bytes. Pillow's `.info` dict (EXIF, ICC color profiles, text chunks, anything else a format allows embedding) belongs to the *original* `Image` object and is never copied onto this one. There is no metadata-stripping allowlist/denylist to maintain or get wrong.
- **The validated result (`ValidatedImage`) carries pixel bytes, dimensions, format, a SHA-256 of the *original* upload, and its byte size — nothing else.** The SHA-256 is computed over the original bytes (before any stripping) specifically so it's useful as a duplicate-detection/audit key even though the bytes themselves are never stored.

## What is never persisted or returned

- The raw uploaded file. Not on disk, not in the database, not in any response.
- The original filename, verbatim — only `sanitize_filename()`'s output (path components and control characters stripped, truncated to 128 chars) is stored, as `input_filename_safe`.
- EXIF, ICC profiles, or any other embedded metadata from the original file.
- A base64/encoded copy of the input image anywhere in the database. (The Grad-CAM *explanation* image is base64-encoded, but only in the immediate POST response — see [inference-architecture.md](inference-architecture.md#key-decisions) — and is itself derived from the stripped, validated pixel buffer, never the original upload bytes.)

## Why PNG/JPEG only, and why no DICOM

This project works with PCam-style 96×96 (or similarly small) RGB patches, not whole-slide images — DICOM, OpenSlide formats (`.svs`, `.tiff` pyramids), and multi-gigabyte WSI handling are a substantially different engineering problem (tiling, pyramid levels, vendor-specific metadata) that this phase does not attempt. PNG and JPEG cover every format the Phase 2 dataset pipeline and the bundled synthetic/PCam patches actually use.
