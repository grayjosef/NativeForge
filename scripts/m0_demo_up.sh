#!/usr/bin/env bash
set -u

ROOT="/home/josefgray/projects/nativeforge"
RUN_DIR="$ROOT/.run"
LOG_DIR="$ROOT/logs"
BACKEND_LOG="$LOG_DIR/m0_backend.log"
FRONTEND_LOG="$LOG_DIR/m0_frontend.log"
BACKEND_PID="$RUN_DIR/m0_backend.pid"
FRONTEND_PID="$RUN_DIR/m0_frontend.pid"

mkdir -p "$RUN_DIR" "$LOG_DIR"
cd "$ROOT" || exit 1

echo "================ NATIVEFORGE M0 UP ================"
echo "root=$ROOT"

cat > "$ROOT/.env" <<'ENVEOF'
DATABASE_URL=sqlite+pysqlite:///./nativeforge.local.db
NF_DEV_ORG_HEADERS=true
ENVEOF

export DATABASE_URL=sqlite+pysqlite:///./nativeforge.local.db
export NF_DEV_ORG_HEADERS=true

echo "--- migrate DB ---"
uv run alembic upgrade head || exit 1

echo "--- seed M0 orgs ---"
uv run python scripts/seed_m0_demo_data.py || exit 1

echo "--- stop stale managed processes if present ---"
if [ -f "$BACKEND_PID" ] && kill -0 "$(cat "$BACKEND_PID")" 2>/dev/null; then
  kill "$(cat "$BACKEND_PID")" 2>/dev/null || true
fi
if [ -f "$FRONTEND_PID" ] && kill -0 "$(cat "$FRONTEND_PID")" 2>/dev/null; then
  kill "$(cat "$FRONTEND_PID")" 2>/dev/null || true
fi
rm -f "$BACKEND_PID" "$FRONTEND_PID"

echo "--- start backend :8000 ---"
nohup bash -lc '
  cd /home/josefgray/projects/nativeforge
  export DATABASE_URL=sqlite+pysqlite:///./nativeforge.local.db
  export NF_DEV_ORG_HEADERS=true
  uv run uvicorn nativeforge.main:app --reload --host 127.0.0.1 --port 8000
' > "$BACKEND_LOG" 2>&1 &
echo $! > "$BACKEND_PID"

echo "--- start frontend :5173 ---"
nohup bash -lc '
  cd /home/josefgray/projects/nativeforge/frontend
  if [ ! -d node_modules ]; then npm ci; fi
  npm run dev -- --host 127.0.0.1 --port 5173
' > "$FRONTEND_LOG" 2>&1 &
echo $! > "$FRONTEND_PID"

sleep 4

echo "--- status ---"
echo "backend_pid=$(cat "$BACKEND_PID") log=$BACKEND_LOG"
echo "frontend_pid=$(cat "$FRONTEND_PID") log=$FRONTEND_LOG"

echo "--- health ---"
curl -sS -w "\nHTTP_STATUS=%{http_code}\n" http://127.0.0.1:8000/health || true

echo "--- frontend ---"
curl -I -sS http://127.0.0.1:5173/ | head || true

echo
echo "OPEN: http://127.0.0.1:5173/"
echo "API:  http://127.0.0.1:8000/docs"
echo "=================================================="
