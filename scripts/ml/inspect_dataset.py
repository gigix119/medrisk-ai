#!/usr/bin/env python
"""Thin wrapper: `python scripts/ml/inspect_dataset.py --config configs/ml/smoke.yaml`."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from medrisk_ml.cli import build_parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args(["data", "inspect", *sys.argv[1:]])
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
