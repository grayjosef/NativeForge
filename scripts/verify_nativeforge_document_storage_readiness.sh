#!/usr/bin/env bash
# Gate 141F — is document storage readiness exact right now?
#
# RESULT=PASS when document METADATA is operational and the body-storage
# refusal is correct. RESULT=BLOCKED only if the metadata path is broken or the
# expected blocker is not what it should be.
#
# `document_body_storage_ready=false` is the EXPECTED answer, not a failure.
# This deployment has no object store and every route says so by name. A
# verifier that failed on that would be demanding the gate lie.
#
# It proves it by calling the routes: create a document REFERENCE against an
# award, read it back anchored on organization_id, list the award's documents,
# read it as another organization and get nothing, ask what body storage is
# available, ask to store the bytes and be refused with the missing key NAMES,
# then archive what it created.
#
# The session is real. It is minted through `customer_session_format_service`
# for the demo organization's existing owner identity, read out of
# `nf_org_memberships`. No fake user, no fake session, no fake membership.
#
# NO OBJECT STORE IS CONTACTED. There is no SDK in this project to contact one
# with, no external adapter is constructed, no body bytes are sent, and no real
# customer file is read or hashed. This script fails if any of those changes.
#
# No secrets. No tokens. No cookies. No state. No PKCE verifier. No provider
# subject. No object storage endpoint, bucket, region, key id or secret — key
# NAMES only, which is what a reader needs and what a value is not.
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

echo "verify=document_storage_readiness"

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

# ------------------------- 2. no object storage SDK is installed, at all
#
# Checked before anything else: "no object store was contacted" is worth more
# as a property of the dependency set than as a claim about one run.
SDK_PRESENT="$(.venv/bin/python - <<'PY'
import importlib.util

found = [
    name
    for name in ("boto3", "botocore", "minio", "s3fs", "aioboto3")
    if importlib.util.find_spec(name) is not None
]
print(",".join(found) if found else "none")
PY
)"
[ "$SDK_PRESENT" = "none" ] && pass no_object_storage_sdk_installed "none" \
  || fail no_object_storage_sdk_installed "$SDK_PRESENT"

# ------------------------------------ 3. every route, over real HTTP, anonymous
DOC="00000000-0000-0000-0000-000000000141"
anon_ok=1
for spec in \
  "GET /v1/nf/demo/orgs/${DEMO_ORG}/awarded-grants/${DOC}/documents" \
  "POST /v1/nf/demo/orgs/${DEMO_ORG}/awarded-grants/${DOC}/documents" \
  "GET /v1/nf/demo/orgs/${DEMO_ORG}/documents/${DOC}" \
  "POST /v1/nf/demo/orgs/${DEMO_ORG}/documents/${DOC}/archive" \
  "GET /v1/nf/demo/orgs/${DEMO_ORG}/documents/${DOC}/body-storage" \
  "POST /v1/nf/demo/orgs/${DEMO_ORG}/documents/${DOC}/body"
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
  "$BACKEND/v1/nf/demo/orgs/${DEMO_ORG}/documents/${DOC}/body-storage" \
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

# `.env` reaches pydantic Settings and never `os.environ`. The session format
# service reads the key from the environment, so a process that only has
# Settings can SIGN a session and cannot VERIFY one. Read through Settings,
# placed in this process's own environment, never printed.
_raw = getattr(get_settings(), "nf_session_signing_key", "") or ""
_key = (
    _raw.get_secret_value() if hasattr(_raw, "get_secret_value") else str(_raw)
).strip()
if _key and not os.environ.get("NF_SESSION_SIGNING_KEY"):
    os.environ["NF_SESSION_SIGNING_KEY"] = _key

from nativeforge.db.session import engine
from nativeforge.services.customer_persistence_activation_service import (
    prove_customer_persistence,
    resolve_accountable_identity,
)
from nativeforge.services.customer_session_format_service import build_session
from nativeforge.services.document_storage_readiness_service import (
    build_document_storage_readiness,
    document_storage_readiness_invariant_failures,
)
from nativeforge.services.document_storage_route_smoke_service import (
    document_storage_route_smoke_invariant_failures,
    run_document_storage_route_smoke,
)
from nativeforge.services.object_storage_adapter_service import (
    adapter_proof_invariant_failures,
    run_hermetic_adapter_proof,
)
from nativeforge.services.object_storage_configuration_preflight_service import (
    build_object_storage_preflight,
    preflight_invariant_failures,
)

DEMO = os.environ["NF_DEMO_ORG"]
OTHER = "cccccccc-dddd-eeee-ffff-00000000d141"

# The preflight. Key NAMES reach this report; no value does.
adapter_proof = run_hermetic_adapter_proof()
preflight = build_object_storage_preflight(
    hermetic_fake_passed=bool(adapter_proof["hermetic_fake_passed"])
)
out["preflight_state"] = preflight["state"]
out["object_store_configured"] = bool(preflight["object_store_configured"])
out["missing_configuration_key_names"] = list(preflight["absent_key_names"])
out["preflight_invariant_failures"] = preflight_invariant_failures(preflight)
out["hermetic_fake_passed"] = bool(adapter_proof["hermetic_fake_passed"])
out["adapter_invariant_failures"] = adapter_proof_invariant_failures(adapter_proof)
out["adapter_checks_failed"] = list(adapter_proof["blocked_reasons"])

# The lanes this gate may not regress.
with engine.begin() as connection:
    persistence = prove_customer_persistence(
        connection=connection, organization_id=DEMO
    )
out["customer_persistence_live"] = bool(persistence["customer_persistence_live"])
out["persistence_rows_left_live"] = int(persistence["rows_left_live"])

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

# Real HTTP against the running server, not an in-process client.
import httpx

with httpx.Client(
    base_url=os.environ.get("NF_BACKEND", "http://127.0.0.1:8000"), timeout=20.0
) as client:
    smoke = run_document_storage_route_smoke(
        client=client,
        organization_id=DEMO,
        other_organization_id=OTHER,
        session_headers=headers,
    )
out["driven_over"] = "http"

# The RUNTIME readiness: no body route proof, because runtime has no adapter.
readiness = build_document_storage_readiness(
    preflight=preflight,
    adapter_proof=adapter_proof,
    metadata_route_smoke=smoke,
    body_route_smoke=None,
)

for key in (
    "end_to_end_completed",
    "unauthenticated_refused",
    "forged_header_refused",
    "metadata_route_operational",
    "org_scoped_read_write_proved",
    "cross_org_refused",
    "caller_supplied_fields_refused",
    "body_storage_fields_refused",
    "body_storage_readiness_route_operational",
    "unconfigured_blocker_correct",
    "caller_supplied_object_key_refused",
    "archive_preserves_the_row",
    "body_bytes_not_required",
    "external_object_store_contacted",
    "network_calls_to_object_storage",
    "body_bytes_sent",
    "body_bytes_written",
    "real_customer_files_read",
    "real_customer_files_hashed",
    "credential_values_sent",
    "secrets_exposed",
    "real_customer_data_written",
    "real_organization_touched",
):
    out[key] = smoke[key]
out["smoke_notes"] = list(smoke["notes"])
out["smoke_blocked_reasons"] = list(smoke["blocked_reasons"])
out["smoke_invariant_failures"] = document_storage_route_smoke_invariant_failures(smoke)

for key in (
    "document_metadata_operational",
    "document_body_storage_ready",
    "scope",
    "object_store_required_for_metadata",
    "body_bytes_required_for_metadata",
    "production_storage",
    "body_bytes_written_externally",
):
    out[f"readiness_{key}"] = readiness[key]
out["readiness_blocked_reasons"] = list(readiness["blocked_reasons"])
out["readiness_invariant_failures"] = document_storage_readiness_invariant_failures(
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

METADATA="$(get readiness_document_metadata_operational)"
BLOCKER_OK="$(get unconfigured_blocker_correct)"

# ------------------------------------------------------ 5. what must stay true
[ "$(get login_live)" = "True" ] && pass login_live "true" || block login_live "false"
[ "$(get customer_persistence_live)" = "True" ] && pass customer_persistence_live "true" \
  || block customer_persistence_live "false"
[ "$(get accountable_identity_resolved)" = "True" ] && pass accountable_identity "nf_org_memberships" \
  || block accountable_identity "absent"
[ "$(get session_minted)" = "True" ] && pass session_minted "real_signed_session" \
  || block session_minted "$(getlist session_blocked_reasons)"

# ------------------------------------------------ 6. metadata, which must work
for capability in metadata_route_operational org_scoped_read_write_proved \
                  body_storage_readiness_route_operational \
                  archive_preserves_the_row; do
  [ "$(get "$capability")" = "True" ] && pass "capability:$capability" \
    || block "capability_not_proved:$capability"
done
[ "$METADATA" = "True" ] && pass document_metadata_operational "true" \
  || block document_metadata_operational "false"
[ "$(get end_to_end_completed)" = "True" ] && pass end_to_end_document_smoke "all_routes" \
  || block end_to_end_document_smoke "did_not_complete"

# --------------------------------- 7. the body blocker, which must be CORRECT
#
# The expected answer is "refused, by name". A blocker that stopped bounding
# would be the failure here - not the refusal itself.
[ "$BLOCKER_OK" = "True" ] && pass body_storage_blocker_correct \
  "document_body_storage_is_not_configured" \
  || block body_storage_blocker_correct "the_blocker_was_not_what_it_should_be"

for refusal in unauthenticated_refused forged_header_refused cross_org_refused \
               caller_supplied_fields_refused body_storage_fields_refused \
               caller_supplied_object_key_refused; do
  [ "$(get "$refusal")" = "True" ] && pass "refusal:$refusal" \
    || fail "refusal:$refusal" "$(get "$refusal")"
done

# ------------------------------------------------------ 8. nothing was touched
for field in external_object_store_contacted credential_values_sent \
             secrets_exposed real_customer_data_written \
             real_organization_touched object_store_configured \
             readiness_document_body_storage_ready \
             readiness_production_storage \
             readiness_object_store_required_for_metadata \
             readiness_body_bytes_required_for_metadata; do
  value="$(get "$field")"
  [ "$value" = "False" ] && pass "stays_false:$field" \
    || fail "stays_false:$field" "$value"
done

for field in network_calls_to_object_storage body_bytes_sent body_bytes_written \
             real_customer_files_read real_customer_files_hashed \
             readiness_body_bytes_written_externally \
             persistence_rows_left_live; do
  value="$(get "$field")"
  echo "count=$field n=$value"
  [ "$value" = "0" ] && pass "stays_zero:$field" || fail "stays_zero:$field" "$value"
done

[ "$(get body_bytes_not_required)" = "True" ] && pass metadata_needs_no_body_bytes \
  || fail metadata_needs_no_body_bytes "$(get body_bytes_not_required)"

# ------------------------------ 9. the fake adapter, which proves the code only
[ "$(get hermetic_fake_passed)" = "True" ] && pass hermetic_fake_adapter "passed" \
  || fail hermetic_fake_adapter "$(getlist adapter_checks_failed)"

echo "preflight_state=$(get preflight_state)"
echo "missing_configuration=$(getlist missing_configuration_key_names)"

for inv in preflight_invariant_failures adapter_invariant_failures \
           smoke_invariant_failures readiness_invariant_failures; do
  value="$(getlist "$inv")"
  [ -z "$value" ] && pass "invariants:$inv" "none_failed" || fail "invariants:$inv" "$value"
done

NOTES="$(getlist smoke_notes)"
[ -n "$NOTES" ] && echo "notes=$NOTES"

# ------------------------------------------------------------ 10. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

if [ "$METADATA" = "True" ] && [ "$BLOCKER_OK" = "True" ] && [ -z "$BLOCKERS" ]; then
  echo "RESULT=PASS"
  echo "document_metadata_operational=true"
  echo "document_body_storage_ready=false"
  echo "body_storage_blocker=document_body_storage_is_not_configured"
  echo "object_store_configured=false"
  echo "object_store_contacted=false"
  echo "body_bytes_written=0"
  echo "credentials_required=false"
  echo "credentials_printed=false"
  echo "production_storage=false"
  echo "scope=$(get readiness_scope)"
  exit 0
fi

echo "RESULT=BLOCKED"
echo "document_metadata_operational=$METADATA"
echo "body_storage_blocker_correct=$BLOCKER_OK"
if [ -n "$BLOCKERS" ]; then
  echo "blocker=$BLOCKERS"
else
  echo "blocker=$(getlist readiness_blocked_reasons)"
fi
echo "smoke_blockers=$(getlist smoke_blocked_reasons)"
echo "next=docs/operations/740_GATE141_STORAGE_READINESS_DELTA.md"
exit 1
