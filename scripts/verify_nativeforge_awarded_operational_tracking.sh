#!/usr/bin/env bash
# Gate 139G — are the four post-award lanes actually operational right now?
#
# RESULT=PASS only when awarded_operational_tracking is true. Anything else is
# RESULT=BLOCKED with the exact blocker named.
#
# It proves it by calling the routes: create an award, attach a requirement,
# attach a proof event, attach a document REFERENCE, read every one back
# anchored on organization_id, call the same reads as another organization and
# get nothing, then archive all four in reverse dependency order.
#
# The session is real. It is minted through `customer_session_format_service`
# for the demo organization's existing owner identity, read out of
# `nf_org_memberships` - the same chain a browser login produces, and the same
# one Gate 138's foreign key forced when a synthetic id was refused. No fake
# user, no fake session, no fake membership.
#
# Every row is fixture-labelled and archived. No object store is contacted, no
# document body is written, no live source is called, no email is sent, and the
# real organization is never addressed.
#
# No secrets. No tokens. No cookies. No state. No PKCE verifier. No provider
# subject. Counts, booleans and blocker names only.
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

echo "verify=awarded_operational_tracking"

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

# ------------------------------------ 2. the four routes, over real HTTP, anon
#
# Against the running server, not a test client: these must fail closed for
# anybody on the network, which is a different claim from failing closed in a
# process that imported the app.
anon_ok=1
for path in \
  "/v1/nf/demo/orgs/${DEMO_ORG}/awarded-grants" \
  "/v1/nf/demo/orgs/${DEMO_ORG}/awarded-grants/00000000-0000-0000-0000-000000000139/requirements" \
  "/v1/nf/demo/orgs/${DEMO_ORG}/requirements/00000000-0000-0000-0000-000000000139/proof-events" \
  "/v1/nf/demo/orgs/${DEMO_ORG}/awarded-grants/00000000-0000-0000-0000-000000000139/documents"
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
  "$BACKEND/v1/nf/demo/orgs/${DEMO_ORG}/awarded-grants" 2>/dev/null || echo 000)"
[ "$forged" = "401" ] && pass live_forged_header_refused "http=401" \
  || fail live_forged_header_refused "http=$forged"

# --------------------------------------- 3. the smoke, with a real session
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

# `.env` reaches pydantic Settings and never `os.environ` - the rule this
# campaign settled in Gate 130. `customer_session_format_service` reads the key
# from the environment, so a process that only has Settings can SIGN a session
# and cannot VERIFY one: the first run minted a valid cookie and the app
# refused it with `no_signing_key_available_so_nothing_can_be_verified`.
#
# Read through Settings, placed in this process's own environment, never
# printed. The running server already has it via systemd EnvironmentFile.
_raw = getattr(get_settings(), "nf_session_signing_key", "") or ""
# A pydantic SecretStr, so the value is never repr'd by accident.
_key = (
    _raw.get_secret_value() if hasattr(_raw, "get_secret_value") else str(_raw)
).strip()
if _key and not os.environ.get("NF_SESSION_SIGNING_KEY"):
    os.environ["NF_SESSION_SIGNING_KEY"] = _key

from nativeforge.db.session import engine
from nativeforge.services.awarded_operational_route_smoke_service import (
    route_smoke_invariant_failures,
    run_post_award_route_smoke,
)
from nativeforge.services.awarded_operational_tracking_readiness_service import (
    awarded_readiness_invariant_failures,
    build_awarded_operational_readiness,
)
from nativeforge.services.customer_persistence_activation_service import (
    prove_customer_persistence,
    resolve_accountable_identity,
)
from nativeforge.services.customer_session_format_service import build_session

DEMO = os.environ["NF_DEMO_ORG"]
OTHER = "cccccccc-dddd-eeee-ffff-00000000d139"

# Gate 138's round trip, so the readiness roll-up has a repository proof that
# was measured rather than assumed.
with engine.begin() as connection:
    persistence = prove_customer_persistence(
        connection=connection, organization_id=DEMO
    )
out["customer_persistence_live"] = bool(persistence["customer_persistence_live"])
out["persistence_rows_left_live"] = int(persistence["rows_left_live"])

# The session: a real one, for the organization's real owner.
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
    else:
        out["session_blocked_reasons"] = list(built["blocked_reasons"])
out["session_minted"] = bool(headers)

# Real HTTP against the running server, not an in-process client: that the
# server serves these routes is a stronger claim than that a process which
# imported the app does.
import httpx

with httpx.Client(
    base_url=os.environ.get("NF_BACKEND", "http://127.0.0.1:8000"), timeout=20.0
) as client:
    smoke = run_post_award_route_smoke(
        client=client,
        organization_id=DEMO,
        other_organization_id=OTHER,
        session_headers=headers,
    )
out["driven_over"] = "http"

readiness = build_awarded_operational_readiness(
    route_smoke=smoke, repository_proof=persistence
)

for key in (
    "end_to_end_proved",
    "forged_header_refused",
    "document_body_refused",
    "caller_relabel_refused",
    "unsupported_requirement_stayed_unresolved",
    "object_store_contacted",
    "document_body_written",
    "live_source_called",
    "email_sent",
):
    out[key] = smoke[key]
out["route_operational_lanes"] = list(smoke["route_operational_lanes"])
out["smoke_blocked_lanes"] = list(smoke["blocked_lanes"])
out["smoke_invariant_failures"] = route_smoke_invariant_failures(smoke)
out["lane_detail"] = {
    lane: {k: v for k, v in facts.items() if k != "blocked_reasons"}
    for lane, facts in smoke["lanes"].items()
}
out["lane_blocked_reasons"] = {
    lane: facts["blocked_reasons"]
    for lane, facts in smoke["lanes"].items()
    if facts["blocked_reasons"]
}

for key in (
    "awarded_operational_tracking",
    "scope",
    "object_store_configured",
    "document_body_storage_ready",
    "production_awarded_tracking",
    "verified_operational_binding",
):
    out[key] = readiness[key]
out["readiness_route_live_lanes"] = list(readiness["route_live_lanes"])
out["readiness_repository_live_lanes"] = list(readiness["repository_live_lanes"])
out["readiness_blocked_lanes"] = list(readiness["blocked_lanes"])
out["readiness_blocked_reasons"] = list(readiness["blocked_reasons"])
out["readiness_invariant_failures"] = awarded_readiness_invariant_failures(readiness)

print(json.dumps(out))
PY
)"

LAST_LINE="$(echo "$MEASURED" | tail -n 1)"
if ! echo "$LAST_LINE" | .venv/bin/python -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
  fail measurement_available "route_smoke_failed"
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

TRACKING="$(get awarded_operational_tracking)"
SCOPE="$(get scope)"

[ "$(get login_live)" = "True" ] && pass login_live "true" || block login_live "false"
[ "$(get customer_persistence_live)" = "True" ] && pass customer_persistence_live "true" \
  || block customer_persistence_live "false"
[ "$(get accountable_identity_resolved)" = "True" ] && pass accountable_identity "nf_org_memberships" \
  || block accountable_identity "absent"
[ "$(get session_minted)" = "True" ] && pass session_minted "real_signed_session" \
  || block session_minted "$(getlist session_blocked_reasons)"

# ---------------------------------------------------------------- 4. the lanes
for lane in $(getlist route_operational_lanes); do
  echo "lane=$lane route=operational"
done
for lane in $(getlist smoke_blocked_lanes); do
  block "lane_not_operational:$lane"
done

[ "$(get end_to_end_proved)" = "True" ] && pass end_to_end_post_award_smoke "four_lanes" \
  || block end_to_end_post_award_smoke "did_not_complete"

# ------------------------------------------------------------ 5. the refusals
for refusal in forged_header_refused document_body_refused caller_relabel_refused \
               unsupported_requirement_stayed_unresolved; do
  [ "$(get "$refusal")" = "True" ] && pass "refusal:$refusal" \
    || fail "refusal:$refusal" "$(get "$refusal")"
done

# ------------------------------------------------------- 6. what stays false
for field in object_store_contacted document_body_written live_source_called \
             email_sent object_store_configured document_body_storage_ready \
             production_awarded_tracking verified_operational_binding; do
  value="$(get "$field")"
  [ "$value" = "False" ] && pass "stays_false:$field" \
    || fail "stays_false:$field" "$value"
done

echo "count=persistence_rows_left_live n=$(get persistence_rows_left_live)"
[ "$(get persistence_rows_left_live)" = "0" ] && pass persistence_cleanup_left_nothing \
  || fail persistence_cleanup_left_nothing "n=$(get persistence_rows_left_live)"

SMOKE_INV="$(getlist smoke_invariant_failures)"
READY_INV="$(getlist readiness_invariant_failures)"
[ -z "$SMOKE_INV" ] && pass smoke_invariants "none_failed" || fail smoke_invariants "$SMOKE_INV"
[ -z "$READY_INV" ] && pass readiness_invariants "none_failed" \
  || fail readiness_invariants "$READY_INV"

# ------------------------------------------------------------- 7. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

if [ "$TRACKING" = "True" ] && [ -z "$BLOCKERS" ]; then
  echo "RESULT=PASS"
  echo "awarded_operational_tracking=true"
  echo "scope=$SCOPE"
  echo "route_live_lanes=$(getlist readiness_route_live_lanes)"
  echo "customer_auth_live=$(get customer_auth_live)"
  echo "production_awarded_tracking=false"
  echo "object_store_configured=false"
  echo "document_body_storage_ready=false"
  exit 0
fi

echo "RESULT=BLOCKED"
echo "awarded_operational_tracking=$TRACKING"
if [ -n "$BLOCKERS" ]; then
  echo "blocker=$BLOCKERS"
else
  echo "blocker=$(getlist readiness_blocked_reasons)"
fi
echo "next=docs/operations/731_GATE139_AWARDED_READINESS_DELTA.md"
exit 1
