"""Runs the standard local quality gates in sequence, mirroring CI:

  ruff format --check, ruff check, mypy, pytest (with coverage).

Stops at the first failure so you fix issues in the order CI would report them.
"""

import subprocess
import sys

CHECKS: list[tuple[str, list[str]]] = [
    ("ruff format --check", [sys.executable, "-m", "ruff", "format", "--check", "."]),
    ("ruff check", [sys.executable, "-m", "ruff", "check", "."]),
    ("mypy", [sys.executable, "-m", "mypy", "app", "scripts", "medrisk_ml", "medrisk_inference"]),
    (
        "pytest",
        [
            sys.executable,
            "-m",
            "pytest",
            "--cov=app",
            "--cov=medrisk_inference",
            "--cov-report=term-missing",
        ],
    ),
]


def main() -> None:
    for name, command in CHECKS:
        print(f"\n=== {name} ===", flush=True)
        result = subprocess.run(command)
        if result.returncode != 0:
            print(f"\n'{name}' failed (exit code {result.returncode}). Stopping.", flush=True)
            sys.exit(result.returncode)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
