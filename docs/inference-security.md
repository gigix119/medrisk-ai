# Inference security (Phase 3)

This extends [security.md](security.md) with everything specific to real model inference: untrusted image uploads, a loaded PyTorch model in-process, and a richer error surface. Read that file first for auth/JWT/password handling, which is unchanged.

## Threat model for the upload path

The histopathology endpoint accepts an arbitrary file from any authenticated user. It is treated as hostile input, not as "probably a histopathology patch":

| Risk | Mitigation |
|---|---|
| Decompression bomb (small file, enormous decoded size) | `Image.MAX_IMAGE_PIXELS` set to the configured cap before decode; `DecompressionBombWarning` promoted to a hard error. See [image-input-contract.md](image-input-contract.md). |
| Memory exhaustion via an oversized upload | Streamed, chunked read with a running byte-count check against `MAX_UPLOAD_BYTES` — rejected before the full body is ever buffered, and never trusting a client-supplied `Content-Length`. |
| Format/MIME confusion (polyglot files, spoofed `Content-Type`) | The declared `Content-Type` is cross-checked against Pillow's *own* format sniffing of the decoded bytes, not trusted alone; only `PNG`/`JPEG` are accepted regardless. |
| Metadata exfiltration via EXIF/ICC profiles (GPS tags, embedded comments, camera serial numbers) | The validated image is rebuilt from a raw pixel buffer (`Image.frombytes`) — Pillow's `.info` dict from the original parse is structurally unreachable from that point on, not filtered after the fact. |
| Animated-image decode cost amplification | Multi-frame images (`n_frames > 1`) are rejected outright; only the first frame is ever considered, and only for files that are already single-frame. |
| Arbitrary file read / path traversal via a "model path" parameter | Not applicable by construction — no endpoint accepts a path. `MODEL_BUNDLE_PATH` is a server-side environment variable only. |

## What is never logged, persisted, or returned

- **Raw image bytes.** Never written to disk, never stored in the database, never echoed in a response. Only a SHA-256 of the original upload (`input_sha256`) and basic technical metadata (dimensions, format, byte size) are kept.
- **EXIF/ICC/embedded metadata.** Dropped before the validated image even exists as an object — see above.
- **Filenames, verbatim.** `sanitize_filename()` strips path components and control characters and truncates to 128 chars before anything derived from a client-supplied filename touches the database (`input_filename_safe`).
- **Raw exception text from a model/runtime failure.** `run_histopathology_prediction()` (`app/services/prediction.py`) catches *any* exception that isn't already a recognized `AppError`, logs the full exception **server-side only** via `logger.exception(...)`, marks the `Prediction` row failed with a generic `error_code="INFERENCE_FAILED"` and a fixed safe message, and raises a brand-new generic `AppError` — the original exception object (and anything it might contain: a file path, a tensor repr, a third-party library's internal message) never reaches the HTTP response or the database. This is covered by an integration test (`test_inference_failure_marks_prediction_failed_without_leaking_internals`) that deliberately raises an exception containing a fake secret path and asserts it appears nowhere in the response or the stored row.
- **The model bundle's filesystem path.** Present internally on `ModelDeployment.bundle_path` for operator debugging only; never serialized into `ActiveModelResponse`, `ModelHealthResponse`, or any other schema. `tests/integration/test_model_metadata.py::test_response_never_includes_bundle_path` asserts this directly.
- **The Grad-CAM explanation image, anywhere except the immediate POST response.** It is base64-encoded PNG data, generated fresh per request, and intentionally has no database column — history and detail reads return `explanation_status` (a string) but structurally cannot return the image itself.

## Error message safety

`medrisk_inference` exceptions carry two things: a stable `error_code` (safe to expose; it's an enum-like string, never derived from request content) and a human-readable `message` (which **may** describe internal state — a missing manifest field, a tensor shape — and is not assumed safe). `translate_inference_error()` (`app/services/prediction.py`) decides per status class:

- **4xx → message shown verbatim.** These only ever describe properties of the upload itself ("dimensions 64x64 do not match required 32x32"), which the client already knows because they sent it.
- **5xx → message replaced with a fixed generic string** ("The inference request could not be completed due to an internal error."), regardless of what the original message said. A 503/500-class failure usually means something about the *model* or *runtime* went wrong, which is never the client's information to have.

## Synthetic-model guardrails (defense in depth)

A synthetic-only model bundle (`manifest.synthetic_only=true`) has no medical meaning at all — it exists purely to exercise the pipeline end-to-end without a real trained model. Three independent layers prevent it from ever being mistaken for something real:

1. **`app/core/config.py::Settings.validate_production_model_policy`** — refuses to even start the app in `ENVIRONMENT=production` with `ALLOW_SYNTHETIC_MODEL=true`.
2. **`medrisk_inference/config.py::InferenceConfig.synthetic_model_allowed`** — re-derives the same answer independently inside the package that actually loads bundles, rather than trusting the app layer's settings object got passed through correctly.
3. **`medrisk_inference/bundle.py::load_bundle`** — checks `manifest.synthetic_only and not config.synthetic_model_allowed` at the point of load and refuses with `MODEL_BUNDLE_INVALID`, and separately refuses any bundle where `synthetic_only` and `eligible_for_demo` are both true (already prevented at Phase 2 registration time, but bundles are files on disk and could in principle be hand-edited — this is a defensive re-check, not redundant paranoia).

Every response that touches the active model (the prediction response, `/api/v1/models/active`, `/health/model`) also includes `synthetic_only` explicitly, and the medical disclaimer is present on every prediction response, every model-metadata response, and the API root.

## Concurrency as a DoS consideration

`INFERENCE_MAX_CONCURRENCY` (default 1) plus `INFERENCE_QUEUE_TIMEOUT_SECONDS` (default 5) bound how many requests can be doing inference at once and how long an excess request waits before failing fast with `429` (and a `Retry-After` header) rather than queuing unboundedly. This is concurrency control, not rate limiting — it stops the model from being overwhelmed by simultaneous *concurrent* requests. As of Phase 8, both inference endpoints (`POST /predictions/histopathology` and `POST /datasets/{id}/samples/{id}/predict`) are additionally covered by `RATE_LIMIT_INFERENCE_PER_MINUTE` (`app/core/rate_limit.py`) to bound *sequential* requests from one client too — see [security.md](security.md) "Rate limiting (Phase 8)". The limiter is per-process/in-memory, not distributed (see [SECURITY_AUDIT.md](SECURITY_AUDIT.md)).

## Bundle loading trust boundary

`load_bundle()` treats the bundle directory as a trusted-but-verify input: trusted in the sense that only an operator (via `MODEL_BUNDLE_PATH`) can point at one, but still verified — `medrisk_ml.registry.bundle.verify_bundle()`'s checksum + smoke-inference check, plus Phase 3's own re-checks (square input, `positive_class` actually in `class_names`, normalization shape, synthetic-in-production) — because a bundle is still a file on disk that could have been corrupted, partially copied, or hand-edited since it was registered. `_ensure_no_symlink_escape()` additionally resolves every expected bundle file and rejects any that resolves outside the bundle directory, so a symlink planted inside a bundle directory cannot be used to make `load_bundle` read a file from elsewhere on the filesystem.

## No real patient data — unchanged from Phase 1, reinforced by Phase 3

Everything in [security.md](security.md)'s "No real patient data" section still holds, and Phase 3 reinforces rather than weakens it: the upload pipeline doesn't merely *avoid* storing raw images — it makes storing them structurally impossible (there is no code path that writes `rgb_image_bytes` anywhere persistent), and `client_reference` is documented, in both the API schema description and this doc, as a field that must never contain patient-identifying information, even though the API itself cannot enforce that for a free-text field.
