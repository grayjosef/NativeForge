#!/usr/bin/env bash
# Gate 138C — is org-scoped customer persistence actually live right now?
#
# RESULT=PASS only when customer_persistence_live is true. Anything else is
# RESULT=BLOCKED with the exact blocker named.
#
# It proves it by doing it: a fixture-labelled row into each of five lanes,
# read back BY ID anchored on organization_id, a cross-organization read that
# must return nothing, and an archive so nothing is left live. Five writes, and
# five archived rows afterwards.
#
# Fixture-labelled means `fact_status = demo_fixture` and `is_demo = true`,
# which is what makes `production_write` false in every repository underneath -
# so this needs neither customer_auth_live nor a verified operational binding,
# and claims neither.
#
# No real organization. No real customer data. No object store, and no document
# body: the document lane records a reference and object_store_configured stays
# false.
#
# No secrets. No tokens. No cookies. No state. No PKCE verifier. No provider
# subject. No email addresses. Counts, booleans and blocker names only.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

BACKEND="${NF_BACKEND_OVERRIDE:-http://127.0.0.1:8000}"
DEMO_ORG="${NF_DEMO_ORG_OVERRIDE:-bbbbbbbb-cccc-dddd-eeee-ffffffffffff}"
TIMEOUT=20

BLOCKERS=""
FAILED=""

pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
block() {
  echo "check=$1 status=BLOCKED ${2:-}"
  BLOCKERS="${BLOCKERS}${BLOCKERS:+,}$1"
}

echo "verify=customer_persistence_live"

# ------------------------------------------------------------- 1. backend up
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  "$BACKEND/backend/health" 2>/dev/null || echo 000)"
if [ "$code" = "200" ]; then
  pass backend_running "http=$code"
else
  fail backend_running "http=$code"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=backend_not_running"
  exit 1
fi

# ------------------------------------------- 2. the route path, unauthenticated
#
# One lane has routes. An unauthenticated call must 401, and a forged
# X-NF-Org-Id must not change that - Gates 134 and 135 removed the chain that
# would have let it.
route_path="/v1/nf/demo/orgs/${DEMO_ORG}/tribal-profile"
anon="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  "$BACKEND$route_path" 2>/dev/null || echo 000)"
forged="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  -H "X-NF-Org-Id: ${DEMO_ORG}" "$BACKEND$route_path" 2>/dev/null || echo 000)"

[ "$anon" = "401" ] && pass route_refuses_unauthenticated "http=401" \
  || fail route_refuses_unauthenticated "http=$anon"
[ "$forged" = "401" ] && pass forged_header_cannot_override "http=401" \
  || fail forged_header_cannot_override "http=$forged"

# ---------------------------------------------- 3. login_live and dev headers
LOGIN_JSON="$(curl -s --max-time "$TIMEOUT" "$BACKEND/api/auth/session" 2>/dev/null || true)"

MEASURED="$(
  NF_SESSION_JSON="$LOGIN_JSON" NF_DEMO_ORG="$DEMO_ORG" .venv/bin/python - <<'PY' 2>&1
import json
import os
import sys

sys.path.insert(0, "src")

out = {}
try:
    session = json.loads(os.environ.get("NF_SESSION_JSON") or "{}")
except ValueError:
    session = {}


def flag(name):
    if name in session:
        return session[name]
    return (session.get("activation_gate") or {}).get(name)


out["login_live"] = bool(flag("login_live"))
out["customer_auth_live"] = bool(flag("customer_auth_live"))

from nativeforge.db.session import engine
from nativeforge.services.customer_persistence_activation_service import (
    persistence_activation_invariant_failures,
    prove_customer_persistence,
)
from nativeforge.services.dev_org_header_shutdown_readiness_service import (
    build_dev_header_shutdown_readiness,
)
from nativeforge.lib.settings import get_settings

readiness = build_dev_header_shutdown_readiness()
out["dev_header_route_consumers"] = int(readiness["dev_header_used_by_routes"])
out["nf_dev_org_headers"] = bool(get_settings().nf_dev_org_headers)

# The round trip. A fresh seed per run, so this is re-runnable.
with engine.begin() as connection:
    proof = prove_customer_persistence(
        connection=connection, organization_id=os.environ["NF_DEMO_ORG"]
    )

for key in (
    "customer_persistence_live",
    "scope",
    "accountable_principal_available",
    "accountable_identity_resolved",
    "organization_is_demo",
    "rows_written",
    "rows_archived",
    "rows_left_live",
    "cross_org_rows_read",
    "object_store_contacted",
    "object_store_configured",
    "document_bodies_written",
    "real_customer_data_written",
    "real_organization_touched",
    "production_persistence_ready",
    "fact_status_written",
):
    out[key] = proof[key]

out["repository_live_lanes"] = list(proof["repository_persistence_live_lanes"])
out["route_live_lanes"] = list(proof["route_persistence_live_lanes"])
out["route_missing_lanes"] = list(proof["route_missing_lanes"])
out["blocked_lanes"] = list(proof["blocked_lanes"])
out["proof_blocked_reasons"] = list(proof["blocked_reasons"])
out["invariant_failures"] = persistence_activation_invariant_failures(proof)
out["lane_steps"] = {
    lane["lane"]: lane["steps"] for lane in proof["lane_results"]
}

print(json.dumps(out))
PY
)"

LAST_LINE="$(echo "$MEASURED" | tail -n 1)"
if ! echo "$LAST_LINE" | .venv/bin/python -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
  fail measurement_available "round_trip_probe_failed"
  echo "$MEASURED" | tail -n 5
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=measurement_unavailable"
  exit 1
fi
MEASURED="$LAST_LINE"
pass measurement_available

get() { echo "$MEASURED" | .venv/bin/python -c "import json,sys;print(json.load(sys.stdin).get('$1'))"; }
getlist() {
  echo "$MEASURED" | .venv/bin/python -c \
    "import json,sys;v=json.load(sys.stdin).get('$1') or [];print(' '.join(str(x) for x in v))"
}

LOGIN_LIVE="$(get login_live)"
AUTH_LIVE="$(get customer_auth_live)"
CONSUMERS="$(get dev_header_route_consumers)"
HEADERS_ON="$(get nf_dev_org_headers)"
PERSIST_LIVE="$(get customer_persistence_live)"
SCOPE="$(get scope)"
PRINCIPAL="$(get accountable_principal_available)"
IDENTITY="$(get accountable_identity_resolved)"
IS_DEMO="$(get organization_is_demo)"

[ "$LOGIN_LIVE" = "True" ] && pass login_live "true" || block login_live "false"
[ "$CONSUMERS" = "0" ] && pass dev_header_consumers_zero "n=0" \
  || block dev_header_consumers_zero "n=$CONSUMERS"
[ "$HEADERS_ON" = "False" ] && pass nf_dev_org_headers_false_safe "off" \
  || echo "check=nf_dev_org_headers_false_safe status=WARN on_but_no_route_reads_it"
[ "$PRINCIPAL" = "True" ] && pass accountable_principal "membership_row" \
  || block accountable_principal "absent"
[ "$IDENTITY" = "True" ] && pass accountable_identity_resolved "nf_org_memberships" \
  || block accountable_identity_resolved "absent"
[ "$IS_DEMO" = "True" ] && pass organization_is_demo "derived" \
  || block organization_is_demo "not_a_demo_organization"

# --------------------------------------------------------- 4. the round trip
echo "count=rows_written n=$(get rows_written)"
echo "count=rows_archived n=$(get rows_archived)"
echo "count=rows_left_live n=$(get rows_left_live)"
echo "count=cross_org_rows_read n=$(get cross_org_rows_read)"
echo "fact_status_written=$(get fact_status_written)"

for lane in $(getlist repository_live_lanes); do
  echo "lane=$lane repository=live"
done
for lane in $(getlist route_live_lanes); do
  echo "lane=$lane route=live"
done
for lane in $(getlist route_missing_lanes); do
  echo "lane=$lane route=MISSING"
done
for lane in $(getlist blocked_lanes); do
  block "lane_blocked:$lane"
done

[ "$(get cross_org_rows_read)" = "0" ] && pass cross_org_read_refused "n=0" \
  || fail cross_org_read_refused "n=$(get cross_org_rows_read)"
[ "$(get rows_left_live)" = "0" ] && pass cleanup_left_nothing_live "n=0" \
  || fail cleanup_left_nothing_live "n=$(get rows_left_live)"

# ------------------------------------------------------- 5. what stays false
for field in object_store_contacted object_store_configured \
             real_customer_data_written real_organization_touched \
             production_persistence_ready; do
  value="$(get "$field")"
  [ "$value" = "False" ] && pass "stays_false:$field" \
    || fail "stays_false:$field" "$value"
done
[ "$(get document_bodies_written)" = "0" ] && pass no_document_body_written "n=0" \
  || fail no_document_body_written "n=$(get document_bodies_written)"

INVARIANTS="$(getlist invariant_failures)"
if [ -z "$INVARIANTS" ]; then
  pass proof_invariants "none_failed"
else
  fail proof_invariants "$INVARIANTS"
fi

# ------------------------------------------------------------- 6. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

if [ "$PERSIST_LIVE" = "True" ] && [ -z "$BLOCKERS" ]; then
  echo "RESULT=PASS"
  echo "customer_persistence_live=true"
  echo "scope=$SCOPE"
  echo "customer_auth_live=$AUTH_LIVE"
  echo "customer_auth_live_not_required_because=a_fixture_labelled_write_is_not_a_production_write"
  echo "production_persistence_ready=false"
  echo "object_store_configured=false"
  exit 0
fi

echo "RESULT=BLOCKED"
echo "customer_persistence_live=$PERSIST_LIVE"
if [ -n "$BLOCKERS" ]; then
  echo "blocker=$BLOCKERS"
else
  echo "blocker=$(getlist proof_blocked_reasons)"
fi
echo "next=docs/operations/724_GATE138_ORG_SCOPED_CUSTOMER_PERSISTENCE.md"
exit 1
