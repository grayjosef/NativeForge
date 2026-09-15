#!/usr/bin/env bash
# Gate 155F — is the Gates 151-155 closeout honest?
#
# This verifier's job is to fail when the reassessment claims more than the
# block earned. The specific overstatements it is built to catch:
#
#   "four lanes went true"        they did not exist at Gate 150. They were
#                                 CREATED. Nothing that was false became true.
#   "we have backups"             Gate 61/65 still returns SKIP. It is RUN here.
#   "we are monitored"            production_monitoring is false and constant.
#   "the customer beta can start" LIMITED_GO, unchanged since Gate 145.
#   "production is closer"        NO_GO, and no branch computes anything else.
#
# It also enforces the rule the next-block decision must obey: do NOT recommend
# another readiness wrapper around a blocker only a person can clear. The
# recommendation is re-derived here and the rule is checked, not trusted.
#
# NOTHING IS ACTIVATED. No activation mechanism is created, no capability is
# turned on, no lane is changed, no row is written. No mail, no provider, no
# live source, no collector, no object store, no customer data. The real
# organization is refused by name and never read.
#
# No secrets, tokens, cookies, state, PKCE verifier, provider subject, API keys
# or recipient addresses.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

BACKEND="${NF_BACKEND_OVERRIDE:-http://127.0.0.1:8000}"
REAL_ORG="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
TIMEOUT=20

FAILED=""

pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
info() { echo "check=$1 status=INFO ${2:-}"; }

echo "verify=operational_durability_reassessment"

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

# ------------------------------- 2. every prior verifier in the block still passes
#
# Run, not assumed. A closeout that reported the block green while one of its
# own gates had regressed would be the whole failure mode of a closeout gate.
for v in tenant_digest_persistence audit_replay_readiness \
  backup_restore_readiness operational_health_runbook; do
  r="$(timeout 900 bash "scripts/verify_nativeforge_${v}.sh" 2>/dev/null \
    | grep -E '^RESULT=' | tail -1)"
  if [ "$r" = "RESULT=PASS" ]; then
    pass "block_verifier_still_passes:$v"
  else
    fail "block_verifier_still_passes:$v" "${r:-no result}"
  fi
done

# The production backup harness must STILL return SKIP. A PASS here would mean
# somebody provisioned an instance, which changes the whole reassessment.
r="$(timeout 900 bash scripts/verify_nativeforge_backup_restore.sh 2>/dev/null \
  | grep -E '^RESULT=' | tail -1)"
if [ "$r" = "RESULT=SKIP" ]; then
  pass production_backup_harness_still_skip "Gate 61/65 unchanged"
else
  fail production_backup_harness_still_skip "${r:-no result}"
fi

# ------------------------------------------- 3. the reassessment and decision
REPORT="$(
  .venv/bin/python - <<'PYEOF' 2>/dev/null || true
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

from nativeforge.services import (
    operational_durability_artifact_gate155_service as art,
)
from nativeforge.services.beta_onboarding_readiness_summary_service import (
    build_beta_onboarding_summary,
)
from nativeforge.services.next_activation_decision_service import (
    WRAPPER_RISK,
    build_next_activation_decision,
    next_activation_decision_invariant_failures,
)
from nativeforge.services.operational_durability_reassessment_service import (
    DURABILITY_LANES,
    UNCHANGED_FALSE_LANES,
    build_durability_reassessment,
    durability_reassessment_invariant_failures,
)

out = {"invariant_failures": []}

decision = build_next_activation_decision(
    real_customer_org_exists=False,
    second_identity_available=False,
    consent_decision_available=False,
)
out["invariant_failures"].extend(
    next_activation_decision_invariant_failures(decision)
)

reassessment = build_durability_reassessment(
    internal_demo_beta="GO",
    controlled_customer_beta="LIMITED_GO",
    tenant_digest_persistence_live=True,
    audit_replay_ready=True,
    operational_backup_restore_ready=True,
    operational_health_ready=True,
    production_backup_ready=False,
    production_monitoring_active=False,
    controlled_customer_pilot=False,
    activation_mechanism_exists=False,
    customer_auth_live=False,
    verified_operational_binding=False,
    consent_boundary_documented=False,
    customer_beta_scope_approved=False,
    source_monitoring_live=False,
    email_delivery=False,
    object_store_configured=False,
    next_block=decision,
)
out["invariant_failures"].extend(
    durability_reassessment_invariant_failures(reassessment)
)

delta = reassessment["lane_delta"]
out["durability_improved"] = reassessment["operational_durability_improved"]
out["lanes_created_count"] = delta["lanes_created_count"]
out["lanes_proved_count"] = len(delta["lanes_proved"])
out["lanes_proved"] = delta["lanes_proved"]
out["lanes_not_proved"] = delta["lanes_not_proved"]
out["false_to_true"] = delta["lanes_that_were_false_and_became_true"]
out["unchanged_false_count"] = delta["unchanged_false_count"]
out["unchanged_false_true_ones"] = sorted(
    k for k, v in delta["unchanged_false_lanes"].items() if v
)
out["declared_lane_count"] = len(DURABILITY_LANES)
out["must_stay_false_count"] = len(UNCHANGED_FALSE_LANES)

out["customer_beta_decision"] = reassessment["customer_beta_decision"]
out["production_decision"] = reassessment["production_decision"]
out["internal_demo_decision"] = reassessment["internal_demo_decision"]
out["any_decision_changed"] = reassessment["any_decision_changed"]
out["production_backup_ready"] = reassessment["production_durability"][
    "production_backup_ready"
]
out["production_monitoring_active"] = reassessment["production_durability"][
    "production_monitoring_active"
]
out["activation_mechanism_created"] = reassessment["activation_mechanism_created"]
out["anything_activated"] = reassessment["anything_activated"]
out["real_org_touched"] = reassessment["real_organization_touched"]
out["email_sent"] = reassessment["email_sent"]
out["live_source_called"] = reassessment["live_source_called"]
out["object_store_contacted"] = reassessment["object_store_contacted"]
out["rows_written"] = reassessment["rows_written"]
out["leaked_shapes"] = reassessment["leaked_shapes"]

# The two conflations that must never be dropped.
pairs = {(e["readiness"], e["is_not"]) for e in reassessment["conflations"]}
out["backup_conflation_present"] = (
    "operational_backup_restore_ready",
    "production_backup_ready",
) in pairs
out["monitoring_conflation_present"] = (
    "operational_health_ready",
    "production monitoring",
) in pairs

# -- the next-block rule, re-derived and checked -----------------------
out["recommended_block"] = decision["recommended_block"]
out["first_gate"] = decision["first_gate"]
out["decision_deterministic"] = (
    build_next_activation_decision(
        real_customer_org_exists=False,
        second_identity_available=False,
        consent_decision_available=False,
    )
    == decision
)
chosen = next(
    e
    for e in decision["ranked_candidates"]
    if e["candidate"] == decision["recommended_block"]
)
out["recommended_is_engineering_advancable"] = chosen["engineering_can_advance"]
out["recommended_engineering_blockers"] = chosen["engineering_blocker_count"]
out["recommended_human_blockers"] = chosen["human_blocker_count"]
out["recommended_is_not_a_wrapper"] = chosen["verdict"] != WRAPPER_RISK
out["wrapper_candidates"] = sorted(
    e["candidate"]
    for e in decision["ranked_candidates"]
    if e["verdict"] == WRAPPER_RISK
)

# The branch: with the prerequisites available, customer activation wins.
alt = build_next_activation_decision(
    real_customer_org_exists=True,
    second_identity_available=True,
    consent_decision_available=True,
)
out["branch_flips_to_customer"] = alt["recommended_block"] == "customer_activation"

# -- the cockpit must not read as production-ready ----------------------
card = build_beta_onboarding_summary()["durability_closeout_card"]
out["card_production_monitoring"] = card["production_monitoring_active"]
out["card_production_backup"] = card["production_backup_ready"]
out["card_pilot_active"] = card["controlled_customer_pilot_active"]
out["card_activation_mechanism"] = card["activation_mechanism_exists"]
out["card_customer_beta"] = card["controlled_customer_beta"]
out["card_production_rollout"] = card["production_rollout"]
out["card_false_to_true"] = card["lanes_that_were_false_and_became_true"]

# -- artifacts ----------------------------------------------------------
built = art.build_durability_artifacts()
out["artifact_count"] = len(built)
out["artifacts_deterministic"] = art.build_durability_artifacts() == built
directory = Path(art.ARTIFACT_DIR)
out["artifacts_on_disk_match"] = all(
    (directory / n).is_file()
    and (directory / n).read_text(encoding="utf-8") == b
    for n, b in built.items()
)
blob = "\n".join(built.values()).lower()
out["artifact_claims_production_backup"] = '"production_backup_ready": true' in blob
out["artifact_claims_production_monitoring"] = (
    '"production_monitoring_active": true' in blob
)

out["invariant_failures"] = sorted(set(out["invariant_failures"]))
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

# --------------------------------------------------- 4. the four lanes moved
if [ "$(get lanes_created_count)" = "4" ] &&
   [ "$(get lanes_proved_count)" = "4" ] &&
   [ "$(get declared_lane_count)" = "4" ]; then
  pass four_durability_lanes_created_and_proved "$(getlist lanes_proved)"
else
  fail four_durability_lanes_created_and_proved \
    "created=$(get lanes_created_count) proved=$(get lanes_proved_count)"
fi

# The overstatement this gate exists to prevent.
if [ "$(getlist false_to_true)" = "none" ]; then
  pass no_false_lane_became_true "they were created, not flipped"
else
  fail no_false_lane_became_true "$(getlist false_to_true)"
fi

if [ "$(get durability_improved)" = "True" ]; then
  pass operational_durability_improved
else
  fail operational_durability_improved "$(getlist lanes_not_proved)"
fi

# ------------------------------------------ 5. the decisions did not move
if [ "$(get customer_beta_decision)" = "LIMITED_GO" ]; then
  pass customer_beta_remains_limited_go "unchanged since Gate 145"
else
  fail customer_beta_remains_limited_go "$(get customer_beta_decision)"
fi

if [ "$(get production_decision)" = "NO_GO" ]; then
  pass production_remains_no_go
else
  fail production_remains_no_go "$(get production_decision)"
fi

if [ "$(get internal_demo_decision)" = "GO" ]; then
  pass internal_demo_remains_go
else
  fail internal_demo_remains_go "$(get internal_demo_decision)"
fi

if [ "$(get any_decision_changed)" = "False" ]; then
  pass no_decision_changed_without_an_approval
else
  fail no_decision_changed_without_an_approval
fi

# ------------------------------------------- 6. what must remain false
if [ "$(get unchanged_false_count)" = "8" ] &&
   [ "$(getlist unchanged_false_true_ones)" = "none" ]; then
  pass eight_lanes_remain_false
else
  fail eight_lanes_remain_false "$(getlist unchanged_false_true_ones)"
fi

for flag in production_backup_ready production_monitoring_active \
  activation_mechanism_created anything_activated real_org_touched \
  email_sent live_source_called object_store_contacted; do
  if [ "$(get "$flag")" = "False" ]; then
    pass "stays_false:$flag"
  else
    fail "stays_false:$flag" "became true"
  fi
done

if [ "$(get rows_written)" = "0" ]; then
  pass reassessment_writes_nothing
else
  fail reassessment_writes_nothing "n=$(get rows_written)"
fi

if [ "$(getlist leaked_shapes)" = "none" ]; then
  pass reassessment_leaks_nothing
else
  fail reassessment_leaks_nothing "$(getlist leaked_shapes)"
fi

# ------------------------------- 7. the conflations must stay in the payload
if [ "$(get backup_conflation_present)" = "True" ]; then
  pass backup_conflation_warning_present "operational restore is not production backup"
else
  fail backup_conflation_warning_present "it was removed"
fi

if [ "$(get monitoring_conflation_present)" = "True" ]; then
  pass monitoring_conflation_warning_present
else
  fail monitoring_conflation_warning_present "it was removed"
fi

# ------------------------------------------------- 8. the next-block rule
info recommended_block "$(get recommended_block)"
info first_gate "$(get first_gate)"
info wrapper_candidates "$(getlist wrapper_candidates)"

if [ "$(get decision_deterministic)" = "True" ]; then
  pass next_block_decision_deterministic
else
  fail next_block_decision_deterministic
fi

if [ "$(get recommended_is_not_a_wrapper)" = "True" ] &&
   [ "$(get recommended_is_engineering_advancable)" = "True" ]; then
  pass recommended_block_is_not_a_wrapper \
    "$(get recommended_engineering_blockers) engineering blockers"
else
  fail recommended_block_is_not_a_wrapper \
    "it recommends a block only a person can advance"
fi

if [ "$(get recommended_engineering_blockers)" -ge 2 ] 2>/dev/null; then
  pass recommended_block_has_real_engineering_work
else
  fail recommended_block_has_real_engineering_work \
    "n=$(get recommended_engineering_blockers)"
fi

# The branch must be reachable, or the rule is unfalsifiable.
if [ "$(get branch_flips_to_customer)" = "True" ]; then
  pass customer_branch_is_reachable "with prerequisites, customer activation wins"
else
  fail customer_branch_is_reachable "the branch cannot be reached"
fi

# ------------------------------------ 9. the cockpit makes no false claim
for flag in card_production_monitoring card_production_backup \
  card_pilot_active card_activation_mechanism; do
  if [ "$(get "$flag")" = "False" ]; then
    pass "cockpit_states_false:$flag"
  else
    fail "cockpit_states_false:$flag"
  fi
done

if [ "$(get card_customer_beta)" = "LIMITED_GO" ] &&
   [ "$(get card_production_rollout)" = "NO_GO" ]; then
  pass cockpit_states_the_decisions_on_its_face
else
  fail cockpit_states_the_decisions_on_its_face
fi

if [ "$(getlist card_false_to_true)" = "none" ]; then
  pass cockpit_claims_no_false_lane_became_true
else
  fail cockpit_claims_no_false_lane_became_true "$(getlist card_false_to_true)"
fi

# --------------------------------------------------------- 10. artifacts
if [ "$(get artifact_count)" = "9" ] &&
   [ "$(get artifacts_deterministic)" = "True" ] &&
   [ "$(get artifacts_on_disk_match)" = "True" ]; then
  pass artifacts "9 files, deterministic, match the builder"
else
  fail artifacts \
    "n=$(get artifact_count) det=$(get artifacts_deterministic) match=$(get artifacts_on_disk_match)"
fi

for flag in artifact_claims_production_backup artifact_claims_production_monitoring; do
  if [ "$(get "$flag")" = "False" ]; then
    pass "stays_false:$flag"
  else
    fail "stays_false:$flag"
  fi
done

# ----------------------------------- 11. the real organization is untouched
hits="$(grep -rl "$REAL_ORG" artifacts/operational_durability_gate155/ 2>/dev/null | wc -l)"
if [ "$hits" = "0" ]; then
  pass real_organization_absent_from_artifacts
else
  fail real_organization_absent_from_artifacts "n=$hits"
fi

# ------------------------------------------------------------ 12. the lane
if [ "$(getlist invariant_failures)" = "none" ]; then
  pass invariants "none_failed"
else
  fail invariants "$(getlist invariant_failures)"
fi

# ---------------------------------------------------------- 13. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "operational_durability_improved=true"
echo "scope=controlled_dev_demo"
echo "lanes_created_by_this_block=4"
echo "lanes_that_were_false_and_became_true=0"
echo "internal_demo_beta=GO"
echo "controlled_customer_beta=LIMITED_GO"
echo "production_rollout=NO_GO"
echo "decisions_changed=0"
echo "lanes_remaining_false=8"
echo "production_backup_ready=false (Gate 61/65 harness re-run, still SKIP)"
echo "production_monitoring_active=false"
echo "controlled_customer_pilot=false"
echo "activation_mechanism_created=false"
echo "anything_activated=false"
echo "next_block=$(get recommended_block)"
echo "next_block_engineering_blockers=$(get recommended_engineering_blockers)"
echo "next_block_human_blockers=$(get recommended_human_blockers)"
echo "first_gate=$(get first_gate)"
echo "real_organization_touched=false"
echo "real_customer_data_written=false"
echo "emails_sent=0"
echo "live_source_calls=0"
echo "object_store_calls=0"
echo "next=docs/operations/809_GATE155_GATES_151_155_CLOSEOUT.md"
exit 0
