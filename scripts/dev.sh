#!/usr/bin/env bash
# Convenience launcher for local development on Linux/macOS.
# Prints every command it runs - nothing here is hidden magic.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$REPO_ROOT/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "Virtual environment not found at .venv. Create it first:"
    echo "  python3.12 -m venv .venv"
    echo "  .venv/bin/python -m pip install -r requirements-dev.txt"
    exit 1
fi

echo "Running: $VENV_PYTHON -m uvicorn app.main:app --reload"
exec "$VENV_PYTHON" -m uvicorn app.main:app --reload
