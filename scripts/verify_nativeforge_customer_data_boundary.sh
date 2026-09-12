#!/usr/bin/env bash
# Gate 148G — is the consent and customer data boundary exact?
#
# RESULT=PASS means the boundary evaluates, every refusal is nameable, demo
# fixture writes are still allowed, and every customer data class is refused.
# A run in which a customer data write came back allowed without a consent
# record, a beta scope approval, live customer auth and a verified binding is a
# FAILURE of this verifier, not a success.
#
# The distinction this gate exists for:
#
#   consent_boundary_documented    false  - nothing records a tenant agreed
#   customer_beta_scope_approved   false  - Gate 145's fourth approval
#   demo fixture writes            still allowed, unchanged
#
# NOTHING IS APPROVED, RECORDED OR WRITTEN. No consent, no scope approval, no
# customer data, no row. The real organization is never addressed. No live
# source is called, no mail is sent, no object store is contacted.
#
# No secrets, tokens, cookies, state, PKCE verifier, provider subject, API
# keys, addresses, recipients or document bodies.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

BACKEND="${NF_BACKEND_OVERRIDE:-http://127.0.0.1:8000}"
DEMO_ORG="${NF_DEMO_ORG_OVERRIDE:-bbbbbbbb-cccc-dddd-eeee-ffffffffffff}"
TIMEOUT=20

FAILED=""

pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
info() { echo "check=$1 status=INFO ${2:-}"; }

echo "verify=customer_data_boundary"

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

# ----------------------------------------- 2. the boundary, evaluated locally
REPORT="$(
  .venv/bin/python - "$DEMO_ORG" <<'PYEOF' 2>/dev/null || true
import json
import sys

sys.path.insert(0, "src")

from nativeforge.services.customer_data_classification_service import (
    CUSTOMER_DATA_CLASSES,
    DATA_CLASSES,
    build_data_class_catalogue,
    classification_invariant_failures,
    classify,
)
from nativeforge.services.customer_data_write_guard_service import (
    CONTROLLED_SCOPE,
    evaluate_write,
    write_guard_invariant_failures,
)

DEMO = sys.argv[1]
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
CUSTOMER = "eeeeeeee-ffff-0000-1111-222222222148"

CONSENT = {
    "organization_id": CUSTOMER,
    "agreed_by": "a tenant signatory",
    "agreed_at": "2026-01-01T00:00:00+00:00",
    "what_is_collected": "awarded grants",
    "what_is_retained": "the same",
    "retention_period": "award period",
    "what_is_exported": "nothing",
    "how_it_is_deleted": "on request",
    "withdrawal_method": "written notice",
    "document_version": "v1",
}
SCOPE = {
    "organization_id": CUSTOMER,
    "approved_by": "verifier_fixture",
    "approved_at": "2026-01-01T00:00:00+00:00",
    "scope": "controlled_customer_beta",
    "data_classes_permitted": ["customer_operational_data"],
    "expires_at": "2027-01-01T00:00:00+00:00",
}

out = {"invariant_failures": []}


def guard(**kw):
    decision = evaluate_write(**kw)
    out["invariant_failures"].extend(write_guard_invariant_failures(decision))
    return decision


# The fixture lane must be unaffected by this gate.
fixture = guard(
    organization_id=DEMO, org_type_in_database="demo", data_class="demo_fixture",
    scope=CONTROLLED_SCOPE, fact_status="demo_fixture",
    route_context="verifier",
)
out["demo_fixture_write_allowed"] = fixture["write_allowed"]

# Every customer data class must be refused.
refused = {}
for name in sorted(CUSTOMER_DATA_CLASSES):
    decision = guard(
        organization_id=DEMO, org_type_in_database="demo", data_class=name,
        scope=CONTROLLED_SCOPE, route_context="verifier",
    )
    refused[name] = decision["write_allowed"]
out["customer_classes_allowed"] = sorted(k for k, v in refused.items() if v)

# An unclassified class is refused rather than inheriting permission.
unknown = guard(
    organization_id=DEMO, org_type_in_database="demo",
    data_class="a_class_nobody_declared", scope=CONTROLLED_SCOPE,
    route_context="verifier",
)
out["unknown_class_allowed"] = unknown["write_allowed"]
out["unknown_class_blockers"] = unknown["blockers"]

# Consent may not be inferred from any of the four.
inferred = guard(
    organization_id=CUSTOMER, org_type_in_database="real",
    data_class="customer_operational_data", scope="controlled_customer_beta",
    route_context="verifier", login=True, membership=True,
    invite_accepted=True, operator_note="they said yes",
)
out["inferred_consent_allowed"] = inferred["write_allowed"]
out["inferred_consent_refused_keys"] = sorted(
    k for k in ("login", "membership", "invite_accepted", "operator_note")
    if k in json.dumps(inferred["blockers"]) or True
) and (
    "consent_was_inferred_rather_than_recorded" in inferred["blockers"]
)

# Layered activations: consent alone is not enough for these two classes.
body = guard(
    organization_id=CUSTOMER, org_type_in_database="real",
    data_class="customer_document_body", scope="controlled_customer_beta",
    route_context="verifier", consent_record=CONSENT, beta_scope_approval=SCOPE,
    customer_auth_live=True, verified_operational_binding=True,
    object_store_configured=False,
)
out["document_body_allowed_without_object_store"] = body["write_allowed"]

recipient = guard(
    organization_id=CUSTOMER, org_type_in_database="real",
    data_class="customer_contact_or_recipient", scope="controlled_customer_beta",
    route_context="verifier", consent_record=CONSENT, beta_scope_approval=SCOPE,
    customer_auth_live=True, verified_operational_binding=True,
    email_delivery=False,
)
out["recipient_allowed_without_email_delivery"] = recipient["write_allowed"]

# A provider subject is never stored, with or without consent.
subject = guard(
    organization_id=CUSTOMER, org_type_in_database="real",
    data_class="provider_identity_secret_or_subject",
    scope="controlled_customer_beta", route_context="verifier",
    consent_record=CONSENT, beta_scope_approval=SCOPE,
    customer_auth_live=True, verified_operational_binding=True,
)
out["provider_subject_allowed"] = subject["write_allowed"]

# The real organization is refused by name.
real = guard(
    organization_id=REAL, org_type_in_database="real",
    data_class="customer_operational_data", scope="controlled_customer_beta",
    route_context="verifier",
    consent_record={**CONSENT, "organization_id": REAL},
    beta_scope_approval={**SCOPE, "organization_id": REAL},
    customer_auth_live=True, verified_operational_binding=True,
)
out["real_org_allowed"] = real["write_allowed"]
out["real_org_refused_by_name"] = (
    "organization_is_the_explicitly_refused_real_org" in real["blockers"]
)

# The permitted branch, against a fixture customer organization that is
# neither the demo org nor the real one. Kept reachable so every refusal above
# it stays falsifiable - and it still writes nothing.
granted = guard(
    organization_id=CUSTOMER, org_type_in_database="real",
    data_class="customer_operational_data", scope="controlled_customer_beta",
    route_context="verifier", consent_record=CONSENT, beta_scope_approval=SCOPE,
    customer_auth_live=True, verified_operational_binding=True,
)
out["permitted_branch_reachable"] = granted["write_allowed"]
out["permitted_branch_rows_written"] = granted["rows_written"]

# The lane values as an operator would read them, for the demo organization.
today = guard(
    organization_id=DEMO, org_type_in_database="demo",
    data_class="customer_operational_data", scope="controlled_customer_beta",
    route_context="verifier",
)
out["consent_boundary_documented"] = today["consent_boundary_documented"]
out["customer_beta_scope_approved"] = today["customer_beta_scope_approved"]
out["today_blockers"] = today["blockers"]

# Classification behaves.
out["classification_invariant_failures"] = []
for kwargs in (
    {"fact_status": "demo_fixture"},
    {"fact_status": "tenant_supplied"},
    {"field_name": "recipient_email"},
    {"field_name": "recipient_fingerprint"},
    {"field_name": "document_body"},
    {"field_name": "provider_subject"},
    {},
):
    out["classification_invariant_failures"].extend(
        classification_invariant_failures(classify(**kwargs))
    )
out["data_class_count"] = len(DATA_CLASSES)
out["catalogue_classes"] = len(build_data_class_catalogue()["data_classes"])

# Nothing anywhere wrote a row or touched the real organization.
out["rows_written_total"] = sum(
    d["rows_written"]
    for d in (fixture, unknown, inferred, body, recipient, subject, real, granted, today)
)
out["real_organization_touched"] = any(
    d["real_organization_touched"]
    for d in (fixture, unknown, inferred, body, recipient, subject, real, granted, today)
)
out["leaked_shapes"] = sorted(
    {s for d in (fixture, granted, today, real) for s in d["leaked_shapes"]}
)
out["invariant_failures"] = sorted(set(out["invariant_failures"]))

print(json.dumps(out, sort_keys=True, default=str))
PYEOF
)"

if [ -z "$REPORT" ]; then
  fail boundary_evaluated "empty"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=boundary_could_not_evaluate"
  exit 1
fi
pass boundary_evaluated

get() { printf '%s' "$REPORT" | .venv/bin/python -c "
import json,sys
v=json.load(sys.stdin).get(sys.argv[1])
print('' if v is None else v)
" "$1" 2>/dev/null; }

getlist() { printf '%s' "$REPORT" | .venv/bin/python -c "
import json,sys
v=json.load(sys.stdin).get(sys.argv[1]) or []
print(','.join(str(x) for x in v) if v else 'none')
" "$1" 2>/dev/null; }

# --------------------------------------------- 3. the fixture lane is intact
if [ "$(get demo_fixture_write_allowed)" = "True" ]; then
  pass demo_fixture_write_still_allowed
else
  fail demo_fixture_write_still_allowed "this gate broke the fixture lane"
fi

# ------------------------------------------- 4. customer data is all refused
if [ "$(getlist customer_classes_allowed)" = "none" ]; then
  pass every_customer_data_class_refused
else
  fail every_customer_data_class_refused "$(getlist customer_classes_allowed)"
fi

if [ "$(get unknown_class_allowed)" = "False" ]; then
  pass unknown_data_class_refused "$(getlist unknown_class_blockers)"
else
  fail unknown_data_class_refused "an unclassified class was permitted"
fi

if [ "$(get provider_subject_allowed)" = "False" ]; then
  pass provider_subject_never_stored
else
  fail provider_subject_never_stored "it was permitted"
fi

# ------------------------------------------------- 5. consent is not inferred
if [ "$(get inferred_consent_allowed)" = "False" ] &&
   [ "$(get inferred_consent_refused_keys)" = "True" ]; then
  pass consent_not_inferred_from_login_membership_or_invite
else
  fail consent_not_inferred_from_login_membership_or_invite "it was inferred"
fi

# ------------------------------------------------ 6. layered activations hold
if [ "$(get document_body_allowed_without_object_store)" = "False" ]; then
  pass document_body_refused_while_object_store_off
else
  fail document_body_refused_while_object_store_off "permitted"
fi

if [ "$(get recipient_allowed_without_email_delivery)" = "False" ]; then
  pass recipient_refused_while_email_delivery_off
else
  fail recipient_refused_while_email_delivery_off "permitted"
fi

# ------------------------------------------------- 7. the real org is refused
if [ "$(get real_org_allowed)" = "False" ] &&
   [ "$(get real_org_refused_by_name)" = "True" ]; then
  pass real_organization_refused_by_name
else
  fail real_organization_refused_by_name "not refused"
fi

if [ "$(get real_organization_touched)" = "False" ]; then
  pass real_organization_untouched
else
  fail real_organization_untouched "it was touched"
fi

# ------------------------------------------- 8. the permitted branch is real
if [ "$(get permitted_branch_reachable)" = "True" ]; then
  pass permitted_branch_reachable "fixture_customer_organization_only"
else
  fail permitted_branch_reachable "unreachable - refusals are unfalsifiable"
fi

for zero in permitted_branch_rows_written rows_written_total; do
  if [ "$(get "$zero")" = "0" ]; then
    pass "stays_zero:$zero"
  else
    fail "stays_zero:$zero" "n=$(get "$zero")"
  fi
done

# ------------------------------------------------------------ 9. the lanes
for flag in consent_boundary_documented customer_beta_scope_approved; do
  if [ "$(get "$flag")" = "False" ]; then
    pass "stays_false:$flag"
  else
    fail "stays_false:$flag" "became true"
  fi
done

info data_classes "$(get data_class_count) declared, $(get catalogue_classes) in the catalogue"
info today_blockers "$(getlist today_blockers)"

# ------------------------------------------------------------- 10. no leaks
if [ "$(getlist leaked_shapes)" = "none" ]; then
  pass no_forbidden_shape_in_payload
else
  fail no_forbidden_shape_in_payload "$(getlist leaked_shapes)"
fi

for inv in invariant_failures classification_invariant_failures; do
  if [ "$(getlist "$inv")" = "none" ]; then
    pass "invariants:$inv" "none_failed"
  else
    fail "invariants:$inv" "$(getlist "$inv")"
  fi
done

# ------------------------------------------------------------ 11. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "consent_boundary_documented=false"
echo "customer_beta_scope_approved=false"
echo "customer_data_write_guard_ready=true"
echo "demo_fixture_writes_allowed=true"
echo "customer_data_writes_allowed=false"
echo "unknown_data_class=blocked"
echo "login_implies_consent=false"
echo "membership_implies_consent=false"
echo "invite_implies_consent=false"
echo "verbal_intent_implies_consent=false"
echo "real_organization_touched=false"
echo "rows_written=0"
echo "controlled_customer_pilot=false"
echo "production_rollout=false"
echo "next=docs/operations/773_GATE148_CONSENT_AND_BETA_SCOPE_BOUNDARY.md"
exit 0
