#!/usr/bin/env bash
# Deterministic, no-network connector closeout tests (Sprint 30). Full log under /tmp.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="/tmp/nativeforge_connector_closeout_$(date +%Y%m%d_%H%M%S).log"
cd "$ROOT"
{
  echo "=== CONNECTOR CLOSEOUT (backend only, no npm) ==="
  echo "root=$ROOT"
  echo
  uv run ruff check src/nativeforge/services/source_connectors \
    tests/test_sprint30_connector_closeout_validation.py
  uv run ruff format --check src/nativeforge/services/source_connectors \
    tests/test_sprint30_connector_closeout_validation.py
  uv run pytest -q tests/test_sprint30_connector_closeout_validation.py
} > "$LOG" 2>&1
EC=$?
echo "================ COPY THIS SUMMARY ================"
echo "=== NATIVEFORGE CONNECTOR CLOSEOUT CHECK ==="
echo "exit_code=$EC"
echo "log=$LOG"
tail -n 80 "$LOG"
echo "=================================================="
exit "$EC"
