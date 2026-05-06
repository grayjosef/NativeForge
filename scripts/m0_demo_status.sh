#!/usr/bin/env bash
set -u

ROOT="/home/josefgray/projects/nativeforge"
RUN_DIR="$ROOT/.run"
LOG_DIR="$ROOT/logs"
BACKEND_PID="$RUN_DIR/m0_backend.pid"
FRONTEND_PID="$RUN_DIR/m0_frontend.pid"

echo "================ NATIVEFORGE M0 STATUS ================"

if [ -f "$BACKEND_PID" ] && kill -0 "$(cat "$BACKEND_PID")" 2>/dev/null; then
  echo "backend: running pid=$(cat "$BACKEND_PID")"
else
  echo "backend: not running"
fi

if [ -f "$FRONTEND_PID" ] && kill -0 "$(cat "$FRONTEND_PID")" 2>/dev/null; then
  echo "frontend: running pid=$(cat "$FRONTEND_PID")"
else
  echo "frontend: not running"
fi

echo
echo "--- health ---"
curl -sS -w "\nHTTP_STATUS=%{http_code}\n" http://127.0.0.1:8000/health || true

echo
echo "--- trust manifest demo ---"
curl -sS -w "\nHTTP_STATUS=%{http_code}\n" \
  -H "X-NF-Org-Id: bbbbbbbb-cccc-dddd-eeee-ffffffffffff" \
  "http://127.0.0.1:8000/v1/nf/demo/orgs/bbbbbbbb-cccc-dddd-eeee-ffffffffffff/trust/manifest" | head -c 1600 || true
echo

echo
echo "--- logs ---"
echo "backend:  $LOG_DIR/m0_backend.log"
echo "frontend: $LOG_DIR/m0_frontend.log"
echo "open:     http://127.0.0.1:5173/"
echo "docs:     http://127.0.0.1:8000/docs"
echo "======================================================"
