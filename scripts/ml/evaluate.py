#!/usr/bin/env python
"""Thin wrapper: `python scripts/ml/evaluate.py --experiment-id <EXPERIMENT_ID>`."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from medrisk_ml.cli import build_parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args(["evaluate", *sys.argv[1:]])
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
