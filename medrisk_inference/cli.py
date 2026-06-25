"""Command-line entrypoint: `python -m medrisk_inference.cli <command> ...`.

No command in this module touches PostgreSQL or FastAPI - every command works directly
against a bundle directory on disk, so a developer can verify/warm-up/predict/benchmark a
model without running the full backend.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from medrisk_inference.config import InferenceConfig
from medrisk_inference.constants import MEDICAL_DISCLAIMER, SYNTHETIC_MODEL_WARNING
from medrisk_inference.exceptions import InferenceError
from medrisk_inference.runtime import HistopathologyModelRuntime
from medrisk_inference.service import run_inference
from medrisk_inference.utils import sanitize_filename

_EXIT_OK = 0
_EXIT_ERROR = 1


def _build_config(args: argparse.Namespace) -> InferenceConfig:
    return InferenceConfig(
        environment=args.environment,
        model_bundle_path=args.bundle_path,
        model_device=args.device,
        model_warmup_enabled=True,
        allow_synthetic_model=args.allow_synthetic,
        gradcam_enabled=True,
    )


def _add_common_bundle_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--bundle-path", required=True, help="Path to a model bundle directory.")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument(
        "--environment",
        default="development",
        choices=["development", "test", "production"],
        help="Which environment policy to apply when deciding if a synthetic bundle is allowed.",
    )
    parser.add_argument(
        "--allow-synthetic",
        action="store_true",
        help="Permit loading a synthetic_only bundle outside the test environment.",
    )


def _print_model_summary(runtime: HistopathologyModelRuntime) -> None:
    manifest = runtime.manifest
    print(f"model_id:          {manifest.model_id}")
    print(f"architecture:      {manifest.architecture}")
    print(f"dataset_mode:      {manifest.dataset_mode}")
    print(f"synthetic_only:    {manifest.synthetic_only}")
    print(f"eligible_for_demo: {manifest.eligible_for_demo}")
    print(f"device:            {runtime.device.device}")
    print(f"threshold:         {runtime.threshold}")
    if manifest.synthetic_only:
        print(f"WARNING: {SYNTHETIC_MODEL_WARNING}")
    print(MEDICAL_DISCLAIMER)


def cmd_environment(_args: argparse.Namespace) -> int:
    import torch
    import torchvision

    print(f"python:      {sys.version.split()[0]}")
    print(f"torch:       {torch.__version__}")
    print(f"torchvision: {torchvision.__version__}")
    print(f"cuda_available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"device_name: {torch.cuda.get_device_name(0)}")
    print(MEDICAL_DISCLAIMER)
    return _EXIT_OK


def cmd_verify_bundle(args: argparse.Namespace) -> int:
    config = _build_config(args)
    try:
        runtime = HistopathologyModelRuntime.load(args.bundle_path, config)
    except InferenceError as exc:
        print(f"FAILED [{exc.error_code}]: {exc.message}", file=sys.stderr)
        return _EXIT_ERROR
    _print_model_summary(runtime)
    print("Bundle verification + warm-up: OK")
    runtime.close()
    return _EXIT_OK


def cmd_warmup(args: argparse.Namespace) -> int:
    config = _build_config(args)
    try:
        runtime = HistopathologyModelRuntime.load(args.bundle_path, config)
    except InferenceError as exc:
        print(f"FAILED [{exc.error_code}]: {exc.message}", file=sys.stderr)
        return _EXIT_ERROR
    health = runtime.health()
    print(json.dumps(vars(health), default=str, indent=2))
    runtime.close()
    return _EXIT_OK if health.ready else _EXIT_ERROR


def cmd_predict(args: argparse.Namespace) -> int:
    config = _build_config(args)
    image_path = Path(args.image)
    if not image_path.is_file():
        print(f"Image not found: {image_path}", file=sys.stderr)
        return _EXIT_ERROR

    try:
        runtime = HistopathologyModelRuntime.load(args.bundle_path, config)
        result = run_inference(
            runtime,
            image_path.read_bytes(),
            declared_content_type=None,
            include_explanation=args.include_explanation,
        )
    except InferenceError as exc:
        print(f"FAILED [{exc.error_code}]: {exc.message}", file=sys.stderr)
        return _EXIT_ERROR

    summary = {
        "model_id": result.model.model_id,
        "synthetic_only": result.model.synthetic_only,
        "decision": result.decision.decision,
        "predicted_class": result.decision.predicted_class,
        "raw_probability": result.raw_output.raw_probability,
        "calibrated_probability": result.decision.calibrated_probability,
        "threshold": result.decision.threshold,
        "input_filename": sanitize_filename(image_path.name),
        "timings_ms": vars(result.timings),
        "explanation_status": result.explanation.status,
    }
    print(json.dumps(summary, indent=2))

    if args.include_explanation and result.explanation.data and args.output_explanation:
        import base64

        Path(args.output_explanation).write_bytes(base64.b64decode(result.explanation.data))
        print(f"Explanation PNG written to {args.output_explanation}")

    if result.model.synthetic_only:
        print(f"WARNING: {SYNTHETIC_MODEL_WARNING}")
    print(MEDICAL_DISCLAIMER)
    runtime.close()
    return _EXIT_OK


def cmd_benchmark(args: argparse.Namespace) -> int:
    config = _build_config(args)
    image_path = Path(args.image)
    if not image_path.is_file():
        print(f"Image not found: {image_path}", file=sys.stderr)
        return _EXIT_ERROR
    image_bytes = image_path.read_bytes()

    try:
        runtime = HistopathologyModelRuntime.load(args.bundle_path, config)
        for _ in range(args.warmup_runs):
            run_inference(runtime, image_bytes, include_explanation=False)

        durations_ms: list[float] = []
        for _ in range(args.runs):
            started = time.perf_counter()
            run_inference(runtime, image_bytes, include_explanation=False)
            durations_ms.append((time.perf_counter() - started) * 1000)
    except InferenceError as exc:
        print(f"FAILED [{exc.error_code}]: {exc.message}", file=sys.stderr)
        return _EXIT_ERROR

    durations_ms.sort()
    p95_index = max(0, int(len(durations_ms) * 0.95) - 1)
    print(
        json.dumps(
            {
                "runs": args.runs,
                "mean_ms": statistics.mean(durations_ms),
                "median_ms": statistics.median(durations_ms),
                "p95_ms": durations_ms[p95_index],
                "min_ms": durations_ms[0],
                "max_ms": durations_ms[-1],
                "device": str(runtime.device.device),
            },
            indent=2,
        )
    )
    runtime.close()
    return _EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m medrisk_inference.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("environment", help="Print interpreter/library/hardware info.")

    verify_parser = subparsers.add_parser(
        "verify-bundle", help="Verify a model bundle loads and warms up."
    )
    _add_common_bundle_args(verify_parser)

    warmup_parser = subparsers.add_parser("warmup", help="Load a bundle and report runtime health.")
    _add_common_bundle_args(warmup_parser)

    predict_parser = subparsers.add_parser(
        "predict", help="Run one local prediction against an image file."
    )
    _add_common_bundle_args(predict_parser)
    predict_parser.add_argument("--image", required=True, help="Path to a local PNG/JPEG image.")
    predict_parser.add_argument("--include-explanation", action="store_true")
    predict_parser.add_argument(
        "--output-explanation",
        default=None,
        help="If set with --include-explanation, write the Grad-CAM PNG here.",
    )

    benchmark_parser = subparsers.add_parser("benchmark", help="Benchmark local inference latency.")
    _add_common_bundle_args(benchmark_parser)
    benchmark_parser.add_argument("--image", required=True, help="Path to a local PNG/JPEG image.")
    benchmark_parser.add_argument("--warmup-runs", type=int, default=5)
    benchmark_parser.add_argument("--runs", type=int, default=50)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    handlers = {
        "environment": cmd_environment,
        "verify-bundle": cmd_verify_bundle,
        "warmup": cmd_warmup,
        "predict": cmd_predict,
        "benchmark": cmd_benchmark,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
