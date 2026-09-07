#!/usr/bin/env bash
# Gate 144F — is the cockpit route-live, and is what it shows honest?
#
# RESULT=PASS when the cockpit reports every lane, the operational lanes are
# operational, AND every forbidden lane is still false. Both halves matter: a
# cockpit that reported production ready would be a FAILURE of this verifier,
# not a success.
#
# It proves it by calling the routes: read the readiness summary, the next safe
# action, the blocker matrix and the capability matrix; then check that each
# false lane is present, named, and carries a blocker.
#
# NOTHING IS ACTIVATED. No live source is called, no collector starts, no mail
# is sent, no object store is contacted, and no lane's value changes.
#
# No secrets, tokens, cookies, state, PKCE verifier, provider subject, API keys
# or recipient addresses. Lane names, statuses, booleans and blocker names only.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

BACKEND="${NF_BACKEND_OVERRIDE:-http://127.0.0.1:8000}"
PREVIEW="${NF_PREVIEW_OVERRIDE:-http://127.0.0.1:5175}"
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

echo "verify=beta_onboarding_cockpit"

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

preview="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  "$PREVIEW/" 2>/dev/null || echo 000)"
[ "$preview" = "200" ] && pass frontend_running "http=200" \
  || echo "check=frontend_running status=SKIP http=$preview (route is backend-proved)"

# ------------------------------- 2. the lanes this cockpit reports on, proved
#
# Each lane's own verifier, run first. A cockpit that claimed a lane its
# verifier could not prove would be the thing this gate exists to prevent.
for lane in customer_persistence_live awarded_operational_tracking \
            tenant_digest_operational document_storage_readiness \
            email_delivery_readiness no_live_source_calls \
            source_monitoring_preflight; do
  if bash "$ROOT/scripts/verify_nativeforge_${lane}.sh" >/dev/null 2>&1; then
    pass "lane_verifier:$lane" "RESULT=PASS"
  else
    block "lane_verifier_did_not_pass:$lane"
  fi
done

# ------------------------------------ 3. every route, over real HTTP, anonymous
anon_ok=1
for path in \
  "/v1/nf/demo/orgs/${DEMO_ORG}/beta-cockpit/readiness" \
  "/v1/nf/demo/orgs/${DEMO_ORG}/beta-cockpit/next-actions" \
  "/v1/nf/demo/orgs/${DEMO_ORG}/beta-cockpit/blockers" \
  "/v1/nf/demo/orgs/${DEMO_ORG}/beta-cockpit/capabilities"
do
  status="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
    "$BACKEND$path" 2>/dev/null || echo 000)"
  if [ "$status" != "401" ]; then
    anon_ok=0
    fail "live_route_refuses_unauthenticated" "http=$status $path"
  fi
done
[ "$anon_ok" = "1" ] && pass live_route_refuses_unauthenticated "401 x4"

forged="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  -H "X-NF-Org-Id: ${DEMO_ORG}" \
  "$BACKEND/v1/nf/demo/orgs/${DEMO_ORG}/beta-cockpit/readiness" \
  2>/dev/null || echo 000)"
[ "$forged" = "401" ] && pass live_forged_header_refused "http=401" \
  || fail live_forged_header_refused "http=$forged"

# --------------------------------------- 4. the cockpit, with a real session
SESSION_JSON="$(curl -s --max-time "$TIMEOUT" "$BACKEND/api/auth/session" 2>/dev/null || true)"

MEASURED="$(
  NF_SESSION_JSON="$SESSION_JSON" NF_DEMO_ORG="$DEMO_ORG" NF_BACKEND="$BACKEND" \
    .venv/bin/python - <<'PY' 2>&1
import json
import os
import sys
import time
import uuid

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

from nativeforge.lib.settings import get_settings

_raw = getattr(get_settings(), "nf_session_signing_key", "") or ""
_key = (
    _raw.get_secret_value() if hasattr(_raw, "get_secret_value") else str(_raw)
).strip()
if _key and not os.environ.get("NF_SESSION_SIGNING_KEY"):
    os.environ["NF_SESSION_SIGNING_KEY"] = _key

from nativeforge.db.session import engine
from nativeforge.services.beta_onboarding_readiness_summary_service import (
    LANE_KEYS,
    NEVER_TRUE_LANES,
    summary_invariant_failures,
)
from nativeforge.services.customer_persistence_activation_service import (
    resolve_accountable_identity,
)
from nativeforge.services.customer_session_format_service import build_session

DEMO = os.environ["NF_DEMO_ORG"]
OTHER = "cccccccc-dddd-eeee-ffff-00000000d144"

with engine.connect() as connection:
    identity = resolve_accountable_identity(connection=connection, organization_id=DEMO)
out["accountable_identity_resolved"] = bool(identity)

headers = {}
if identity:
    issued = int(time.time())
    built = build_session(
        principal_id=identity,
        organization_id=DEMO,
        roles=["org_owner"],
        issued_at=issued,
        expires_at=issued + 900,
        auth_source="oidc_authorization_code",
        session_id=str(uuid.uuid4()),
        now=issued + 1,
    )
    if built["session_cookie_valid"]:
        headers = {"Cookie": f"nf_session={built['session_cookie_value']}"}
out["session_minted"] = bool(headers)

import httpx

base = f"/v1/nf/demo/orgs/{DEMO}/beta-cockpit"
with httpx.Client(
    base_url=os.environ.get("NF_BACKEND", "http://127.0.0.1:8000"), timeout=30.0
) as client:
    readiness = client.get(f"{base}/readiness", headers=headers)
    actions = client.get(f"{base}/next-actions", headers=headers)
    blockers = client.get(f"{base}/blockers", headers=headers)
    capabilities = client.get(f"{base}/capabilities", headers=headers)
    cross = client.get(
        f"/v1/nf/demo/orgs/{OTHER}/beta-cockpit/readiness", headers=headers
    )
out["driven_over"] = "http"


def body(response):
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


readiness_body = body(readiness)
out["readiness_route_operational"] = (
    readiness.status_code == 200 and "lanes" in readiness_body
)
out["next_actions_route_operational"] = (
    actions.status_code == 200 and "next_safe_action" in body(actions)
)
out["blockers_route_operational"] = (
    blockers.status_code == 200 and "blockers" in body(blockers)
)
out["capabilities_route_operational"] = (
    capabilities.status_code == 200 and "capabilities" in body(capabilities)
)
out["cross_org_refused"] = cross.status_code in {403, 404}

lanes = {lane["lane"]: lane for lane in (readiness_body.get("lanes") or [])}
out["lane_count"] = len(lanes)
out["expected_lane_count"] = len(LANE_KEYS)
out["every_lane_reported"] = set(lanes) == set(LANE_KEYS)
out["missing_lanes"] = sorted(set(LANE_KEYS) - set(lanes))
out["lane_status"] = {key: lane["status"] for key, lane in lanes.items()}
out["lane_value"] = {key: bool(lane["value"]) for key, lane in lanes.items()}
out["operational_lanes"] = list(readiness_body.get("operational_lanes") or [])

# Every forbidden lane must still be false AND must carry a blocker.
forbidden_true = [key for key in NEVER_TRUE_LANES if lanes.get(key, {}).get("value")]
out["forbidden_lanes_true"] = sorted(forbidden_true)
out["every_forbidden_lane_is_false"] = not forbidden_true
out["every_false_lane_names_a_blocker"] = all(
    lane["blockers"] for lane in lanes.values() if not lane["value"]
)
out["lanes_without_a_blocker"] = sorted(
    key
    for key, lane in lanes.items()
    if not lane["value"] and not lane["blockers"]
)

out["cockpit_invariant_failures"] = list(
    readiness_body.get("invariant_failures") or []
)

# What the routes must never claim.
for name, response in (
    ("readiness", readiness),
    ("next_actions", actions),
    ("blockers", blockers),
    ("capabilities", capabilities),
):
    payload = body(response)
    for claim in (
        "production_rollout",
        "controlled_customer_pilot",
        "customer_auth_live",
        "source_monitoring_live",
        "email_delivery",
        "object_store_configured",
        "verified_operational_binding",
        "real_organization_touched",
        "customer_names_reported",
    ):
        if payload.get(claim):
            out.setdefault("route_claims", []).append(f"{name}:{claim}")
    for counter in ("live_source_calls", "emails_sent", "object_store_calls",
                    "collectors_activated"):
        if payload.get(counter):
            out.setdefault("route_counters", []).append(
                f"{name}:{counter}={payload[counter]}"
            )

# The whole readiness payload, checked for a customer-shaped string.
rendered = json.dumps(readiness_body).lower()
out["names_a_customer"] = any(
    marker in rendered for marker in ("tribe", "@", "eligib", "deadline")
)

# The summary service's own invariants, computed independently of the route.
from nativeforge.services.beta_onboarding_readiness_summary_service import (
    build_beta_onboarding_summary,
)

local = build_beta_onboarding_summary(
    login_live=out["login_live"],
    customer_persistence_live=True,
    awarded_operational_tracking=True,
    tenant_digest_operational=True,
    document_metadata_operational=True,
    email_delivery_readiness=True,
    source_monitoring_preflight_ready=True,
)
out["summary_invariant_failures"] = summary_invariant_failures(local)
out["summary_operational_lanes"] = local["operational_lanes"]
for key in (
    "production_rollout",
    "controlled_customer_pilot",
    "customer_auth_live",
    "source_monitoring_live",
    "email_delivery",
    "object_store_configured",
    "verified_operational_binding",
):
    out[f"summary_{key}"] = local[key]

print(json.dumps(out))
PY
)"

LAST_LINE="$(echo "$MEASURED" | tail -n 1)"
if ! echo "$LAST_LINE" | .venv/bin/python -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
  fail measurement_available "cockpit_smoke_failed"
  echo "$MEASURED" | tail -n 6
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

# ------------------------------------------------------ 5. what must stay true
[ "$(get login_live)" = "True" ] && pass login_live "true" || block login_live "false"
[ "$(get accountable_identity_resolved)" = "True" ] && pass accountable_identity \
  "nf_org_memberships" || block accountable_identity "absent"
[ "$(get session_minted)" = "True" ] && pass session_minted "real_signed_session" \
  || block session_minted "absent"

# --------------------------------------------------------------- 6. the routes
for capability in readiness_route_operational next_actions_route_operational \
                  blockers_route_operational capabilities_route_operational; do
  [ "$(get "$capability")" = "True" ] && pass "capability:$capability" \
    || block "capability_not_proved:$capability"
done
[ "$(get cross_org_refused)" = "True" ] && pass refusal:cross_org_refused \
  || fail refusal:cross_org_refused "$(get cross_org_refused)"

# ---------------------------------------------------------------- 7. the lanes
echo "count=lanes n=$(get lane_count) expected=$(get expected_lane_count)"
[ "$(get every_lane_reported)" = "True" ] && pass every_lane_reported \
  || fail every_lane_reported "missing: $(getlist missing_lanes)"
echo "operational_lanes=$(getlist operational_lanes)"

[ "$(get every_false_lane_names_a_blocker)" = "True" ] && pass \
  every_false_lane_names_a_blocker \
  || fail every_false_lane_names_a_blocker "$(getlist lanes_without_a_blocker)"

# -------------------------------- 8. THE FORBIDDEN LANES ARE STILL FALSE
#
# A cockpit reporting any of these true is a failure of this verifier.
[ "$(get every_forbidden_lane_is_false)" = "True" ] && pass \
  every_forbidden_lane_is_false \
  || fail every_forbidden_lane_is_false "$(getlist forbidden_lanes_true)"

for field in summary_production_rollout summary_controlled_customer_pilot \
             summary_customer_auth_live summary_source_monitoring_live \
             summary_email_delivery summary_object_store_configured \
             summary_verified_operational_binding \
             customer_auth_live names_a_customer; do
  value="$(get "$field")"
  [ "$value" = "False" ] && pass "stays_false:$field" \
    || fail "stays_false:$field" "$value"
done

CLAIMS="$(getlist route_claims)"
[ -z "$CLAIMS" ] && pass no_route_claimed_a_forbidden_capability \
  || fail no_route_claimed_a_forbidden_capability "$CLAIMS"
COUNTERS="$(getlist route_counters)"
[ -z "$COUNTERS" ] && pass no_route_reported_an_activation \
  || fail no_route_reported_an_activation "$COUNTERS"

for inv in cockpit_invariant_failures summary_invariant_failures; do
  value="$(getlist "$inv")"
  [ -z "$value" ] && pass "invariants:$inv" "none_failed" || fail "invariants:$inv" "$value"
done

# ------------------------------------------------------------- 9. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

if [ -z "$BLOCKERS" ]; then
  echo "RESULT=PASS"
  echo "cockpit_foundation_route_live=true"
  echo "lanes_reported=$(get lane_count)"
  echo "operational_lanes=$(getlist summary_operational_lanes)"
  echo "customer_auth_live=false"
  echo "source_monitoring_live=false"
  echo "email_delivery=false"
  echo "object_store_configured=false"
  echo "controlled_customer_pilot=false"
  echo "production_rollout=false"
  echo "live_source_calls=0"
  echo "emails_sent=0"
  echo "object_store_calls=0"
  exit 0
fi

echo "RESULT=BLOCKED"
echo "blocker=$BLOCKERS"
echo "next=docs/operations/755_GATE144_BETA_ONBOARDING_READINESS_DELTA.md"
exit 1
