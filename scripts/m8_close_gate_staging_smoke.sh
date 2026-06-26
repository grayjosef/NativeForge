#!/usr/bin/env bash
# M8 close-gate live staging smoke (verify-live output for operator review).
set -euo pipefail
cd "$(dirname "$0")/.."

SMOKE_DB="/tmp/nf_m8_close_gate.sqlite3"
rm -f "$SMOKE_DB"
export DATABASE_URL="sqlite+pysqlite:///${SMOKE_DB}"
export NF_DEV_ORG_HEADERS=true
export NF_APP_ENV=staging
ORG=bbbbbbbb-cccc-dddd-eeee-ffffffffffff
BASE=http://127.0.0.1:18765
PORT=18765

.venv/bin/alembic upgrade head
.venv/bin/python -c "
import uuid
from nativeforge.db.session import SessionLocal
from nativeforge.db.models import Organization
oid = uuid.UUID('${ORG}')
with SessionLocal() as s:
    s.add(Organization(id=oid, org_type='demo'))
    s.commit()
"

wait_for_server() {
  for _ in $(seq 1 30); do
    if curl -sf "$BASE/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.2
  done
  echo "server not ready on $BASE" >&2
  return 1
}

.venv/bin/uvicorn nativeforge.main:app --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
wait_for_server

echo "=== 1. Fresh activation state (defaults OFF) ==="
curl -s "$BASE/v1/nf/demo/orgs/$ORG/operator/activation" \
  -H "X-NF-Org-Id: $ORG" | .venv/bin/python -m json.tool

echo ""
echo "=== 2. Header-auth: NF_DEV_ORG_HEADERS=false (operator header NOT honored) ==="
kill $SERVER_PID
wait $SERVER_PID 2>/dev/null || true
export NF_DEV_ORG_HEADERS=false
.venv/bin/uvicorn nativeforge.main:app --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!
wait_for_server
curl -s -w "\nHTTP %{http_code}\n" -X POST \
  "$BASE/v1/nf/demo/orgs/$ORG/operator/activation/governed-action" \
  -H "X-NF-Org-Id: $ORG" -H "X-NF-Actor-Role: operator" \
  -H "Content-Type: application/json" \
  -d '{"governed_action":"activation:toggle","toggle":"kill_switch","value":true}'

kill $SERVER_PID
wait $SERVER_PID 2>/dev/null || true
export NF_DEV_ORG_HEADERS=true
.venv/bin/uvicorn nativeforge.main:app --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!
wait_for_server

echo ""
echo "=== 3a. Agent => 403 ==="
curl -s -w "\nHTTP %{http_code}\n" -X POST \
  "$BASE/v1/nf/demo/orgs/$ORG/operator/activation/governed-action" \
  -H "X-NF-Org-Id: $ORG" -H "X-NF-Actor-Role: agent" \
  -H "Content-Type: application/json" \
  -d '{"governed_action":"activation:toggle","toggle":"live_attribution","value":true}'

echo ""
echo "=== 3b. Live publish no reason => 400 ==="
curl -s -w "\nHTTP %{http_code}\n" -X POST \
  "$BASE/v1/nf/demo/orgs/$ORG/operator/activation/governed-action" \
  -H "X-NF-Org-Id: $ORG" -H "X-NF-Actor-Role: operator" \
  -H "Content-Type: application/json" \
  -d '{"governed_action":"activation:toggle","toggle":"live_publish","value":true}'

echo ""
echo "=== 3c. Live publish + reason => 200 ==="
curl -s -X POST \
  "$BASE/v1/nf/demo/orgs/$ORG/operator/activation/governed-action" \
  -H "X-NF-Org-Id: $ORG" -H "X-NF-Actor-Role: operator" \
  -H "Content-Type: application/json" \
  -d '{"governed_action":"activation:toggle","toggle":"live_publish","value":true,"reason":"M8 close-gate staging smoke."}' \
  | .venv/bin/python -m json.tool

echo ""
echo "=== 3d. policy:change auto_publish => version 1 ==="
curl -s -X POST \
  "$BASE/v1/nf/demo/orgs/$ORG/operator/activation/governed-action" \
  -H "X-NF-Org-Id: $ORG" -H "X-NF-Actor-Role: admin" \
  -H "Content-Type: application/json" \
  -d '{"governed_action":"policy:change","toggle":"auto_publish","value":true,"reason":"M8 auto-publish enable.","config_payload":{"max_batch":5}}' \
  | .venv/bin/python -m json.tool

echo ""
echo "=== 3e. Engage kill switch ==="
curl -s -X POST \
  "$BASE/v1/nf/demo/orgs/$ORG/operator/activation/governed-action" \
  -H "X-NF-Org-Id: $ORG" -H "X-NF-Actor-Role: operator" \
  -H "Content-Type: application/json" \
  -d '{"governed_action":"activation:toggle","toggle":"kill_switch","value":true}' \
  | .venv/bin/python -m json.tool

echo ""
echo "=== 3f. verify-live: publish + auto-publish queue HALTED ==="
curl -s -X POST "$BASE/v1/nf/demo/orgs/$ORG/operator/activation/verify-live" \
  -H "X-NF-Org-Id: $ORG" | .venv/bin/python -m json.tool

echo ""
echo "=== M8 STAGING SMOKE COMPLETE ==="
