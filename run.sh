#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$ROOT_DIR/job-finder-web"
PYTHON_BIN="$APP_DIR/venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Missing project virtual environment: $PYTHON_BIN" >&2
    echo "Run $APP_DIR/setup.sh first." >&2
    exit 1
fi

cd "$APP_DIR"
exec "$PYTHON_BIN" run.py
