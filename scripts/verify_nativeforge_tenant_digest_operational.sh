#!/usr/bin/env bash
# Gate 140I — is the tenant digest actually operational right now?
#
# RESULT=PASS only when tenant_digest_operational is true. Anything else is
# RESULT=BLOCKED with the exact blocker named.
#
# It proves it by calling the routes: add two real registry sources to the
# watchlist, read them back anchored on organization_id, ask for the weekly
# digest with no setting at all, ask for the daily one and be refused until the
# profile enables it, suppress an opportunity with a real audit row behind it,
# watch the item move rather than vanish, lift it, read readiness, read
# everything as another organization and get nothing, then archive what it
# created.
#
# The session is real. It is minted through `customer_session_format_service`
# for the demo organization's existing owner identity, read out of
# `nf_org_memberships` - the same chain a browser login produces. No fake user,
# no fake session, no fake membership.
#
# Every row is fixture-labelled and cleaned up. No live grant source is called,
# no collector is started, no mail is sent, no object store is contacted, and
# the real organization is never addressed.
#
# WATCHING IS NOT MONITORING. A watchlist entry is a statement of interest;
# `source_monitoring_live` is false in every response and this script fails if
# it is ever true.
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

echo "verify=tenant_digest_operational"

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

# ------------------------------------ 2. every route, over real HTTP, anonymous
#
# Against the running server, not a test client: these must fail closed for
# anybody on the network, which is a different claim from failing closed in a
# process that imported the app.
ENTRY="00000000-0000-0000-0000-000000000140"
anon_ok=1
for spec in \
  "GET /v1/nf/demo/orgs/${DEMO_ORG}/source-watchlist" \
  "POST /v1/nf/demo/orgs/${DEMO_ORG}/source-watchlist" \
  "GET /v1/nf/demo/orgs/${DEMO_ORG}/source-watchlist/${ENTRY}" \
  "POST /v1/nf/demo/orgs/${DEMO_ORG}/source-watchlist/${ENTRY}/archive" \
  "GET /v1/nf/demo/orgs/${DEMO_ORG}/digest" \
  "GET /v1/nf/demo/orgs/${DEMO_ORG}/digest/readiness" \
  "POST /v1/nf/demo/orgs/${DEMO_ORG}/digest/cadence" \
  "POST /v1/nf/demo/orgs/${DEMO_ORG}/digest/suppress" \
  "POST /v1/nf/demo/orgs/${DEMO_ORG}/digest/lift"
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
[ "$anon_ok" = "1" ] && pass live_route_refuses_unauthenticated "401 x9"

forged="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  -H "X-NF-Org-Id: ${DEMO_ORG}" \
  "$BACKEND/v1/nf/demo/orgs/${DEMO_ORG}/digest" 2>/dev/null || echo 000)"
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
# and cannot VERIFY one. Read through Settings, placed in this process's own
# environment, never printed. The running server already has it via systemd.
_raw = getattr(get_settings(), "nf_session_signing_key", "") or ""
_key = (
    _raw.get_secret_value() if hasattr(_raw, "get_secret_value") else str(_raw)
).strip()
if _key and not os.environ.get("NF_SESSION_SIGNING_KEY"):
    os.environ["NF_SESSION_SIGNING_KEY"] = _key

import sqlalchemy as sa

from nativeforge.db.session import engine
from nativeforge.services.customer_persistence_activation_service import (
    prove_customer_persistence,
    resolve_accountable_identity,
)
from nativeforge.services.customer_session_format_service import build_session
from nativeforge.services.tenant_digest_operational_readiness_service import (
    build_tenant_digest_readiness,
    tenant_digest_readiness_invariant_failures,
)
from nativeforge.services.tenant_digest_route_smoke_service import (
    run_tenant_digest_route_smoke,
    tenant_digest_route_smoke_invariant_failures,
)
from nativeforge.services.tenant_profile_repository_service import (
    archive_tenant_profile,
    get_tenant_profile,
    upsert_tenant_profile,
)

DEMO = os.environ["NF_DEMO_ORG"]
OTHER = "cccccccc-dddd-eeee-ffff-00000000d140"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

# Gate 138's round trip, so the readiness roll-up has a repository proof that
# was measured rather than assumed.
with engine.begin() as connection:
    persistence = prove_customer_persistence(
        connection=connection, organization_id=DEMO
    )
out["customer_persistence_live"] = bool(persistence["customer_persistence_live"])
out["persistence_rows_left_live"] = int(persistence["rows_left_live"])

with engine.connect() as connection:
    identity = resolve_accountable_identity(connection=connection, organization_id=DEMO)
out["accountable_identity_resolved"] = bool(identity)

# The digest needs a tenant profile, and the demo organization has none live -
# Gate 138's persistence smoke archives what it writes. So seed one, weekly and
# fixture-labelled, and archive it again at the end. Weekly on purpose: the
# smoke proves weekly is the DEFAULT with no setting, so seeding daily would
# have hidden the thing the daily check is meant to demonstrate.
with engine.begin() as connection:
    before = get_tenant_profile(connection=connection, organization_id=DEMO)
    out["profile_existed_before"] = bool(before.get("rows_read"))
    seeded = upsert_tenant_profile(
        connection=connection,
        organization_id=DEMO,
        tenant_id_label="nf-verify-gate140",
        customer_org_id_label="nf-verify-gate140",
        recognition_status="federally_recognized",
        recognition_status_fact_status="demo_fixture",
        operating_states=["SC"],
        operating_states_fact_status="demo_fixture",
        applicant_classes=["federally_recognized_tribe"],
        applicant_classes_fact_status="demo_fixture",
        digest_frequency="weekly",
        profile_status="active",
        is_demo=True,
    )
out["profile_seeded"] = bool(seeded.get("rows_written"))
if not seeded.get("rows_written"):
    out["profile_blocked_reasons"] = list(seeded.get("blocked_reasons") or [])

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

try:
    with httpx.Client(
        base_url=os.environ.get("NF_BACKEND", "http://127.0.0.1:8000"), timeout=20.0
    ) as client:
        smoke = run_tenant_digest_route_smoke(
            client=client,
            organization_id=DEMO,
            other_organization_id=OTHER,
            session_headers=headers,
        )
finally:
    # Leave the database as it was found: no live profile, whatever the smoke
    # did to the cadence along the way.
    with engine.begin() as connection:
        archived = archive_tenant_profile(connection=connection, organization_id=DEMO)
        out["profile_archived_after"] = int(archived.get("rows_written") or 0) > 0
        for table, column in (
            ("nf_source_watchlist_entries", "archived_at"),
            ("nf_tenant_pursuit_suppressions", "lifted_at"),
        ):
            out[f"{table}_left_live"] = int(
                connection.execute(
                    sa.text(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL")
                ).scalar_one()
            )
            anchors = [
                row[0]
                for row in connection.execute(
                    sa.text(f"SELECT organization_id FROM {table}")
                ).all()
            ]
            matched = 0
            for anchor in anchors:
                try:
                    matched += int(uuid.UUID(str(anchor)) == uuid.UUID(REAL))
                except (ValueError, AttributeError, TypeError):
                    continue
            out[f"{table}_for_the_real_org"] = matched
            out[f"{table}_not_fixture_labelled"] = int(
                connection.execute(
                    sa.text(
                        f"SELECT COUNT(*) FROM {table} "
                        "WHERE fact_status <> 'demo_fixture'"
                    )
                ).scalar_one()
            )

out["driven_over"] = "http"

readiness = build_tenant_digest_readiness(
    route_smoke=smoke,
    customer_persistence_live=persistence["customer_persistence_live"],
    profile_available=bool(seeded.get("rows_written")),
)

for key in (
    "end_to_end_completed",
    "unauthenticated_refused",
    "forged_header_refused",
    "watchlist_route_operational",
    "watchlist_registry_check_enforced",
    "watchlist_fixture_prefix_enforced",
    "watchlist_caller_supplied_fields_refused",
    "watchlist_archive_preserves_the_row",
    "digest_preview_operational",
    "weekly_default_proved",
    "daily_refused_before_opt_in",
    "daily_setting_proved",
    "unknown_cadence_refused",
    "suppression_proved",
    "suppression_audit_backed",
    "suppression_preserves_the_opportunity",
    "suppression_lift_proved",
    "cross_org_refused",
    "readiness_route_operational",
    "live_grant_sources_called",
    "network_calls_to_grant_sources",
    "emails_sent",
    "collectors_activated",
    "object_store_calls",
    "real_customer_data_written",
    "real_organization_touched",
):
    out[key] = smoke[key]
out["item_counts"] = smoke["item_counts"]
out["smoke_notes"] = list(smoke["notes"])
out["smoke_blocked_reasons"] = list(smoke["blocked_reasons"])
out["smoke_invariant_failures"] = tenant_digest_route_smoke_invariant_failures(smoke)

for key in (
    "tenant_digest_operational",
    "scope",
    "source_monitoring_required_for_preview",
    "email_required_for_preview",
    "source_monitoring_live",
    "email_delivery_available",
    "live_source_coverage",
    "production_tenant_digest",
    "production_rollout",
    "controlled_customer_pilot",
):
    out[key] = readiness[key]
out["readiness_blocked_reasons"] = list(readiness["blocked_reasons"])
out["readiness_invariant_failures"] = tenant_digest_readiness_invariant_failures(
    readiness
)

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

OPERATIONAL="$(get tenant_digest_operational)"
SCOPE="$(get scope)"

# ------------------------------------------------------ 4. what must stay true
[ "$(get login_live)" = "True" ] && pass login_live "true" || block login_live "false"
[ "$(get customer_persistence_live)" = "True" ] && pass customer_persistence_live "true" \
  || block customer_persistence_live "false"
[ "$(get accountable_identity_resolved)" = "True" ] && pass accountable_identity "nf_org_memberships" \
  || block accountable_identity "absent"
[ "$(get session_minted)" = "True" ] && pass session_minted "real_signed_session" \
  || block session_minted "$(getlist session_blocked_reasons)"
[ "$(get profile_seeded)" = "True" ] && pass fixture_profile_seeded "weekly" \
  || block fixture_profile_seeded "$(getlist profile_blocked_reasons)"

# ------------------------------------------------------------- 5. the capabilities
for capability in watchlist_route_operational digest_preview_operational \
                  weekly_default_proved daily_setting_proved suppression_proved \
                  suppression_audit_backed readiness_route_operational; do
  [ "$(get "$capability")" = "True" ] && pass "capability:$capability" \
    || block "capability_not_proved:$capability"
done

[ "$(get end_to_end_completed)" = "True" ] && pass end_to_end_tenant_digest_smoke "all_routes" \
  || block end_to_end_tenant_digest_smoke "did_not_complete"

# ------------------------------------------------------------ 6. the refusals
for refusal in unauthenticated_refused forged_header_refused cross_org_refused \
               unknown_cadence_refused daily_refused_before_opt_in \
               watchlist_registry_check_enforced watchlist_fixture_prefix_enforced \
               watchlist_caller_supplied_fields_refused \
               watchlist_archive_preserves_the_row \
               suppression_preserves_the_opportunity suppression_lift_proved; do
  [ "$(get "$refusal")" = "True" ] && pass "refusal:$refusal" \
    || fail "refusal:$refusal" "$(get "$refusal")"
done

# ------------------------------------------------------- 7. what stays false
for field in live_grant_sources_called real_customer_data_written \
             real_organization_touched source_monitoring_live \
             email_delivery_available live_source_coverage \
             production_tenant_digest production_rollout \
             controlled_customer_pilot \
             source_monitoring_required_for_preview email_required_for_preview; do
  value="$(get "$field")"
  [ "$value" = "False" ] && pass "stays_false:$field" \
    || fail "stays_false:$field" "$value"
done

for field in network_calls_to_grant_sources emails_sent collectors_activated \
             object_store_calls; do
  value="$(get "$field")"
  [ "$value" = "0" ] && pass "stays_zero:$field" || fail "stays_zero:$field" "$value"
done

# --------------------------------------------------------- 8. nothing left behind
for field in nf_source_watchlist_entries_left_live \
             nf_tenant_pursuit_suppressions_left_live \
             nf_source_watchlist_entries_for_the_real_org \
             nf_tenant_pursuit_suppressions_for_the_real_org \
             nf_source_watchlist_entries_not_fixture_labelled \
             nf_tenant_pursuit_suppressions_not_fixture_labelled \
             persistence_rows_left_live; do
  value="$(get "$field")"
  echo "count=$field n=$value"
  [ "$value" = "0" ] && pass "cleanup:$field" || fail "cleanup:$field" "n=$value"
done

[ "$(get profile_archived_after)" = "True" ] && pass fixture_profile_archived_after \
  || fail fixture_profile_archived_after "$(get profile_archived_after)"

SMOKE_INV="$(getlist smoke_invariant_failures)"
READY_INV="$(getlist readiness_invariant_failures)"
[ -z "$SMOKE_INV" ] && pass smoke_invariants "none_failed" || fail smoke_invariants "$SMOKE_INV"
[ -z "$READY_INV" ] && pass readiness_invariants "none_failed" \
  || fail readiness_invariants "$READY_INV"

NOTES="$(getlist smoke_notes)"
[ -n "$NOTES" ] && echo "notes=$NOTES"

# ------------------------------------------------------------- 9. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

if [ "$OPERATIONAL" = "True" ] && [ -z "$BLOCKERS" ]; then
  echo "RESULT=PASS"
  echo "tenant_digest_operational=true"
  echo "scope=$SCOPE"
  echo "source_watchlist=operational"
  echo "digest_preview=operational"
  echo "weekly_default=operational"
  echo "daily_optional_setting=operational"
  echo "pursuit_suppression=operational"
  echo "customer_auth_live=$(get customer_auth_live)"
  echo "source_monitoring_live=false"
  echo "email_delivery=false"
  echo "production_tenant_digest=false"
  exit 0
fi

echo "RESULT=BLOCKED"
echo "tenant_digest_operational=$OPERATIONAL"
if [ -n "$BLOCKERS" ]; then
  echo "blocker=$BLOCKERS"
else
  echo "blocker=$(getlist readiness_blocked_reasons)"
fi
echo "smoke_blockers=$(getlist smoke_blocked_reasons)"
echo "next=docs/operations/736_GATE140_TENANT_DIGEST_READINESS_DELTA.md"
exit 1
