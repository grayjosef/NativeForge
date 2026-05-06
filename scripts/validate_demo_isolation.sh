#!/usr/bin/env bash
# Local / CI helper: NF-001 demo isolation checks (subset + SQL grep gate).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python scripts/check_nf_sql_grep.py
ruff check src tests
ruff format --check src tests
pytest tests/test_demo_isolation.py tests/test_isolation_routes.py -q
