#!/usr/bin/env bash
set -u

ROOT="/home/josefgray/projects/nativeforge"
RUN_UP=false

for arg in "$@"; do
  case "$arg" in
    --up) RUN_UP=true ;;
  esac
done

cd "$ROOT" || exit 1

echo "================ NATIVEFORGE M0 RESET ================"
echo "root=$ROOT"

echo ""
echo "--- stop managed backend/frontend (if running) ---"
bash "$ROOT/scripts/m0_demo_down.sh"

echo ""
echo "--- remove local runtime files (repo root only; .env unchanged) ---"
DELETED=()
safe_rm() {
  local path="$1"
  local label="$2"
  if [ -e "$path" ]; then
    rm -rf "$path"
    DELETED+=("$label")
    echo "removed: $label"
  else
    echo "absent (skip): $label"
  fi
}

safe_rm "$ROOT/.run" ".run/"
safe_rm "$ROOT/logs" "logs/"
safe_rm "$ROOT/nativeforge.local.db" "nativeforge.local.db"
safe_rm "$ROOT/uv.lock" "uv.lock"

echo ""
echo "--- recreate DB (file-backed SQLite + migrations + seed) ---"
export DATABASE_URL=sqlite+pysqlite:///./nativeforge.local.db
export NF_DEV_ORG_HEADERS=true

echo "DATABASE_URL=$DATABASE_URL"
echo "NF_DEV_ORG_HEADERS=$NF_DEV_ORG_HEADERS"

echo ""
echo "--- migration: uv run alembic upgrade head ---"
if uv run alembic upgrade head; then
  MIGRATION_RESULT="OK"
  echo "migration result: $MIGRATION_RESULT"
else
  MIGRATION_RESULT="FAILED"
  echo "migration result: $MIGRATION_RESULT"
  exit 1
fi

echo ""
echo "--- seed: uv run python scripts/seed_m0_demo_data.py ---"
if uv run python scripts/seed_m0_demo_data.py; then
  SEED_RESULT="OK"
  echo "seed result: $SEED_RESULT"
else
  SEED_RESULT="FAILED"
  echo "seed result: $SEED_RESULT"
  exit 1
fi

if [ "$RUN_UP" = true ]; then
  echo ""
  echo "--- start stack (--up): scripts/m0_demo_up.sh ---"
  bash "$ROOT/scripts/m0_demo_up.sh" || exit 1
fi

echo ""
echo "--- reset summary ---"
echo "stopped: managed backend/frontend (see messages above; pid files cleared)"
if [ "${#DELETED[@]}" -gt 0 ]; then
  echo "deleted: ${DELETED[*]}"
else
  echo "deleted: (none of the target paths were present)"
fi
echo "migration: $MIGRATION_RESULT"
echo "seed: $SEED_RESULT"

echo ""
echo "--- next commands ---"
if [ "$RUN_UP" != true ]; then
  echo "  nf-up              # start backend + frontend"
fi
echo "  nf-status          # health + trust manifest probe"
echo "  open               http://127.0.0.1:5173/"
echo "  nf-down            # stop managed processes when finished"
echo "======================================================"
