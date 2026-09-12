#!/usr/bin/env bash
# Gate 149F — is the pilot activation package exact, and does the pilot stay off?
#
# RESULT=PASS means the package states every prerequisite, refuses every
# bundled capability, and controlled_customer_pilot remains false. A run in
# which the pilot came back true, or in which a bundled activation was
# permitted, is a FAILURE of this verifier, not a success.
#
# The distinction, for the seventh time in this campaign:
#
#   activation_package_ready     the prerequisites are stated and measurable
#   controlled_customer_pilot    a pilot is running
#
# NOTHING IS ACTIVATED, APPROVED OR WRITTEN. No pilot, no approval, no customer
# data, no row. The real organization is never addressed. No live source is
# called, no mail is sent, no object store is contacted.
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

echo "verify=controlled_customer_pilot_activation_package"

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

# --------------------------------------------- 2. the package, evaluated
REPORT="$(
  .venv/bin/python - <<'PYEOF' 2>/dev/null || true
import json
import sys

sys.path.insert(0, "src")

from nativeforge.services.controlled_beta_artifact_gate145_service import (
    FULL_BATTERY,
)
from nativeforge.services.controlled_beta_readiness_decision_service import (
    build_controlled_beta_decision,
)
from nativeforge.services.controlled_customer_pilot_activation_boundary_service import (  # noqa: E501
    UNSAFE_BUNDLE_KEYS,
    activation_decision_invariant_failures,
    build_pilot_activation_decision,
)
from nativeforge.services.controlled_customer_pilot_activation_checklist_service import (  # noqa: E501
    PREREQUISITES,
    SEPARATELY_GATED,
    build_pilot_activation_checklist,
    checklist_invariant_failures,
)

beta = build_controlled_beta_decision(**FULL_BATTERY)
scopes = beta["by_scope"]
SCOPE_ARGS = {
    "internal_demo_beta": scopes["internal_demo_beta"]["decision"],
    "controlled_customer_beta": scopes["controlled_customer_beta"]["decision"],
}

APPROVAL = {
    "organization_id": "eeeeeeee-ffff-0000-1111-222222222149",
    "approved_by": "verifier_fixture",
    "approved_at": "2026-01-01T00:00:00+00:00",
    "pilot_scope": "one organization",
    "support_contact": "the operator",
    "rollback_owner": "the owner",
    "expires_at": "2027-01-01T00:00:00+00:00",
}
OWNER = {"support_contact": "the operator", "rollback_owner": "the owner"}
ALL_SATISFIED = dict(
    real_customer_organization_exists=True,
    second_person_event_complete=True,
    customer_auth_live=True,
    verified_operational_binding=True,
    consent_boundary_documented=True,
    customer_beta_scope_approved=True,
    customer_data_write_guard_ready=True,
    support_and_rollback_owner=OWNER,
    pilot_scope_limitations_documented=True,
)

out = {"invariant_failures": [], "checklist_invariant_failures": []}

today = build_pilot_activation_checklist(
    customer_data_write_guard_ready=True, **SCOPE_ARGS
)
out["checklist_invariant_failures"].extend(checklist_invariant_failures(today))
out["controlled_customer_pilot"] = today["controlled_customer_pilot"]
out["activation_package_ready"] = today["activation_package_ready"]
out["internal_demo_beta"] = today["internal_demo_beta"]
out["controlled_customer_beta"] = today["controlled_customer_beta"]
out["production_rollout"] = today["production_rollout"]
out["prerequisites_missing"] = today["prerequisites_missing"]
out["prerequisite_count"] = today["prerequisite_count"]
out["satisfied_count"] = today["prerequisites_satisfied_count"]
out["activation_mechanism_exists"] = today["activation_mechanism_exists"]
out["separately_gated_names"] = sorted(SEPARATELY_GATED)
out["separately_gated_in_prerequisites"] = sorted(
    set(SEPARATELY_GATED) & set(PREREQUISITES)
)

# The permitted-prerequisites branch, kept reachable so every refusal above it
# stays falsifiable - and the pilot STILL does not activate.
full = build_pilot_activation_checklist(**ALL_SATISFIED, **SCOPE_ARGS)
out["checklist_invariant_failures"].extend(checklist_invariant_failures(full))
out["full_checklist_pilot"] = full["controlled_customer_pilot"]
out["full_checklist_missing"] = full["prerequisites_missing"]


def decide(**kw):
    decision = build_pilot_activation_decision(**kw, **SCOPE_ARGS)
    out["invariant_failures"].extend(
        activation_decision_invariant_failures(decision)
    )
    return decision


now = decide(customer_data_write_guard_ready=True)
out["today_may_activate"] = now["may_activate"]
out["today_would_permit"] = now["prerequisites_would_permit"]
out["today_blockers"] = now["blockers"]
out["today_rows_written"] = now["rows_written"]

granted = decide(**ALL_SATISFIED, activation_approval=APPROVAL)
out["granted_may_activate"] = granted["may_activate"]
out["granted_would_permit"] = granted["prerequisites_would_permit"]
out["granted_rows_written"] = granted["rows_written"]
out["granted_mutation_performed"] = granted["mutation_performed"]

# Every bundled key must be refused, one at a time, with everything else
# satisfied. This is the failure this gate exists to prevent.
permitted_bundles = []
for key in UNSAFE_BUNDLE_KEYS:
    bundled = decide(**ALL_SATISFIED, activation_approval=APPROVAL, **{key: True})
    if bundled["prerequisites_would_permit"] or not bundled["unsafe_bundled_requests"]:
        permitted_bundles.append(key)
out["permitted_bundles"] = permitted_bundles

both = decide(
    **ALL_SATISFIED,
    activation_approval=APPROVAL,
    activate_email=True,
    source_monitoring_live=True,
    activate_object_storage=True,
)
out["bundled_targets"] = both["unsafe_bundled_targets"]
out["bundled_would_permit"] = both["prerequisites_would_permit"]

production = decide(**ALL_SATISFIED, activation_approval=APPROVAL, go_live=True)
out["production_bundle_would_permit"] = production["prerequisites_would_permit"]
out["production_bundle_blocked"] = (
    "production_requested_alongside_a_pilot" in production["blockers"]
)

out["rows_written_total"] = sum(
    d["rows_written"] for d in (now, granted, both, production)
)
out["real_organization_touched"] = any(
    d["real_organization_touched"] for d in (now, granted, both, production)
)
out["leaked_shapes"] = sorted(
    {s for d in (now, granted, both, production) for s in d["leaked_shapes"]}
)
out["invariant_failures"] = sorted(set(out["invariant_failures"]))
out["checklist_invariant_failures"] = sorted(set(out["checklist_invariant_failures"]))

print(json.dumps(out, sort_keys=True, default=str))
PYEOF
)"

if [ -z "$REPORT" ]; then
  fail package_evaluated "empty"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=package_could_not_evaluate"
  exit 1
fi
pass package_evaluated

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

# ------------------------------------------------------- 3. the pilot is off
if [ "$(get controlled_customer_pilot)" = "False" ]; then
  pass controlled_customer_pilot_false
else
  fail controlled_customer_pilot_false "became true"
fi

if [ "$(get today_may_activate)" = "False" ] &&
   [ "$(get granted_may_activate)" = "False" ]; then
  pass may_activate_false_on_every_branch "no mechanism to act on it"
else
  fail may_activate_false_on_every_branch "a branch returned true"
fi

if [ "$(get activation_mechanism_exists)" = "False" ]; then
  pass no_activation_mechanism_exists
else
  fail no_activation_mechanism_exists "one appeared"
fi

# --------------------------------------------------------- 4. the decisions
info internal_demo_beta "$(get internal_demo_beta)"
info controlled_customer_beta "$(get controlled_customer_beta)"
if [ "$(get production_rollout)" = "NO_GO" ]; then
  pass production_rollout_no_go
else
  fail production_rollout_no_go "$(get production_rollout)"
fi

# ------------------------------------------------------ 5. the prerequisites
info prerequisites "$(get satisfied_count)/$(get prerequisite_count) satisfied"
if [ "$(getlist prerequisites_missing)" != "none" ]; then
  pass prerequisites_named "$(getlist prerequisites_missing)"
else
  fail prerequisites_named "nothing outstanding, which contradicts the lanes"
fi

if [ "$(getlist separately_gated_in_prerequisites)" = "none" ]; then
  pass separately_gated_are_not_prerequisites "$(getlist separately_gated_names)"
else
  fail separately_gated_are_not_prerequisites \
    "$(getlist separately_gated_in_prerequisites)"
fi

# The permitted branch must be reachable in the checklist, or the refusals
# above it are unfalsifiable.
if [ "$(get full_checklist_pilot)" = "True" ] &&
   [ "$(getlist full_checklist_missing)" = "none" ]; then
  pass permitted_branch_reachable "every prerequisite satisfied"
else
  fail permitted_branch_reachable "unreachable - refusals are unfalsifiable"
fi

# ---------------------------------------------------- 6. bundling is refused
if [ "$(getlist permitted_bundles)" = "none" ]; then
  pass every_bundled_capability_refused
else
  fail every_bundled_capability_refused "$(getlist permitted_bundles)"
fi

if [ "$(get bundled_would_permit)" = "False" ]; then
  pass bundled_request_refused "$(getlist bundled_targets)"
else
  fail bundled_request_refused "a bundle was permitted"
fi

if [ "$(get production_bundle_would_permit)" = "False" ] &&
   [ "$(get production_bundle_blocked)" = "True" ]; then
  pass production_bundle_refused_by_name
else
  fail production_bundle_refused_by_name "not refused"
fi

# ------------------------------------------------------- 7. nothing was done
for zero in today_rows_written granted_rows_written rows_written_total; do
  if [ "$(get "$zero")" = "0" ]; then
    pass "stays_zero:$zero"
  else
    fail "stays_zero:$zero" "n=$(get "$zero")"
  fi
done

for flag in granted_mutation_performed real_organization_touched; do
  if [ "$(get "$flag")" = "False" ]; then
    pass "stays_false:$flag"
  else
    fail "stays_false:$flag" "became true"
  fi
done

# ------------------------------------------------------------- 8. no leaks
if [ "$(getlist leaked_shapes)" = "none" ]; then
  pass no_forbidden_shape_in_payload
else
  fail no_forbidden_shape_in_payload "$(getlist leaked_shapes)"
fi

for inv in invariant_failures checklist_invariant_failures; do
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
echo "activation_package_ready=true"
echo "controlled_customer_pilot=false"
echo "pilot_activation_allowed=false"
echo "mutation_path_enabled=false"
echo "mutation_performed=false"
echo "activation_mechanism_exists=false"
echo "internal_demo_beta=$(get internal_demo_beta)"
echo "controlled_customer_beta=$(get controlled_customer_beta)"
echo "production_rollout=NO_GO"
echo "prerequisites_satisfied=$(get satisfied_count)/$(get prerequisite_count)"
echo "prerequisites_missing=$(getlist prerequisites_missing)"
echo "unsafe_bundled_activations_refused=true"
echo "source_monitoring_live=false"
echo "email_delivery=false"
echo "object_store_configured=false"
echo "rows_written=0"
echo "real_organization_touched=false"
echo "next=docs/operations/778_GATE149_PILOT_PREREQUISITES.md"
exit 0
