#!/usr/bin/env bash
# Gate 147F — is the verified-binding approval boundary exact, and is
# verified_operational_binding honestly false?
#
# RESULT=PASS means the boundary evaluates and every refusal is nameable, with
# verified_operational_binding false. A run in which it came back true without
# an approval object, a qualified principal and live customer auth is a FAILURE
# of this verifier, not a success.
#
# The same distinction Gate 146 drew for customer_auth_live, at a new subject:
#
#   approval_boundary_ready      the boundary evaluates and refuses correctly
#   verified_operational_binding somebody actually satisfied it
#
# RESULT=BLOCKED is reserved for the boundary being unable to evaluate - the
# backend down, the classification unreadable, or an invariant failing.
#
# NOTHING IS APPROVED AND NOTHING IS WRITTEN. No binding row, no approval
# record, no audit event. The real organization is counted, never addressed. No
# live source is called, no mail is sent, no object store is contacted.
#
# No secrets, tokens, cookies, state, PKCE verifier, provider subject, API keys
# or addresses. Counts, booleans, classification and blocker names only.
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

echo "verify=verified_binding_approval_boundary"

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

# -------------------------------- 2. the boundary, evaluated against the live DB
REPORT="$(
  .venv/bin/python - "$DEMO_ORG" <<'PYEOF' 2>/dev/null || true
import json
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa

from nativeforge.lib.settings import get_settings
from nativeforge.services.membership_invite_repository_service import (
    build_invite_binding_evidence,
)
from nativeforge.services.tenant_customer_org_binding_repository_service import (
    get_active_binding,
)
from nativeforge.services.verified_operational_binding_activation_boundary_service import (  # noqa: E501
    build_verified_binding_dry_run_decision,
    dry_run_decision_invariant_failures,
)
from nativeforge.services.verified_operational_binding_approval_checklist_service import (  # noqa: E501
    approval_checklist_invariant_failures,
    build_approval_checklist,
)

DEMO = sys.argv[1]
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
FIXTURE = "dddddddd-eeee-ffff-0000-111111111147"
TABLE = "nf_tenant_customer_org_bindings"

out = {}
engine = sa.create_engine(get_settings().database_url)
with engine.connect() as connection:
    invite = build_invite_binding_evidence(connection=connection)
    auth_live = bool(invite.get("invite_binding_passed"))
    read = get_active_binding(connection=connection, organization_id=DEMO)

    def org_type(org):
        row = connection.execute(
            sa.text("SELECT org_type FROM organizations WHERE id = :i"),
            {"i": org.replace("-", "")},
        ).first()
        return str(row[0]) if row and row[0] is not None else None

    # The real organization is COUNTED, never addressed. A row count is not a
    # binding attempt.
    out["real_org_binding_rows"] = connection.execute(
        sa.text("SELECT count(*) FROM " + TABLE + " WHERE organization_id = :i"),
        {"i": REAL.replace("-", "")},
    ).scalar()
    out["verified_binding_rows"] = connection.execute(
        sa.text(
            "SELECT count(*) FROM " + TABLE
            + " WHERE binding_status = 'verified_binding'"
        )
    ).scalar()
    out["demo_org_type"] = org_type(DEMO)
    out["real_org_type"] = org_type(REAL)

demo = build_approval_checklist(
    organization_id=DEMO, org_type_in_database=out["demo_org_type"],
    binding_read=read, customer_auth_live=auth_live,
)
real = build_approval_checklist(
    organization_id=REAL, org_type_in_database=out["real_org_type"],
    customer_auth_live=auth_live,
)
# The caller lying about classification must change nothing.
lied = build_approval_checklist(
    organization_id=DEMO, org_type_in_database=out["demo_org_type"],
    customer_auth_live=auth_live, is_demo=False, org_type="real", tenant_id="t",
)
# The real org listed in the injectable set must still be refused.
injected = build_approval_checklist(
    organization_id=REAL, org_type_in_database=out["real_org_type"],
    customer_auth_live=auth_live,
    authorized_organization_ids=frozenset({REAL}),
)
dry = build_verified_binding_dry_run_decision(
    organization_id=DEMO, org_type_in_database=out["demo_org_type"],
    binding_read=read, customer_auth_live=auth_live,
)
# The permitted branch, against a fixture organization that is neither the
# demo org nor the real one. Kept reachable so every refusal above it stays
# falsifiable - Gate 134F's lesson.
granted = build_verified_binding_dry_run_decision(
    organization_id=FIXTURE, org_type_in_database="real",
    approval={
        "organization_id": FIXTURE, "authorized_by": "verifier_fixture",
        "authorization_scope": "real_org_binding_activation",
        "environment": "local", "recorded_at": "2026-01-01T00:00:00+00:00",
    },
    app_env="local",
    principal={"role": "platform_admin", "authenticated": True,
               "verified_org": True},
    customer_auth_live=True,
    authorized_organization_ids=frozenset({FIXTURE}),
    binding_read={"rows_matched": 0, "blocked_reasons": []},
)

out.update({
    "customer_auth_live": auth_live,
    "verified_operational_binding": demo["verified_operational_binding"],
    "approval_boundary_ready": demo["approval_boundary_ready"],
    "demo_classification": demo["classification"],
    "demo_classification_source": demo["classification_source"],
    "demo_blockers": demo["blockers"],
    "demo_refused": (
        "demo_organization_is_never_a_verified_operational_binding"
        in demo["blockers"]
    ),
    "real_refused": (
        "organization_is_the_explicitly_refused_real_org" in real["blockers"]
    ),
    "injected_real_still_refused": (
        "organization_is_the_explicitly_refused_real_org"
        in injected["blockers"]
    ),
    "lie_changed_nothing": (
        lied["classification"] == "demo"
        and lied["verified_operational_binding"] is False
    ),
    "lied_keys_refused": sorted(
        lied["offered_authority_keys_refused"]
        + lied["offered_classification_keys_refused"]
    ),
    "dry_run_may_attempt": dry["may_attempt_binding"],
    "dry_run_mutation_enabled": dry["mutation_enabled"],
    "dry_run_mutation_performed": dry["mutation_performed"],
    "dry_run_rows_written": dry["rows_written"],
    "dry_run_blockers": dry["blockers"],
    "granted_branch_reachable": granted["may_attempt_binding"],
    "granted_branch_rows_written": granted["rows_written"],
    "binding_written": demo["binding_written_by_this_module"],
    "approval_granted": demo["approval_granted_by_this_module"],
    "real_organization_touched": demo["real_organization_touched"],
    "mutation_path_enabled": demo["mutation_path_enabled"],
    "leaked_shapes": demo["leaked_shapes"],
    "checklist_invariant_failures": (
        approval_checklist_invariant_failures(demo)
        + approval_checklist_invariant_failures(real)
        + approval_checklist_invariant_failures(injected)
    ),
    "dry_run_invariant_failures": (
        dry_run_decision_invariant_failures(dry)
        + dry_run_decision_invariant_failures(granted)
    ),
})
print(json.dumps(out, sort_keys=True))
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

# ------------------------------------------------------------- 3. the counts
for key in real_org_binding_rows verified_binding_rows; do
  echo "count=$key n=$(get "$key")"
done
info demo_org_type "$(get demo_org_type)"
info real_org_type "$(get real_org_type)"
info customer_auth_live "$(get customer_auth_live)"

# ------------------------------------------------- 4. the lane stays false
if [ "$(get verified_operational_binding)" = "False" ]; then
  pass verified_operational_binding_false
else
  fail verified_operational_binding_false "became true"
fi

if [ "$(get approval_boundary_ready)" = "True" ]; then
  pass approval_boundary_ready
else
  fail approval_boundary_ready "boundary could not classify"
fi

# ------------------------------------------------------ 5. the refusals hold
if [ "$(get demo_refused)" = "True" ]; then
  pass demo_organization_refused "categorically"
else
  fail demo_organization_refused "not refused"
fi

if [ "$(get demo_classification_source)" = "module_constant" ] ||
   [ "$(get demo_classification_source)" = "database" ]; then
  pass classification_not_from_the_caller "$(get demo_classification_source)"
else
  fail classification_not_from_the_caller "$(get demo_classification_source)"
fi

if [ "$(get real_refused)" = "True" ]; then
  pass real_organization_refused "by_name"
else
  fail real_organization_refused "not refused"
fi

if [ "$(get injected_real_still_refused)" = "True" ]; then
  pass injected_authorized_set_cannot_reach_the_real_org
else
  fail injected_authorized_set_cannot_reach_the_real_org "it reached it"
fi

if [ "$(get lie_changed_nothing)" = "True" ]; then
  pass caller_supplied_classification_ignored "$(getlist lied_keys_refused)"
else
  fail caller_supplied_classification_ignored "a caller label changed the answer"
fi

# ----------------------------------------------- 6. the real org is untouched
if [ "$(get real_org_binding_rows)" = "0" ]; then
  pass real_organization_has_no_binding_row
else
  fail real_organization_has_no_binding_row "n=$(get real_org_binding_rows)"
fi

if [ "$(get verified_binding_rows)" = "0" ]; then
  pass no_verified_binding_row_exists
else
  fail no_verified_binding_row_exists "n=$(get verified_binding_rows)"
fi

# ------------------------------------------------------- 7. the dry run runs
if [ "$(get dry_run_may_attempt)" = "False" ]; then
  pass dry_run_refuses "blockers=$(getlist dry_run_blockers)"
else
  fail dry_run_refuses "it would attempt a binding"
fi

for flag in dry_run_mutation_enabled dry_run_mutation_performed \
  binding_written approval_granted real_organization_touched \
  mutation_path_enabled; do
  if [ "$(get "$flag")" = "False" ]; then
    pass "stays_false:$flag"
  else
    fail "stays_false:$flag" "became true"
  fi
done

for zero in dry_run_rows_written granted_branch_rows_written; do
  if [ "$(get "$zero")" = "0" ]; then
    pass "stays_zero:$zero"
  else
    fail "stays_zero:$zero" "n=$(get "$zero")"
  fi
done

# The permitted branch must be reachable, or every refusal above it is
# unfalsifiable. It is reached against a fixture organization, and it still
# writes nothing.
if [ "$(get granted_branch_reachable)" = "True" ]; then
  pass permitted_branch_reachable "fixture_organization_only"
else
  fail permitted_branch_reachable "unreachable - refusals are unfalsifiable"
fi

# ------------------------------------------------------------- 8. no leaks
if [ "$(getlist leaked_shapes)" = "none" ]; then
  pass no_forbidden_shape_in_payload
else
  fail no_forbidden_shape_in_payload "$(getlist leaked_shapes)"
fi

for inv in checklist_invariant_failures dry_run_invariant_failures; do
  if [ "$(getlist "$inv")" = "none" ]; then
    pass "invariants:$inv" "none_failed"
  else
    fail "invariants:$inv" "$(getlist "$inv")"
  fi
done

# ------------------------------------------------------------- 9. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "approval_boundary_ready=true"
echo "verified_operational_binding=false"
echo "blocker_count=$(printf '%s' "$REPORT" | .venv/bin/python -c "
import json,sys
print(len(json.load(sys.stdin).get('demo_blockers') or []))
" 2>/dev/null)"
echo "blockers=$(getlist demo_blockers)"
echo "demo_org_can_ever_satisfy_this=false"
echo "real_organization_authorized=false"
echo "real_organization_binding_rows=0"
echo "mutation_path_enabled=false"
echo "customer_auth_live=$(get customer_auth_live | tr '[:upper:]' '[:lower:]')"
echo "controlled_customer_pilot=false"
echo "production_rollout=false"
echo "next=docs/operations/769_GATE147_REAL_ORG_BINDING_APPROVAL_REQUIREMENTS.md"
exit 0
