#!/usr/bin/env bash
set -u

ROOT="/home/josefgray/projects/nativeforge"
RUN_DIR="$ROOT/.run"
BACKEND_PID="$RUN_DIR/m0_backend.pid"
FRONTEND_PID="$RUN_DIR/m0_frontend.pid"

echo "================ NATIVEFORGE M0 DOWN ================"

if [ -f "$BACKEND_PID" ]; then
  PID="$(cat "$BACKEND_PID")"
  if kill -0 "$PID" 2>/dev/null; then
    echo "stopping backend pid=$PID"
    kill "$PID" 2>/dev/null || true
  else
    echo "backend pid not running: $PID"
  fi
  rm -f "$BACKEND_PID"
else
  echo "no backend pid file"
fi

if [ -f "$FRONTEND_PID" ]; then
  PID="$(cat "$FRONTEND_PID")"
  if kill -0 "$PID" 2>/dev/null; then
    echo "stopping frontend pid=$PID"
    kill "$PID" 2>/dev/null || true
  else
    echo "frontend pid not running: $PID"
  fi
  rm -f "$FRONTEND_PID"
else
  echo "no frontend pid file"
fi

echo "done"
echo "====================================================="
