#!/usr/bin/env bash
# SH block: seed catalog hygiene staging verify (AC-1 through AC-5).
set -euo pipefail
cd "$(dirname "$0")/.."

export NF_APP_ENV=staging
export NF_DEV_ORG_HEADERS=true
export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./nativeforge.sh_hygiene.db}"
export NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true
export NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED=true

ORG=bbbbbbbb-cccc-dddd-eeee-ffffffffffff
BASE=http://127.0.0.1:18081
PORT=18081
BIA_SEEDS='["nf-seed-2026-fed-001","nf-seed-2026-fed-003","nf-seed-2026-fed-004"]'

rm -f nativeforge.sh_hygiene.db
uv run alembic upgrade head
uv run python scripts/seed_m0_demo_data.py

echo "=== AC-1: reconciliation report ==="
uv run python scripts/seed_catalog_hygiene_report.py | uv run python -c "
import sys,json
r=json.load(sys.stdin)
print(r['reconciliation']['reconciliation_equation'])
print('nothing_silently_dropped', r['reconciliation']['nothing_silently_dropped'])
"

wait_for_server() {
  for _ in $(seq 1 40); do
    curl -sf "$BASE/health" >/dev/null 2>&1 && return 0
    sleep 0.25
  done
  return 1
}

uv run uvicorn nativeforge.main:app --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
wait_for_server

echo ""
echo "=== Enable live publish ==="
curl -s -X POST \
  "$BASE/v1/nf/demo/orgs/$ORG/operator/activation/governed-action" \
  -H "X-NF-Org-Id: $ORG" -H "X-NF-Actor-Role: operator" \
  -H "Content-Type: application/json" \
  -d '{"governed_action":"activation:toggle","toggle":"live_publish","value":true,"reason":"SH staging BIA identity-key proof."}' \
  >/dev/null

CONFIRM='{"operator_handle":"sh-staging","human_activation_acknowledged":true,"public_only_acknowledged":true,"batch_tier1_public_activation_acknowledged":true}'

echo ""
echo "=== AC-2: BIA shared URL → 3 distinct active registry rows ==="
uv run python << PY
import json, uuid
org = "$ORG"
confirm = json.loads('''$CONFIRM''')
seeds = json.loads('''$BIA_SEEDS''')
from nativeforge.db.session import SessionLocal
from nativeforge.db.models import Organization
from nativeforge.services.tier1_batch_federal_activation_service import activate_tier1_public_batch_human_gate
from nativeforge.repositories import opportunity_sources as os_repo
oid = uuid.UUID(org)
with SessionLocal() as s:
    org_row = s.get(Organization, oid)
    result = activate_tier1_public_batch_human_gate(s, org=org_row, seed_ids=seeds, operator_confirmation=confirm)
    rows = os_repo.list_opportunity_sources_for_org(session=s, org_id=oid, org_type="demo")
    active = [r for r in rows if r.is_active and r.seed_id in seeds]
    proof = {
        "activated_count": result["activated_count"],
        "active_bia_rows": len(active),
        "distinct_ids": len({str(r.id) for r in active}),
        "seed_ids": [r.seed_id for r in active],
        "shared_url": active[0].source_url if active else None,
    }
    s.commit()
print(json.dumps(proof, indent=2))
assert proof["active_bia_rows"] == 3
assert proof["distinct_ids"] == 3
PY

echo ""
echo "=== AC-3: fed-023 login in seed bundle ==="
uv run python -c "
from nativeforge.services.source_ingestion_seed_loader_service import build_source_seed_candidate_bundle
fed023 = next(c for c in build_source_seed_candidate_bundle()['candidates'] if c['seed_id']=='nf-seed-2026-fed-023')
print('access_posture_hint', fed023['access_posture_hint'])
print('catalog_accounting_bucket', fed023['catalog_accounting_bucket'])
print('source_health_status', fed023['source_health_status'])
"

echo ""
echo "=== AC-4: honesty regression (scaled corpus) ==="
uv run python -c "
from nativeforge.services.la_scale_honesty_regression_service import run_la_scale_honesty_regression
import json
print(json.dumps({'verification_passed': run_la_scale_honesty_regression()['verification_passed']}))
"

echo ""
echo "=== AC-5: stash preserved ==="
git stash list | head -1

echo ""
echo "=== SH STAGING VERIFY COMPLETE ==="
