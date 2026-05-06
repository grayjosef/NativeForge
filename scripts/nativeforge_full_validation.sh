#!/usr/bin/env bash
# Full stack checks aligned with .github/workflows/ci.yml (backend + frontend).
# Frontend: must run `npm ci` before typecheck/build so `vite` / `tsc` resolve
# (same as CI). Running `npm run typecheck` without install causes exit 127.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="/tmp/nativeforge_full_validation_$(date +%Y%m%d_%H%M%S).log"
cd "$ROOT"
{
  echo "=== GIT STATE ==="
  git status --short
  echo
  echo "=== BACKEND (match CI: ruff + grep gate + pytest) ==="
  uv run ruff check src tests
  uv run ruff format --check src tests
  python3 scripts/check_nf_sql_grep.py
  uv run pytest -q
  echo
  echo "=== FRONTEND ==="
  if [ -f frontend/package.json ]; then
    cd frontend
    echo "--- npm ci (installs vite, tsc, etc.) ---"
    npm ci
    echo "--- scripts ---"
    node -e "const p=require(\"./package.json\"); console.log(Object.keys(p.scripts||{}).join(\"\\n\"))"
    npm run typecheck
    npm run build
    if node -e "const p=require(\"./package.json\"); process.exit(p.scripts && p.scripts.lint ? 0 : 1)"; then
      npm run lint
    else
      echo "SKIP: no npm run lint in package.json"
    fi
    if node -e "const p=require(\"./package.json\"); process.exit(p.scripts && p.scripts.test ? 0 : 1)"; then
      npm test
    else
      echo "SKIP: no npm test in package.json"
    fi
    cd "$ROOT"
  else
    echo "frontend/package.json not found — frontend validation N/A"
  fi
  echo
  echo "=== MIGRATIONS ==="
  find "$ROOT/alembic/versions" -maxdepth 1 -type f -name "*.py" | sort || true
  uv run alembic history 2>/dev/null || echo "uv run alembic history skipped (no env / DB)"
} > "$LOG" 2>&1
EC=$?
echo "================ COPY THIS SUMMARY ================"
echo "=== NATIVEFORGE FULL VALIDATION ==="
echo "exit_code=$EC"
echo "log=$LOG"
tail -n 200 "$LOG"
echo "=================================================="
exit "$EC"
