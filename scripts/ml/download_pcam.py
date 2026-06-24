#!/usr/bin/env python
"""Thin wrapper around `data download`.

Windows PowerShell:
    $env:MEDRISK_ALLOW_DATA_DOWNLOAD = "1"
    python scripts/ml/download_pcam.py --config configs/ml/resnet18.yaml --download
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from medrisk_ml.cli import build_parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args(["data", "download", *sys.argv[1:]])
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
