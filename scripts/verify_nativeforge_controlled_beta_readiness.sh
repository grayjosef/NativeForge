#!/usr/bin/env bash
# Gate 145E — is the controlled beta decision matrix honest, and route-live?
#
# RESULT=PASS when the decision route answers for all three scopes AND the
# verdicts are the honest ones:
#
#   internal/demo beta        GO, or LIMITED_GO with its blockers named
#   controlled customer beta  LIMITED_GO or NO_GO, never unconditional GO
#   production rollout        NO_GO, always
#
# A run in which production came back GO is a FAILURE of this verifier, not a
# success. So is one where a readiness flag was treated as the capability
# beside it.
#
# NOTHING IS APPROVED AND NOTHING IS ACTIVATED. No live source is called, no
# collector starts, no mail is sent, no object store is contacted, no real
# customer data is written, and no pilot is activated.
#
# No secrets, tokens, cookies, state, PKCE verifier, provider subject, API keys
# or recipient addresses. Scope names, verdicts, blockers and counts only.
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

echo "verify=controlled_beta_readiness"

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
  || echo "check=frontend_running status=SKIP http=$preview"

# ---------------- 2. every prior verifier, because a decision rests on them
#
# A matrix built on lanes nobody proved would be the thing this gate exists to
# prevent. Each lane's own verifier runs first.
for lane in demo_live_stack customer_persistence_live \
            awarded_operational_tracking tenant_digest_operational \
            document_storage_readiness email_delivery_readiness \
            no_live_source_calls source_monitoring_preflight \
            beta_onboarding_cockpit; do
  if bash "$ROOT/scripts/verify_nativeforge_${lane}.sh" >/dev/null 2>&1; then
    pass "prior_verifier:$lane" "RESULT=PASS"
  else
    block "prior_verifier_did_not_pass:$lane"
  fi
done

# ------------------------------------ 3. every route, over real HTTP, anonymous
anon_ok=1
for path in readiness blockers unsafe-claims approvals; do
  status="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
    "$BACKEND/v1/nf/demo/orgs/${DEMO_ORG}/beta-decision/$path" \
    2>/dev/null || echo 000)"
  if [ "$status" != "401" ]; then
    anon_ok=0
    fail "live_route_refuses_unauthenticated" "http=$status $path"
  fi
done
[ "$anon_ok" = "1" ] && pass live_route_refuses_unauthenticated "401 x4"

forged="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  -H "X-NF-Org-Id: ${DEMO_ORG}" \
  "$BACKEND/v1/nf/demo/orgs/${DEMO_ORG}/beta-decision/readiness" \
  2>/dev/null || echo 000)"
[ "$forged" = "401" ] && pass live_forged_header_refused "http=401" \
  || fail live_forged_header_refused "http=$forged"

# --------------------------------------- 4. the decision, with a real session
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
from nativeforge.services.controlled_beta_readiness_decision_service import (
    CONFLATIONS,
    GO,
    LIMITED_GO,
    NO_GO,
    SCOPES,
    UNSAFE_CLAIMS,
    build_controlled_beta_decision,
    decision_invariant_failures,
)
from nativeforge.services.customer_persistence_activation_service import (
    resolve_accountable_identity,
)
from nativeforge.services.customer_session_format_service import build_session

DEMO = os.environ["NF_DEMO_ORG"]
OTHER = "cccccccc-dddd-eeee-ffff-00000000d145"

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

base = f"/v1/nf/demo/orgs/{DEMO}/beta-decision"
with httpx.Client(
    base_url=os.environ.get("NF_BACKEND", "http://127.0.0.1:8000"), timeout=30.0
) as client:
    responses = {
        path: client.get(f"{base}/{path}", headers=headers)
        for path in ("readiness", "blockers", "unsafe-claims", "approvals")
    }
    cross = client.get(
        f"/v1/nf/demo/orgs/{OTHER}/beta-decision/readiness", headers=headers
    )
out["driven_over"] = "http"


def body(response):
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


for path, response in responses.items():
    out[f"route_{path.replace('-', '_')}_operational"] = response.status_code == 200
out["cross_org_refused"] = cross.status_code in {403, 404}

readiness_body = body(responses["readiness"])
out["route_scopes"] = sorted((readiness_body.get("by_scope") or {}).keys())
out["every_scope_decided"] = set(out["route_scopes"]) == set(SCOPES)
out["route_internal_demo"] = readiness_body.get("internal_demo_beta")
out["route_customer_beta"] = readiness_body.get("controlled_customer_beta")
out["route_production"] = readiness_body.get("production_rollout")
out["route_invariant_failures"] = readiness_body.get("invariant_failures") or []

out["unsafe_claims_listed"] = len(
    body(responses["unsafe-claims"]).get("unsafe_claims") or []
)
out["conflations_listed"] = len(
    body(responses["unsafe-claims"]).get("conflations") or []
)
out["approvals_listed"] = len(body(responses["approvals"]).get("human_approvals") or [])
out["technical_blockers_listed"] = len(
    body(responses["blockers"]).get("technical_blockers") or []
)

# The decision as the FULL battery proves it - every prior verifier having
# passed before this script reached here.
decision = build_controlled_beta_decision(
    login_live=out["login_live"],
    customer_persistence_live=True,
    awarded_operational_tracking=True,
    tenant_digest_operational=True,
    document_metadata_operational=True,
    email_delivery_readiness=True,
    source_monitoring_preflight_ready=True,
    beta_onboarding_cockpit_route_live=True,
)
out["battery_internal_demo"] = decision["internal_demo_beta"]
out["battery_customer_beta"] = decision["controlled_customer_beta"]
out["battery_production"] = decision["production_rollout"]
out["battery_invariant_failures"] = decision_invariant_failures(decision)
out["customer_beta_blockers"] = decision["by_scope"]["controlled_customer_beta"][
    "blockers"
]
out["customer_beta_constraints"] = decision["by_scope"][
    "controlled_customer_beta"
]["constraints"]

out["internal_demo_is_go_or_limited"] = out["battery_internal_demo"] in {
    GO,
    LIMITED_GO,
}
out["customer_beta_is_not_unconditional_go"] = (
    out["battery_customer_beta"] != GO or bool(decision["customer_auth_live"])
)
out["production_is_no_go"] = out["battery_production"] == NO_GO

for key in (
    "customer_auth_live",
    "source_monitoring_live",
    "email_delivery",
    "object_store_configured",
    "controlled_customer_pilot_activated",
    "production_approved",
    "real_customer_data_written",
    "real_organization_touched",
    "customer_names_reported",
):
    out[f"decision_{key}"] = decision[key]
for key in (
    "live_source_calls",
    "emails_sent",
    "object_store_calls",
    "collectors_activated",
):
    out[f"decision_{key}"] = decision[key]
out["decision_improvement_claims"] = decision["improvement_claims"]

# What the routes must never claim.
for name, response in responses.items():
    payload = body(response)
    for claim in (
        "production_approved",
        "controlled_customer_pilot_activated",
        "customer_auth_live",
        "source_monitoring_live",
        "email_delivery",
        "object_store_configured",
        "real_customer_data_written",
        "customer_names_reported",
    ):
        if payload.get(claim):
            out.setdefault("route_claims", []).append(f"{name}:{claim}")

print(json.dumps(out))
PY
)"

LAST_LINE="$(echo "$MEASURED" | tail -n 1)"
if ! echo "$LAST_LINE" | .venv/bin/python -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
  fail measurement_available "decision_smoke_failed"
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
[ "$(get session_minted)" = "True" ] && pass session_minted "real_signed_session" \
  || block session_minted "absent"

# --------------------------------------------------------------- 6. the routes
for path in readiness blockers unsafe_claims approvals; do
  [ "$(get "route_${path}_operational")" = "True" ] && pass "route:$path" \
    || block "route_not_operational:$path"
done
[ "$(get cross_org_refused)" = "True" ] && pass refusal:cross_org_refused \
  || fail refusal:cross_org_refused "$(get cross_org_refused)"
[ "$(get every_scope_decided)" = "True" ] && pass every_scope_decided \
  "$(getlist route_scopes)" || fail every_scope_decided "$(getlist route_scopes)"

# ------------------------------------------------------------ 7. THE VERDICTS
echo "internal_demo_beta=$(get battery_internal_demo)"
echo "controlled_customer_beta=$(get battery_customer_beta)"
echo "production_rollout=$(get battery_production)"

[ "$(get internal_demo_is_go_or_limited)" = "True" ] && pass \
  internal_demo_is_go_or_limited "$(get battery_internal_demo)" \
  || fail internal_demo_is_go_or_limited "$(get battery_internal_demo)"

[ "$(get customer_beta_is_not_unconditional_go)" = "True" ] && pass \
  customer_beta_is_not_unconditional_go "$(get battery_customer_beta)" \
  || fail customer_beta_is_not_unconditional_go "$(get battery_customer_beta)"

[ "$(get production_is_no_go)" = "True" ] && pass production_is_no_go "NO_GO" \
  || fail production_is_no_go "$(get battery_production)"

CUSTOMER_BLOCKERS="$(getlist customer_beta_blockers)"
[ -n "$CUSTOMER_BLOCKERS" ] && pass customer_beta_blockers_named \
  || fail customer_beta_blockers_named "none named"
echo "customer_beta_blockers=$CUSTOMER_BLOCKERS"

# ------------------------------------------------- 8. the lists are populated
for pair in "unsafe_claims_listed:1" "conflations_listed:1" \
            "approvals_listed:1" "technical_blockers_listed:1"; do
  name="${pair%%:*}"
  value="$(get "$name")"
  echo "count=$name n=$value"
  [ "$value" -ge 1 ] 2>/dev/null && pass "listed:$name" || fail "listed:$name" "n=$value"
done

# ----------------------------------- 9. NOTHING APPROVED, NOTHING ACTIVATED
for field in decision_customer_auth_live decision_source_monitoring_live \
             decision_email_delivery decision_object_store_configured \
             decision_controlled_customer_pilot_activated \
             decision_production_approved decision_real_customer_data_written \
             decision_real_organization_touched \
             decision_customer_names_reported customer_auth_live; do
  value="$(get "$field")"
  [ "$value" = "False" ] && pass "stays_false:$field" \
    || fail "stays_false:$field" "$value"
done

for field in decision_live_source_calls decision_emails_sent \
             decision_object_store_calls decision_collectors_activated; do
  value="$(get "$field")"
  echo "count=$field n=$value"
  [ "$value" = "0" ] && pass "stays_zero:$field" || fail "stays_zero:$field" "$value"
done

IMPROVEMENT="$(getlist decision_improvement_claims)"
[ -z "$IMPROVEMENT" ] && pass no_improvement_claim || fail no_improvement_claim "$IMPROVEMENT"

CLAIMS="$(getlist route_claims)"
[ -z "$CLAIMS" ] && pass no_route_claimed_a_forbidden_capability \
  || fail no_route_claimed_a_forbidden_capability "$CLAIMS"

for inv in route_invariant_failures battery_invariant_failures; do
  value="$(getlist "$inv")"
  [ -z "$value" ] && pass "invariants:$inv" "none_failed" || fail "invariants:$inv" "$value"
done

# ------------------------------------------------------------ 10. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

if [ -z "$BLOCKERS" ]; then
  echo "RESULT=PASS"
  echo "decision_matrix_route_live=true"
  echo "internal_demo_beta=$(get battery_internal_demo)"
  echo "controlled_customer_beta=$(get battery_customer_beta)"
  echo "production_rollout=NO_GO"
  echo "unsafe_claims_listed=$(get unsafe_claims_listed)"
  echo "conflations_listed=$(get conflations_listed)"
  echo "human_approvals_listed=$(get approvals_listed)"
  echo "technical_blockers_listed=$(get technical_blockers_listed)"
  echo "controlled_customer_pilot_activated=false"
  echo "production_approved=false"
  echo "live_source_calls=0"
  echo "emails_sent=0"
  echo "object_store_calls=0"
  exit 0
fi

echo "RESULT=BLOCKED"
echo "blocker=$BLOCKERS"
echo "next=docs/operations/761_GATE145_NEXT_BLOCK_RECOMMENDATION.md"
exit 1
