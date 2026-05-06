#!/usr/bin/env bash
# Backend coverage (requires `uv sync --extra dev`).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
uv run pytest -q --cov=nativeforge --cov-report=term-missing "$@"
