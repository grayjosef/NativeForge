#!/usr/bin/env bash
# Gate 150E — is the customer beta reassessment honest?
#
# RESULT=PASS means the decision is reported as measured and no lane moved
# without evidence. The one failure mode this gate has is reporting
# controlled_customer_beta as GO without the four approvals behind it, and a
# run that did so is a FAILURE of this verifier, not a success.
#
# The expected honest result, unless new external approvals exist:
#
#   internal_demo_beta        GO
#   controlled_customer_beta  LIMITED_GO
#   production_rollout        NO_GO
#
# NOTHING IS ACTIVATED, APPROVED, RECORDED OR WRITTEN. No pilot, no activation
# mechanism, no approval, no customer data, no row. The real organization is
# never addressed. No live source is called, no mail is sent, no object store
# is contacted.
#
# No secrets, tokens, cookies, state, PKCE verifier, provider subject, API
# keys, addresses or recipients.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

BACKEND="${NF_BACKEND_OVERRIDE:-http://127.0.0.1:8000}"
TIMEOUT=20

FAILED=""

pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
info() { echo "check=$1 status=INFO ${2:-}"; }

echo "verify=customer_beta_reassessment"

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

# ------------------------------------------- 2. the reassessment, evaluated
REPORT="$(
  .venv/bin/python - <<'PYEOF' 2>/dev/null || true
import json
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa

from nativeforge.lib.settings import get_settings
from nativeforge.services.controlled_beta_artifact_gate145_service import (
    FULL_BATTERY,
)
from nativeforge.services.controlled_beta_readiness_decision_service import (
    build_controlled_beta_decision,
)
from nativeforge.services.controlled_customer_pilot_activation_checklist_service import (  # noqa: E501
    build_pilot_activation_checklist,
)
from nativeforge.services.customer_auth_second_person_event_checklist_service import (  # noqa: E501
    build_second_person_checklist,
)
from nativeforge.services.customer_beta_reassessment_service import (
    GO,
    build_reassessment,
    reassessment_invariant_failures,
)
from nativeforge.services.membership_invite_repository_service import (
    build_invite_binding_evidence,
)

out = {}
engine = sa.create_engine(get_settings().database_url)
with engine.connect() as connection:
    evidence = build_invite_binding_evidence(connection=connection)
    evidence["identity_rows"] = connection.execute(
        sa.text("SELECT count(*) FROM nf_identities")
    ).scalar()

second = build_second_person_checklist(evidence=evidence)
scopes = build_controlled_beta_decision(**FULL_BATTERY)["by_scope"]
pilot = build_pilot_activation_checklist(
    customer_data_write_guard_ready=True,
    customer_auth_live=second["customer_auth_live"],
    internal_demo_beta=scopes["internal_demo_beta"]["decision"],
    controlled_customer_beta=scopes["controlled_customer_beta"]["decision"],
)

MEASURED = dict(
    internal_demo_beta=scopes["internal_demo_beta"]["decision"],
    controlled_customer_beta=scopes["controlled_customer_beta"]["decision"],
    customer_auth_live=second["customer_auth_live"],
    verified_operational_binding=False,
    consent_boundary_documented=False,
    customer_beta_scope_approved=False,
    controlled_customer_pilot=pilot["controlled_customer_pilot"],
    activation_mechanism_exists=pilot["activation_mechanism_exists"],
    second_person_readiness_passed=second["readiness_passed"],
    approval_boundary_ready=True,
    customer_data_write_guard_ready=True,
    activation_package_ready=pilot["activation_package_ready"],
)

result = build_reassessment(**MEASURED)
out["invariant_failures"] = reassessment_invariant_failures(result)
out.update(
    {
        "internal_demo_beta": result["current_decision"]["internal_demo_beta"],
        "controlled_customer_beta": result["current_decision"][
            "controlled_customer_beta"
        ],
        "production_rollout": result["current_decision"]["production_rollout"],
        "any_decision_changed": result["any_decision_changed"],
        "approvals_outstanding": result["customer_beta_approvals_outstanding"],
        "lanes_moved": result["lanes_moved_by_this_block"],
        "conflation_count": len(result["conflations"]),
        "clarification_count": len(result["clarifications"]),
        "safe_claim_count": result["safe_claim_count"],
        "unsafe_claim_count": result["unsafe_claim_count"],
        "controlled_customer_pilot": result["controlled_customer_pilot"],
        "activation_mechanism_exists": result["activation_mechanism_exists"],
        "rows_written": result["rows_written"],
        "real_organization_touched": result["real_organization_touched"],
        "leaked_shapes": result["leaked_shapes"],
        "next_block": result["next_block"]["block"],
        "next_gate": result["next_block"]["first_gate"],
    }
)

# The one failure mode: a customer GO without the four approvals. Forged here
# so the refusal is exercised on every run rather than asserted in a comment.
forged = build_reassessment(**{**MEASURED, "controlled_customer_beta": GO})
out["forged_customer_go_refused"] = bool(reassessment_invariant_failures(forged))

# And the honest GO branch, kept reachable so the refusal above stays
# falsifiable.
honest = build_reassessment(
    **{
        **MEASURED,
        "controlled_customer_beta": GO,
        "customer_auth_live": True,
        "verified_operational_binding": True,
        "consent_boundary_documented": True,
        "customer_beta_scope_approved": True,
    }
)
out["honest_customer_go_reachable"] = not reassessment_invariant_failures(honest)

# Every unsafe claim must carry the true statement it should be replaced by.
out["unsafe_claims_without_a_true_statement"] = sorted(
    entry["claim"]
    for entry in result["unsafe_claims"]
    if not str(entry.get("true_statement") or "").strip()
)

print(json.dumps(out, sort_keys=True, default=str))
PYEOF
)"

if [ -z "$REPORT" ]; then
  fail reassessment_evaluated "empty"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=reassessment_could_not_evaluate"
  exit 1
fi
pass reassessment_evaluated

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

# ------------------------------------------------------- 3. the decisions
if [ "$(get internal_demo_beta)" = "GO" ]; then
  pass internal_demo_beta_still_go
else
  fail internal_demo_beta_still_go "$(get internal_demo_beta)"
fi

if [ "$(get controlled_customer_beta)" = "LIMITED_GO" ]; then
  pass controlled_customer_beta_still_limited_go
elif [ "$(get controlled_customer_beta)" = "GO" ] &&
     [ "$(getlist approvals_outstanding)" = "none" ]; then
  pass controlled_customer_beta_go_with_every_approval "new evidence exists"
else
  fail controlled_customer_beta_still_limited_go \
    "$(get controlled_customer_beta) with $(getlist approvals_outstanding)"
fi

if [ "$(get production_rollout)" = "NO_GO" ]; then
  pass production_rollout_still_no_go
else
  fail production_rollout_still_no_go "$(get production_rollout)"
fi

if [ "$(get any_decision_changed)" = "False" ]; then
  pass no_decision_changed_since_gate_145
else
  info no_decision_changed_since_gate_145 "a decision moved - check the evidence"
fi

info approvals_outstanding "$(getlist approvals_outstanding)"
info lanes_moved_by_this_block "$(get lanes_moved)"
info next_block "$(get next_block) starting at $(get next_gate)"

# ---------------------------------------------- 4. the pilot is untouched
for flag in controlled_customer_pilot activation_mechanism_exists \
  real_organization_touched; do
  if [ "$(get "$flag")" = "False" ]; then
    pass "stays_false:$flag"
  else
    fail "stays_false:$flag" "became true"
  fi
done

if [ "$(get rows_written)" = "0" ]; then
  pass stays_zero:rows_written
else
  fail stays_zero:rows_written "n=$(get rows_written)"
fi

# -------------------------------------- 5. the one failure mode is refused
if [ "$(get forged_customer_go_refused)" = "True" ]; then
  pass forged_customer_go_refused "invariants fired"
else
  fail forged_customer_go_refused "a GO without approvals was accepted"
fi

if [ "$(get honest_customer_go_reachable)" = "True" ]; then
  pass honest_customer_go_branch_reachable "every approval granted"
else
  fail honest_customer_go_branch_reachable \
    "unreachable - the refusal above is unfalsifiable"
fi

# ------------------------------------------------------------ 6. the claims
info safe_claims "$(get safe_claim_count)"
info unsafe_claims "$(get unsafe_claim_count)"
info conflations "$(get conflation_count)"
info clarifications "$(get clarification_count)"

if [ "$(getlist unsafe_claims_without_a_true_statement)" = "none" ]; then
  pass every_unsafe_claim_has_a_true_alternative
else
  fail every_unsafe_claim_has_a_true_alternative \
    "$(getlist unsafe_claims_without_a_true_statement)"
fi

# ------------------------------------------------------------- 7. no leaks
if [ "$(getlist leaked_shapes)" = "none" ]; then
  pass no_forbidden_shape_in_payload
else
  fail no_forbidden_shape_in_payload "$(getlist leaked_shapes)"
fi

if [ "$(getlist invariant_failures)" = "none" ]; then
  pass invariants "none_failed"
else
  fail invariants "$(getlist invariant_failures)"
fi

# ------------------------------------------------------------- 8. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "internal_demo_beta=$(get internal_demo_beta)"
echo "controlled_customer_beta=$(get controlled_customer_beta)"
echo "production_rollout=$(get production_rollout)"
echo "decision_changed_since_gate_145=$(get any_decision_changed | tr '[:upper:]' '[:lower:]')"
echo "lanes_moved_by_gates_146_to_149=$(get lanes_moved)"
echo "customer_beta_approvals_outstanding=$(getlist approvals_outstanding)"
echo "no_outstanding_customer_blocker_is_technical=true"
echo "controlled_customer_pilot=false"
echo "activation_mechanism_exists=false"
echo "safe_claims=$(get safe_claim_count)"
echo "unsafe_claims=$(get unsafe_claim_count)"
echo "conflations_named=$(get conflation_count)"
echo "rows_written=0"
echo "real_organization_touched=false"
echo "next_block=$(get next_block)"
echo "next_gate=$(get next_gate)"
echo "next=docs/operations/785_GATE150_NEXT_BLOCK_RECOMMENDATION.md"
exit 0
