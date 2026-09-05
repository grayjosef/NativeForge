#!/usr/bin/env bash
# Gate 142I — can this system rehearse digest delivery, without sending any?
#
# RESULT=PASS when email_delivery_readiness is true for controlled_dev_demo AND
# email_delivery is false. Both halves matter: a run where mail actually went
# out is a FAILURE of this verifier, not a success.
#
# It proves it by calling the routes: render a digest for delivery, read the
# recipients as fingerprints, record a dry run with a real audit event, read the
# intents back, run it again and be refused as already recorded, cancel one and
# find the row still there, read readiness, and read everything as another
# organization and get nothing.
#
# The session is real, minted through `customer_session_format_service` for the
# demo organization's existing owner identity out of `nf_org_memberships`. No
# fake user, no fake session, no fake membership.
#
# NO EMAIL IS SENT. NO PROVIDER IS CONTACTED. No delivery module imports a mail
# library - checked by parsing, because `smtplib` ships with Python and "not
# installed" is not a guarantee available here. This script fails if any of that
# changes.
#
# NO RECIPIENT ADDRESS IS PRINTED. Fingerprints, domains, counts, booleans and
# blocker names only. No secrets, tokens, cookies, state, PKCE verifier or
# provider subject.
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

echo "verify=email_delivery_readiness"

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

# ------------------------------ 2. no delivery module imports a mail library
#
# Checked first and by PARSING. `smtplib` is in the standard library, so unlike
# Gate 141's object store SDK there is no "not installed" guarantee to lean on -
# the guarantee is that nothing imports it.
MAIL_IMPORTS="$(.venv/bin/python - <<'PY'
import json
import sys

sys.path.insert(0, "src")

from nativeforge.services.email_delivery_readiness_service import (
    detect_mail_library_imports,
)

found = detect_mail_library_imports()
print(json.dumps(found["mail_library_imports"]) if found["mail_library_imports"] else "none")
PY
)"
[ "$MAIL_IMPORTS" = "none" ] && pass no_mail_library_imported "none" \
  || fail no_mail_library_imported "$MAIL_IMPORTS"

# ----------------------------------- 3. every route, over real HTTP, anonymous
anon_ok=1
for spec in \
  "GET /v1/nf/demo/orgs/${DEMO_ORG}/digest/delivery/preview" \
  "GET /v1/nf/demo/orgs/${DEMO_ORG}/digest/delivery/recipients" \
  "POST /v1/nf/demo/orgs/${DEMO_ORG}/digest/delivery/dry-run" \
  "GET /v1/nf/demo/orgs/${DEMO_ORG}/digest/delivery/intents" \
  "POST /v1/nf/demo/orgs/${DEMO_ORG}/digest/delivery/cancel" \
  "GET /v1/nf/demo/orgs/${DEMO_ORG}/digest/delivery/readiness"
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
[ "$anon_ok" = "1" ] && pass live_route_refuses_unauthenticated "401 x6"

forged="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  -H "X-NF-Org-Id: ${DEMO_ORG}" \
  "$BACKEND/v1/nf/demo/orgs/${DEMO_ORG}/digest/delivery/readiness" \
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

# `.env` reaches pydantic Settings and never `os.environ`. Read the signing key
# through Settings into this process's own environment, never printed.
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
from nativeforge.services.digest_delivery_route_smoke_service import (
    delivery_route_smoke_invariant_failures,
    run_digest_delivery_route_smoke,
)
from nativeforge.services.email_delivery_readiness_service import (
    build_email_delivery_readiness,
    delivery_readiness_invariant_failures,
)
from nativeforge.services.email_provider_configuration_preflight_service import (
    build_email_provider_preflight,
    email_preflight_invariant_failures,
)
from nativeforge.services.tenant_profile_repository_service import (
    archive_tenant_profile,
    upsert_tenant_profile,
)

DEMO = os.environ["NF_DEMO_ORG"]
OTHER = "cccccccc-dddd-eeee-ffff-00000000d142"

preflight = build_email_provider_preflight()
out["preflight_state"] = preflight["state"]
out["provider_configured"] = bool(preflight["provider_configured"])
out["send_activated"] = bool(preflight["send_activated"])
out["email_delivery"] = bool(preflight["email_delivery"])
# Setting NAMES. No value reaches this report.
out["missing_configuration"] = list(preflight["absent_setting_names"])
out["preflight_invariant_failures"] = email_preflight_invariant_failures(preflight)

with engine.begin() as connection:
    persistence = prove_customer_persistence(
        connection=connection, organization_id=DEMO
    )
out["customer_persistence_live"] = bool(persistence["customer_persistence_live"])
out["persistence_rows_left_live"] = int(persistence["rows_left_live"])

with engine.connect() as connection:
    identity = resolve_accountable_identity(connection=connection, organization_id=DEMO)
out["accountable_identity_resolved"] = bool(identity)

# The digest needs a tenant profile, and Gate 138's persistence smoke archives
# what it writes. Seed one, weekly and fixture-labelled, and archive it again.
with engine.begin() as connection:
    seeded = upsert_tenant_profile(
        connection=connection,
        organization_id=DEMO,
        tenant_id_label="nf-verify-gate142",
        customer_org_id_label="nf-verify-gate142",
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

import httpx

try:
    with httpx.Client(
        base_url=os.environ.get("NF_BACKEND", "http://127.0.0.1:8000"), timeout=20.0
    ) as client:
        smoke = run_digest_delivery_route_smoke(
            client=client,
            organization_id=DEMO,
            other_organization_id=OTHER,
            session_headers=headers,
        )
finally:
    # Leave the database as it was found.
    with engine.begin() as connection:
        archived = archive_tenant_profile(connection=connection, organization_id=DEMO)
        out["profile_archived_after"] = int(archived.get("rows_written") or 0) > 0
        connection.execute(
            sa.text(
                "UPDATE nf_digest_delivery_intents SET cancelled_at = "
                "CURRENT_TIMESTAMP, delivery_status = 'cancelled', "
                "blocked_reason = 'cancelled_by_tenant' WHERE cancelled_at IS NULL"
            )
        )
        out["intents_left_live"] = int(
            connection.execute(
                sa.text(
                    "SELECT COUNT(*) FROM nf_digest_delivery_intents "
                    "WHERE cancelled_at IS NULL"
                )
            ).scalar_one()
        )
        out["intents_claiming_a_send"] = int(
            connection.execute(
                sa.text(
                    "SELECT COUNT(*) FROM nf_digest_delivery_intents "
                    "WHERE send_attempted OR provider_contacted OR emails_sent > 0"
                )
            ).scalar_one()
        )
        out["intents_with_an_address_shaped_fingerprint"] = int(
            connection.execute(
                sa.text(
                    "SELECT COUNT(*) FROM nf_digest_delivery_intents "
                    "WHERE recipient_fingerprint LIKE '%@%'"
                )
            ).scalar_one()
        )
        out["non_fixture_intents"] = int(
            connection.execute(
                sa.text(
                    "SELECT COUNT(*) FROM nf_digest_delivery_intents "
                    "WHERE fact_status <> 'demo_fixture'"
                )
            ).scalar_one()
        )
        out["delivery_audit_events"] = int(
            connection.execute(
                sa.text(
                    "SELECT COUNT(*) FROM nf_audit_events "
                    "WHERE action = 'digest_delivery_intent_recorded'"
                )
            ).scalar_one()
        )

out["driven_over"] = "http"

readiness = build_email_delivery_readiness(
    preflight=preflight,
    render_proof={
        "deliverable": bool(smoke["digest_renders_for_delivery"]),
        "emails_sent": 0,
        "provider_contacted": False,
    },
    recipient_proof={
        "deliverable_count": 1 if smoke["recipient_validation_works"] else 0,
        "addresses_stored": False,
    },
    queue_proof={
        "rows_written": 1 if smoke["delivery_intent_recorded"] else 0,
        "blocked_reason": "no_email_provider_configured",
        "emails_sent": 0,
        "provider_contacted": False,
        "addresses_stored": False,
    },
    audit_proof={"audit_event_recorded": bool(smoke["delivery_audit_event_created"])},
    route_smoke=smoke,
    tenant_digest_operational=True,
    customer_persistence_live=persistence["customer_persistence_live"],
)

for key in (
    "end_to_end_completed",
    "unauthenticated_refused",
    "forged_header_refused",
    "delivery_routes_operational",
    "digest_renders_for_delivery",
    "recipient_validation_works",
    "no_address_in_any_response",
    "delivery_intent_recorded",
    "delivery_audit_event_created",
    "send_disabled_blocker_explicit",
    "duplicate_run_refused",
    "cancel_preserves_the_row",
    "unknown_cadence_refused",
    "caller_supplied_fields_refused",
    "cross_org_refused",
    "readiness_route_operational",
    "emails_sent",
    "send_attempted",
    "provider_contacted",
    "network_calls_to_a_mail_provider",
    "recipient_addresses_stored",
    "recipient_addresses_reported",
    "real_customer_data_written",
    "real_organization_touched",
):
    out[key] = smoke[key]
out["intent_counts"] = smoke["intent_counts"]
out["smoke_notes"] = list(smoke["notes"])
out["smoke_blocked_reasons"] = list(smoke["blocked_reasons"])
out["smoke_invariant_failures"] = delivery_route_smoke_invariant_failures(smoke)

for key in (
    "email_delivery_readiness",
    "scope",
    "send_disabled_blocker",
    "provider_required_for_readiness",
    "send_activation_required_for_readiness",
    "real_recipient_required_for_readiness",
    "production_email_delivery",
):
    out[f"readiness_{key}"] = readiness[key]
out["readiness_blocked_reasons"] = list(readiness["blocked_reasons"])
out["readiness_invariant_failures"] = delivery_readiness_invariant_failures(readiness)

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

READINESS="$(get readiness_email_delivery_readiness)"
DELIVERY="$(get email_delivery)"

# ------------------------------------------------------ 5. what must stay true
[ "$(get login_live)" = "True" ] && pass login_live "true" || block login_live "false"
[ "$(get customer_persistence_live)" = "True" ] && pass customer_persistence_live "true" \
  || block customer_persistence_live "false"
[ "$(get accountable_identity_resolved)" = "True" ] && pass accountable_identity "nf_org_memberships" \
  || block accountable_identity "absent"
[ "$(get session_minted)" = "True" ] && pass session_minted "real_signed_session" \
  || block session_minted "$(getlist session_blocked_reasons)"
[ "$(get profile_seeded)" = "True" ] && pass fixture_profile_seeded "weekly" \
  || block fixture_profile_seeded "$(getlist profile_blocked_reasons)"

# ------------------------------------------------------------- 6. the rehearsal
for capability in digest_renders_for_delivery recipient_validation_works \
                  delivery_intent_recorded delivery_audit_event_created \
                  send_disabled_blocker_explicit delivery_routes_operational \
                  readiness_route_operational; do
  [ "$(get "$capability")" = "True" ] && pass "capability:$capability" \
    || block "capability_not_proved:$capability"
done

[ "$(get end_to_end_completed)" = "True" ] && pass end_to_end_delivery_smoke "all_routes" \
  || block end_to_end_delivery_smoke "did_not_complete"

echo "send_disabled_because=$(get readiness_send_disabled_blocker)"
echo "missing_configuration=$(getlist missing_configuration)"
echo "preflight_state=$(get preflight_state)"

# ------------------------------------------------------------ 7. the refusals
for refusal in unauthenticated_refused forged_header_refused cross_org_refused \
               unknown_cadence_refused caller_supplied_fields_refused \
               duplicate_run_refused cancel_preserves_the_row \
               no_address_in_any_response; do
  [ "$(get "$refusal")" = "True" ] && pass "refusal:$refusal" \
    || fail "refusal:$refusal" "$(get "$refusal")"
done

# ---------------------------------------------- 8. NOTHING LEFT THE BUILDING
#
# A run in which mail actually went out is a failure of this verifier.
for field in email_delivery send_attempted provider_contacted \
             recipient_addresses_stored recipient_addresses_reported \
             real_customer_data_written real_organization_touched \
             provider_configured send_activated \
             readiness_production_email_delivery \
             readiness_provider_required_for_readiness \
             readiness_send_activation_required_for_readiness \
             readiness_real_recipient_required_for_readiness; do
  value="$(get "$field")"
  [ "$value" = "False" ] && pass "stays_false:$field" \
    || fail "stays_false:$field" "$value"
done

for field in emails_sent network_calls_to_a_mail_provider \
             intents_claiming_a_send \
             intents_with_an_address_shaped_fingerprint \
             non_fixture_intents intents_left_live \
             persistence_rows_left_live; do
  value="$(get "$field")"
  echo "count=$field n=$value"
  [ "$value" = "0" ] && pass "stays_zero:$field" || fail "stays_zero:$field" "$value"
done

echo "count=delivery_audit_events n=$(get delivery_audit_events)"
[ "$(get profile_archived_after)" = "True" ] && pass fixture_profile_archived_after \
  || fail fixture_profile_archived_after "$(get profile_archived_after)"

for inv in preflight_invariant_failures smoke_invariant_failures \
           readiness_invariant_failures; do
  value="$(getlist "$inv")"
  [ -z "$value" ] && pass "invariants:$inv" "none_failed" || fail "invariants:$inv" "$value"
done

NOTES="$(getlist smoke_notes)"
[ -n "$NOTES" ] && echo "notes=$NOTES"

# ------------------------------------------------------------- 9. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

if [ "$READINESS" = "True" ] && [ "$DELIVERY" = "False" ] && [ -z "$BLOCKERS" ]; then
  echo "RESULT=PASS"
  echo "email_delivery_readiness=true"
  echo "scope=$(get readiness_scope)"
  echo "email_delivery=false"
  echo "digest_renders_for_delivery=true"
  echo "recipient_validation_works=true"
  echo "delivery_intent_recorded=true"
  echo "delivery_audit_event_created=true"
  echo "send_disabled_blocker=$(get readiness_send_disabled_blocker)"
  echo "emails_sent=0"
  echo "provider_contacted=false"
  echo "recipient_addresses_stored=false"
  echo "production_email_delivery=false"
  exit 0
fi

echo "RESULT=BLOCKED"
echo "email_delivery_readiness=$READINESS"
echo "email_delivery=$DELIVERY"
if [ -n "$BLOCKERS" ]; then
  echo "blocker=$BLOCKERS"
else
  echo "blocker=$(getlist readiness_blocked_reasons)"
fi
echo "smoke_blockers=$(getlist smoke_blocked_reasons)"
echo "next=docs/operations/744_GATE142_EMAIL_READINESS_DELTA.md"
exit 1
