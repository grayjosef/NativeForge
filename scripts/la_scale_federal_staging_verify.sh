#!/usr/bin/env bash
# LA block: scale federal activation staging verify-live (AC-1 through AC-6).
set -euo pipefail
cd "$(dirname "$0")/.."

export NF_APP_ENV=staging
export NF_DEV_ORG_HEADERS=true
export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./nativeforge.local.db}"
export NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true
export NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED=true

ORG=bbbbbbbb-cccc-dddd-eeee-ffffffffffff
BASE=http://127.0.0.1:18080
PORT=18080
CONFIRM='{"operator_handle":"la-staging-operator","human_activation_acknowledged":true,"public_only_acknowledged":true,"batch_tier1_public_activation_acknowledged":true}'
BATCH_QS="nf_live_source_ingestion=true&nf_real_resolver_validation=true"

echo "=== LA-0: DB active federal count ==="
uv run python scripts/la0_federal_active_count.py

echo ""
echo "=== Setup: migrate + seed org ==="
uv run alembic upgrade head
uv run python scripts/seed_m0_demo_data.py

wait_for_server() {
  for _ in $(seq 1 40); do
    if curl -sf "$BASE/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  echo "server not ready on $BASE" >&2
  return 1
}

uv run uvicorn nativeforge.main:app --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
wait_for_server

echo ""
echo "=== AC-1: missing batch_tier1_public_activation_acknowledged => 422 ==="
curl -s -w "\nHTTP %{http_code}\n" -X POST \
  "$BASE/v1/nf/demo/orgs/$ORG/discovery/source-ingestion/tier1-batch-live-pull?$BATCH_QS" \
  -H "X-NF-Org-Id: $ORG" -H "Content-Type: application/json" \
  -d '{"operator_handle":"x","human_activation_acknowledged":true,"public_only_acknowledged":true}'

echo ""
echo "=== AC-5 HARD GATE: engage kill switch => batch 403 ==="
curl -s -X POST \
  "$BASE/v1/nf/demo/orgs/$ORG/operator/activation/governed-action" \
  -H "X-NF-Org-Id: $ORG" -H "X-NF-Actor-Role: operator" \
  -H "Content-Type: application/json" \
  -d '{"governed_action":"activation:toggle","toggle":"kill_switch","value":true}' \
  | uv run python -m json.tool

curl -s -w "\nHTTP %{http_code}\n" -X POST \
  "$BASE/v1/nf/demo/orgs/$ORG/discovery/source-ingestion/tier1-batch-live-pull?$BATCH_QS" \
  -H "X-NF-Org-Id: $ORG" -H "Content-Type: application/json" \
  -d "$CONFIRM"

echo ""
echo "=== Release kill switch + enable live publish for cohort ==="
curl -s -X POST \
  "$BASE/v1/nf/demo/orgs/$ORG/operator/activation/governed-action" \
  -H "X-NF-Org-Id: $ORG" -H "X-NF-Actor-Role: operator" \
  -H "Content-Type: application/json" \
  -d '{"governed_action":"activation:toggle","toggle":"kill_switch","value":false}' \
  | uv run python -m json.tool

curl -s -X POST \
  "$BASE/v1/nf/demo/orgs/$ORG/operator/activation/governed-action" \
  -H "X-NF-Org-Id: $ORG" -H "X-NF-Actor-Role: operator" \
  -H "Content-Type: application/json" \
  -d '{"governed_action":"activation:toggle","toggle":"live_publish","value":true,"reason":"LA block staging cohort activation."}' \
  | uv run python -m json.tool

echo ""
echo "=== AC-2/5: LA-5 cohort activation — 3 batches of 20 (live Grants.gov) ==="
for OFFSET in 0 20 40; do
  echo "--- batch_offset=$OFFSET max_batch_size=20 ---"
  curl -s -X POST \
    "$BASE/v1/nf/demo/orgs/$ORG/discovery/source-ingestion/tier1-batch-live-pull?$BATCH_QS&batch_offset=$OFFSET&max_batch_size=20" \
    -H "X-NF-Org-Id: $ORG" -H "Content-Type: application/json" \
    -d "$CONFIRM" \
    | uv run python -c "import sys,json; d=json.load(sys.stdin); print(json.dumps({'batch_offset':d.get('batch_offset'),'batch_size':d.get('batch_size'),'sources_activated':d.get('sources_activated'),'real_grants_ingested':d.get('real_grants_ingested'),'empty_nofo':len(d.get('empty_nofo_sources') or []),'corpus_grant_count':(d.get('corpus_persist') or {}).get('grant_count'),'skipped_dupes':(d.get('corpus_persist') or {}).get('skipped_duplicate_count')}, indent=2))"
done

echo ""
echo "=== AC-3: re-run batch 0 (dedup skip expected) ==="
curl -s -X POST \
  "$BASE/v1/nf/demo/orgs/$ORG/discovery/source-ingestion/tier1-batch-live-pull?$BATCH_QS&batch_offset=0&max_batch_size=20" \
  -H "X-NF-Org-Id: $ORG" -H "Content-Type: application/json" \
  -d "$CONFIRM" \
  | uv run python -c "import sys,json; d=json.load(sys.stdin); cp=d.get('corpus_persist') or {}; print('skipped_duplicate_count', cp.get('skipped_duplicate_count')); print('inserted_count', cp.get('inserted_count'))"

echo ""
echo "=== LA-0 post-activation count ==="
uv run python scripts/la0_federal_active_count.py

echo ""
echo "=== AC-2: classify + match scaled corpus ==="
uv run python -c "
from nativeforge.services.la_scaled_classify_match_orchestrator_service import run_la_scaled_classify_match_block
import json
r = run_la_scaled_classify_match_block()
print(json.dumps({'grant_count': r['grant_count'], 'all_needs_operator_review': r['all_needs_operator_review'], 'match_labels': r['classify_match']['match_label_distribution']}, indent=2))
"

echo ""
echo "=== AC-4: scale honesty regression ==="
uv run python -c "
from nativeforge.services.la_scale_honesty_regression_service import run_la_scale_honesty_regression
import json
r = run_la_scale_honesty_regression()
print(json.dumps(r, indent=2))
"

echo ""
echo "=== LA STAGING VERIFY COMPLETE ==="
