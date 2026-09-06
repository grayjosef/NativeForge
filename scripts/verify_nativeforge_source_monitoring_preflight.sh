#!/usr/bin/env bash
# Gate 143F — can this system evaluate every source without calling one?
#
# RESULT=PASS when source_monitoring_preflight_ready is true for
# controlled_dev_demo AND source_monitoring_live is false. Both halves matter: a
# run in which monitoring had actually started is a FAILURE of this verifier.
#
# It proves it by calling the routes: read readiness, read the blockers by
# class, put a real registry source on the watchlist, evaluate it, and be
# refused for a source the organization does not watch. Then it checks the
# refusals: an unknown id, a terms-blocked source, a human-review-only source,
# and a source needing a credential nobody has.
#
# NO LIVE SOURCE IS CALLED. No robots.txt is fetched, no DNS is resolved, no
# collector is started. Every response is checked for those claims and this
# script fails if any of them changes.
#
# NO API KEY IS PRINTED. No secrets, tokens, cookies, state, PKCE verifier or
# provider subject. Source ids, states, counts, booleans and blocker names only.
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

echo "verify=source_monitoring_preflight"

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

# ------------------------------------------- 2. the no-live-call guard first
#
# Before anything else: if a live path were active, nothing below would be
# worth measuring.
if bash "$ROOT/scripts/verify_nativeforge_no_live_source_calls.sh" >/dev/null 2>&1; then
  pass no_live_source_call_guard "RESULT=PASS"
else
  fail no_live_source_call_guard "the guard did not pass"
fi

# ------------------------------------- 3. every route, over real HTTP, anon
anon_ok=1
for spec in \
  "GET /v1/nf/demo/orgs/${DEMO_ORG}/source-monitoring/readiness" \
  "GET /v1/nf/demo/orgs/${DEMO_ORG}/source-monitoring/blockers" \
  "POST /v1/nf/demo/orgs/${DEMO_ORG}/source-monitoring/evaluate"
do
  method="${spec%% *}"
  path="${spec#* }"
  status="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
    -X "$method" -H 'Content-Type: application/json' -d '{}' \
    "$BACKEND$path" 2>/dev/null || echo 000)"
  if [ "$status" != "401" ]; then
    anon_ok=0
    fail "live_route_refuses_unauthenticated" "http=$status $method $path"
  fi
done
[ "$anon_ok" = "1" ] && pass live_route_refuses_unauthenticated "401 x3"

forged="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  -H "X-NF-Org-Id: ${DEMO_ORG}" \
  "$BACKEND/v1/nf/demo/orgs/${DEMO_ORG}/source-monitoring/readiness" \
  2>/dev/null || echo 000)"
[ "$forged" = "401" ] && pass live_forged_header_refused "http=401" \
  || fail live_forged_header_refused "http=$forged"

# --------------------------------------- 4. the smoke, with a real session
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
from nativeforge.services import tenant_source_watchlist_service as watchlist
from nativeforge.services.customer_persistence_activation_service import (
    resolve_accountable_identity,
)
from nativeforge.services.customer_session_format_service import build_session
from nativeforge.services.source_collector_configuration_preflight_service import (
    build_collector_preflight,
    collector_preflight_invariant_failures,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    allowlist_invariant_failures,
    evaluate_registry,
    evaluate_source,
)
from nativeforge.services.source_monitoring_readiness_service import (
    build_source_monitoring_readiness,
    source_monitoring_readiness_invariant_failures,
)

DEMO = os.environ["NF_DEMO_ORG"]
OTHER = "cccccccc-dddd-eeee-ffff-00000000d143"
# A real federal registry row. Watching it is a statement of interest; nothing
# here fetches it.
WATCHED_SOURCE = "nf-seed-2026-fed-001"
GRANTS_GOV_SOURCE = "nf-seed-2026-fed-013"

# -- the registry, classified. No socket is opened. ----------------------
evaluation = evaluate_registry()
out["registry_row_count"] = int(evaluation["registry_row_count"])
out["by_state"] = evaluation["by_state"]
out["monitorable_count"] = int(evaluation["monitorable_count"])
out["allowlist_invariant_failures"] = allowlist_invariant_failures(evaluation)

# -- the four refusals, each driven for real ------------------------------
refusals = {
    "unknown_source": evaluate_source(source_id="nf-seed-9999-not-real"),
    "terms_blocked": evaluate_source(source_id=WATCHED_SOURCE),
    "human_review_only": evaluate_source(source_id=GRANTS_GOV_SOURCE),
    "fixture_outside_a_test": evaluate_source(source_id="nf-fixture-gate143"),
}
out["refusals"] = {
    name: {
        "state": r["state"],
        "monitorable": r["monitorable"],
        "blocked_reasons": r["blocked_reasons"],
    }
    for name, r in refusals.items()
}
out["unknown_source_refused"] = refusals["unknown_source"]["state"] == "unknown_source"
out["terms_blocked_refused"] = refusals["terms_blocked"]["state"] == "terms_blocked"
out["human_review_refused"] = (
    refusals["human_review_only"]["state"] == "human_review_blocked"
)
out["fixture_refused_outside_a_test"] = (
    refusals["fixture_outside_a_test"]["state"] == "unknown_source"
)

# The credential class, driven through the allowlist's own rule rather than
# through a SAM.gov row - the registry has none, and inventing one would be
# fabricating a source.
sam_like = evaluate_source(
    source_id="nf-seed-sam-probe",
    registry={
        "nf-seed-sam-probe": {
            "seed_id": "nf-seed-sam-probe",
            "canonical_source_id": "nf:source:nf-seed-sam-probe",
            "source_name": "SAM.gov probe row (not in the shipped registry)",
            "source_url": "https://sam.gov/",
            "access_posture_hint": "public",
            "resolver_url_status": "resolved",
            "source_health_status": "healthy",
        }
    },
)
out["api_key_missing_refused"] = sam_like["state"] == "api_key_missing"
out["sam_blocked_reasons"] = sam_like["blocked_reasons"]

# -- the hermetic fixture source, which proves the evaluation path --------
fixture = evaluate_source(source_id="nf-fixture-gate143", allow_fixture=True)
out["fixture_evaluates_hermetically"] = fixture["state"] == "fixture_allowed"
out["fixture_is_not_monitorable"] = fixture["monitorable"] is False

# -- a reviewed and approved source, so the permitted branch is reachable --
approved = evaluate_source(
    source_id=WATCHED_SOURCE,
    terms_statuses={WATCHED_SOURCE: "NO_REVIEW_REQUIRED"},
    activation_approvals=[WATCHED_SOURCE],
)
out["approved_branch_reachable"] = approved["state"] == "activation_approved"

collector = build_collector_preflight(
    config={
        "source_id": WATCHED_SOURCE,
        "fetch_mode": "dry_run",
        "rate_limit_policy": "polite_default",
        "attribution_requirement": "not_required",
        "user_agent_policy": "nativeforge_canonical",
        "raw_payload_storage_policy": "local_dev_ignored",
        "activation_approval": True,
    },
    terms_statuses={WATCHED_SOURCE: "NO_REVIEW_REQUIRED"},
    activation_approvals=[WATCHED_SOURCE],
)
out["collector_preflight_state"] = collector["state"]
out["collector_may_run_live"] = bool(collector["collector_may_run_live"])
out["collector_invariant_failures"] = collector_preflight_invariant_failures(collector)

# -- a session and a watchlist entry, so the routes have something real ----
with engine.connect() as connection:
    identity = resolve_accountable_identity(connection=connection, organization_id=DEMO)
out["accountable_identity_resolved"] = bool(identity)

entry_id = uuid.uuid4()
with engine.begin() as connection:
    added = watchlist.add_watchlist_entry(
        connection=connection,
        entry_id=entry_id,
        organization_id=DEMO,
        source_id=WATCHED_SOURCE,
        watchlist_source="registry_entry",
        source_name="Gate 143 preflight probe",
        jurisdiction="federal",
        fact_status="demo_fixture",
        is_demo=True,
        created_by_identity_id=identity,
    )
out["watchlist_entry_written"] = int(added.get("rows_written") or 0) == 1
if not added.get("rows_written"):
    out["watchlist_blocked_reasons"] = list(added.get("blocked_reasons") or [])

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

base = f"/v1/nf/demo/orgs/{DEMO}/source-monitoring"
try:
    with httpx.Client(
        base_url=os.environ.get("NF_BACKEND", "http://127.0.0.1:8000"), timeout=20.0
    ) as client:
        readiness_response = client.get(f"{base}/readiness", headers=headers)
        blockers_response = client.get(f"{base}/blockers", headers=headers)
        evaluate_response = client.post(
            f"{base}/evaluate", json={"source_id": WATCHED_SOURCE}, headers=headers
        )
        unwatched_response = client.post(
            f"{base}/evaluate", json={"source_id": GRANTS_GOV_SOURCE}, headers=headers
        )
        cross = client.get(
            f"/v1/nf/demo/orgs/{OTHER}/source-monitoring/readiness", headers=headers
        )
finally:
    with engine.begin() as connection:
        watchlist.archive_watchlist_entry(
            connection=connection, organization_id=DEMO, entry_id=str(entry_id)
        )
        out["watchlist_entries_left_live"] = int(
            watchlist.list_watchlist(connection=connection, organization_id=DEMO).get(
                "rows_read"
            )
            or 0
        )

out["driven_over"] = "http"


def body(response):
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


readiness_body = body(readiness_response)
out["readiness_route_operational"] = (
    readiness_response.status_code == 200
    and "source_monitoring_preflight_ready" in readiness_body
)
out["blockers_route_operational"] = (
    blockers_response.status_code == 200
    and "activation_blockers" in body(blockers_response)
)
out["evaluate_route_operational"] = (
    evaluate_response.status_code == 200 and "state" in body(evaluate_response)
)
out["unwatched_source_refused"] = unwatched_response.status_code == 404
out["cross_org_refused"] = cross.status_code in {403, 404}

# What the routes must never claim.
for name, response in (
    ("readiness", readiness_response),
    ("blockers", blockers_response),
    ("evaluate", evaluate_response),
):
    payload = body(response)
    for claim in (
        "fetch_performed",
        "collector_activated",
        "source_monitoring_live",
        "live_source_coverage",
        "api_key_values_reported",
    ):
        if payload.get(claim):
            out.setdefault("route_claims", []).append(f"{name}:{claim}")

readiness = build_source_monitoring_readiness(
    registry_evaluation=evaluation,
    collector_preflight=collector,
    watchlist_can_name_sources=True,
    tenant_digest_operational=True,
    route_smoke={
        "readiness_routes_operational": out["readiness_route_operational"],
        "unauthenticated_refused": True,
        "cross_org_refused": out["cross_org_refused"],
        "blocked_reasons": [],
    },
)
out["source_monitoring_preflight_ready"] = bool(
    readiness["source_monitoring_preflight_ready"]
)
out["source_monitoring_live"] = bool(readiness["source_monitoring_live"])
out["scope"] = readiness["scope"]
out["chokepoint_clean"] = bool(readiness["chokepoint_clean"])
out["activation_blockers"] = [b["blocker"] for b in readiness["activation_blockers"]]
out["readiness_blocked_reasons"] = list(readiness["blocked_reasons"])
out["readiness_invariant_failures"] = source_monitoring_readiness_invariant_failures(
    readiness
)
for key in (
    "collector_activated",
    "fetch_performed",
    "network_calls",
    "live_source_coverage",
    "production_source_monitoring",
    "customer_auth_live",
    "real_organization_touched",
    "api_key_values_reported",
):
    out[f"readiness_{key}"] = readiness[key]

print(json.dumps(out))
PY
)"

LAST_LINE="$(echo "$MEASURED" | tail -n 1)"
if ! echo "$LAST_LINE" | .venv/bin/python -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
  fail measurement_available "preflight_failed"
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

READY="$(get source_monitoring_preflight_ready)"
LIVE="$(get source_monitoring_live)"

# ------------------------------------------------------ 5. what must stay true
[ "$(get login_live)" = "True" ] && pass login_live "true" || block login_live "false"
[ "$(get accountable_identity_resolved)" = "True" ] && pass accountable_identity \
  "nf_org_memberships" || block accountable_identity "absent"
[ "$(get session_minted)" = "True" ] && pass session_minted "real_signed_session" \
  || block session_minted "absent"
[ "$(get watchlist_entry_written)" = "True" ] && pass watchlist_entry_written \
  || block watchlist_entry_written "$(getlist watchlist_blocked_reasons)"

echo "count=registry_rows n=$(get registry_row_count)"
echo "by_state=$(get by_state)"

# ------------------------------------------------------------- 6. the routes
for capability in readiness_route_operational blockers_route_operational \
                  evaluate_route_operational; do
  [ "$(get "$capability")" = "True" ] && pass "capability:$capability" \
    || block "capability_not_proved:$capability"
done

# ------------------------------------------------------------ 7. the refusals
for refusal in unknown_source_refused terms_blocked_refused human_review_refused \
               api_key_missing_refused fixture_refused_outside_a_test \
               unwatched_source_refused cross_org_refused; do
  [ "$(get "$refusal")" = "True" ] && pass "refusal:$refusal" \
    || fail "refusal:$refusal" "$(get "$refusal")"
done

# ------------------------------------- 8. the permitted branches are reachable
[ "$(get fixture_evaluates_hermetically)" = "True" ] && pass hermetic_fixture_evaluates \
  || fail hermetic_fixture_evaluates "$(get fixture_evaluates_hermetically)"
[ "$(get fixture_is_not_monitorable)" = "True" ] && pass fixture_is_not_monitorable \
  || fail fixture_is_not_monitorable "$(get fixture_is_not_monitorable)"
[ "$(get approved_branch_reachable)" = "True" ] && pass approved_branch_reachable \
  "a recorded terms review plus an approval" \
  || fail approved_branch_reachable "$(get approved_branch_reachable)"
echo "collector_preflight_state=$(get collector_preflight_state)"

# --------------------------------- 9. NOTHING WAS CALLED AND NOTHING STARTED
for field in source_monitoring_live collector_may_run_live \
             readiness_collector_activated readiness_fetch_performed \
             readiness_live_source_coverage \
             readiness_production_source_monitoring \
             readiness_customer_auth_live readiness_real_organization_touched \
             readiness_api_key_values_reported; do
  value="$(get "$field")"
  [ "$value" = "False" ] && pass "stays_false:$field" \
    || fail "stays_false:$field" "$value"
done

for field in monitorable_count readiness_network_calls watchlist_entries_left_live; do
  value="$(get "$field")"
  echo "count=$field n=$value"
  [ "$value" = "0" ] && pass "stays_zero:$field" || fail "stays_zero:$field" "$value"
done

CLAIMS="$(getlist route_claims)"
[ -z "$CLAIMS" ] && pass no_route_claimed_a_live_capability \
  || fail no_route_claimed_a_live_capability "$CLAIMS"

[ "$(get chokepoint_clean)" = "True" ] && pass chokepoint_clean \
  || fail chokepoint_clean "$(get chokepoint_clean)"

for inv in allowlist_invariant_failures collector_invariant_failures \
           readiness_invariant_failures; do
  value="$(getlist "$inv")"
  [ -z "$value" ] && pass "invariants:$inv" "none_failed" || fail "invariants:$inv" "$value"
done

echo "activation_blockers=$(getlist activation_blockers)"

# ------------------------------------------------------------- 10. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

if [ "$READY" = "True" ] && [ "$LIVE" = "False" ] && [ -z "$BLOCKERS" ]; then
  echo "RESULT=PASS"
  echo "source_monitoring_preflight_ready=true"
  echo "scope=$(get scope)"
  echo "source_monitoring_live=false"
  echo "collectors_activated=0"
  echo "live_source_calls=0"
  echo "sources_cleared_for_collection=0"
  echo "registry_rows_classified=$(get registry_row_count)"
  echo "api_keys_printed=false"
  echo "production_source_monitoring=false"
  exit 0
fi

echo "RESULT=BLOCKED"
echo "source_monitoring_preflight_ready=$READY"
echo "source_monitoring_live=$LIVE"
if [ -n "$BLOCKERS" ]; then
  echo "blocker=$BLOCKERS"
else
  echo "blocker=$(getlist readiness_blocked_reasons)"
fi
echo "next=docs/operations/750_GATE143_SOURCE_MONITORING_READINESS_DELTA.md"
exit 1
