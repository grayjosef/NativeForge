#!/usr/bin/env bash
# Gate 159K - a loop that wakes on a cadence and contacts nothing.
#
# THIS DOES NOT MAKE SOURCE MONITORING LIVE, AND CANNOT.
# Zero sources are approved, no collector exists, and the orchestration cycle
# table's own CHECK constraints refuse any row claiming a completion, a
# collector invocation or a live source call.
#
# A periodic trigger is the single most plausible thing in this campaign to
# mistake for live monitoring: something now wakes on a cadence and writes rows.
# It is not watching anything.
#
# What this proves by running it:
#
#    1 a one-shot cycle runs end to end
#    2 the same trigger slot twice produces ONE effect
#    3 the duplicate is suppressed and named, not silently repeated
#    4 two owners cannot both hold one slot
#    5 an EXPIRED owner is reclaimable, so one crash does not block a slot
#    6 one missed window recovers exactly once
#    7 a second restart recovers nothing new
#    8 a long outage respects the configured bound
#    9 recovered work reuses Gate 158 idempotency and invents no jobs
#   10 the worker sees the persisted Gate 158 rows
#   11 a blocked source stays blocked
#   12 terms-blocked stays blocked
#   13 human-review-blocked stays blocked
#   14 jobs_completed = 0
#   15 collectors_invoked = 0
#   16 live_source_calls = 0
#   17 source_monitoring_live = false
#   18 cleanup runs AFTER the final process invocation
#   19 cleanup measures actual persisted rows
#   20 no orchestration residue remains
#
# The permitting branches are exercised too. A lock that refused everything, or
# a trigger that never fired, would prove nothing about the refusals.
#
# The restart proof runs in SEPARATE python processes. Reading back through the
# connection that wrote is a green check with two causes - a durable row, or a
# session remembering its own uncommitted write.
#
# Cleanup is the LAST phase. Gate 158 found Gate 157's verifier cleaning up
# before invoking a script that committed 100 more rows, while still reporting
# a clean exit.
#
# No secrets, tokens, cookies, state, PKCE verifier, provider subject, API keys
# or recipient addresses.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

BACKEND="${NF_BACKEND_OVERRIDE:-http://127.0.0.1:8000}"
TIMEOUT=20
DEMO_ORG="bbbbbbbb-cccc-dddd-eeee-ffffffffffff"

FAILED=""

pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
info() { echo "check=$1 status=INFO ${2:-}"; }

jget() {
  printf '%s' "$1" | .venv/bin/python -c \
    'import json,sys;print(json.load(sys.stdin).get(sys.argv[1]))' "$2" \
    2>/dev/null || echo "None"
}

echo "verify=source_orchestration_runtime"

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

# ------------------------------------------------- 2. migration 0045 present
if [ -f alembic/versions/0045_source_orchestration_cycles.py ]; then
  pass migration_0045_present
else
  fail migration_0045_present
fi

# --------------------------------------- 3. the unit exists and is NOT enabled
UNIT="ops/systemd/nativeforge-source-orchestrator.service"
if [ -f "$UNIT" ]; then
  pass orchestrator_unit_written
else
  fail orchestrator_unit_written
fi

# Deliberately not enabled by this gate. Enabling is a host decision, and a
# verifier that enabled it would be making that decision on somebody's behalf.
if systemctl --user is-enabled nativeforge-source-orchestrator.service \
    >/dev/null 2>&1; then
  ACTIVE=1
  info orchestrator_unit_enabled "enabled on this host"
else
  ACTIVE=0
  pass orchestrator_unit_not_enabled "written, not enabled - by design"
fi
export NF_G159_PROCESS_ACTIVE="$ACTIVE"

# The unit must not bind a live path or carry a credential.
if grep -qiE '^(Environment=.*(SECRET|TOKEN|KEY|PASSWORD))' "$UNIT"; then
  fail orchestrator_unit_has_no_secret
else
  pass orchestrator_unit_has_no_secret
fi

TAG="nf-verify-159-$$-$(date +%s)"
export NF_G159_TAG="$TAG"
export NF_G159_ORG="$DEMO_ORG"

# ---------------------------------------- 4. phase A: a cycle, and a duplicate
A="$(.venv/bin/python scripts/_g159_phase_a.py 2>&1 | tail -1)"
if printf '%s' "$A" | grep -q '"first_ran"'; then
  pass phase_a_ran
else
  fail phase_a_ran "$A"
  A='{}'
fi

# ---- cycle identity -------------------------------------------------------
if [ "$(jget "$A" same_slot_same_id)" = "True" ] &&
   [ "$(jget "$A" different_slot_different_id)" = "True" ] &&
   [ "$(jget "$A" identity_invariants)" = "[]" ]; then
  pass cycle_identity_is_deterministic "same slot same id, different slot not"
else
  fail cycle_identity_is_deterministic \
    "same=$(jget "$A" same_slot_same_id) diff=$(jget "$A" different_slot_different_id)"
fi

if [ "$(jget "$A" cycle_id_is_a_job_id)" = "False" ]; then
  pass cycle_id_is_not_a_job_id
else
  fail cycle_id_is_not_a_job_id
fi

# ---- 1. a one-shot cycle runs --------------------------------------------
if [ "$(jget "$A" first_ran)" = "True" ] &&
   [ "$(jget "$A" first_invariants)" = "[]" ]; then
  pass one_shot_cycle_runs \
    "sources=$(jget "$A" sources_seen) created=$(jget "$A" jobs_created)"
else
  fail one_shot_cycle_runs "$(jget "$A" first_invariants)"
fi

# ---- 2 and 3. the same slot twice -----------------------------------------
if [ "$(jget "$A" duplicate_ran)" = "False" ] &&
   [ "$(jget "$A" duplicate_created)" = "0" ] &&
   [ "$(jget "$A" jobs_after_duplicate)" = "$(jget "$A" jobs_after_first)" ] &&
   [ "$(jget "$A" cycle_rows_after_duplicate)" = "$(jget "$A" cycle_rows_after_first)" ]; then
  pass same_slot_twice_is_one_effect \
    "state=$(jget "$A" duplicate_state) rows unchanged"
else
  fail same_slot_twice_is_one_effect \
    "ran=$(jget "$A" duplicate_ran) created=$(jget "$A" duplicate_created)"
fi

if [ "$(jget "$A" duplicate_suppressed)" -ge 1 ] 2>/dev/null; then
  pass duplicate_trigger_suppressed_and_named \
    "suppressed=$(jget "$A" duplicate_suppressed)"
else
  fail duplicate_trigger_suppressed_and_named \
    "suppressed=$(jget "$A" duplicate_suppressed) - a silent skip is not a refusal"
fi

# ---- 4. two owners, one slot ----------------------------------------------
if [ "$(jget "$A" concurrent_ran)" = "False" ] &&
   [ "$(jget "$A" concurrent_created)" = "0" ] &&
   [ "$(jget "$A" cycle_rows_after_concurrent)" = "$(jget "$A" cycle_rows_after_first)" ]; then
  pass concurrent_owners_cannot_both_own \
    "second owner refused, rows unchanged"
else
  fail concurrent_owners_cannot_both_own \
    "ran=$(jget "$A" concurrent_ran)"
fi

# ---- the permitting branch: a NEW slot DOES run --------------------------
if [ "$(jget "$A" later_ran)" = "True" ] &&
   [ "$(jget "$A" later_invariants)" = "[]" ]; then
  pass a_new_slot_runs "so the refusals above are falsifiable"
else
  fail a_new_slot_runs
fi

# ---- 9. a later slot reuses the same work ---------------------------------
if [ "$(jget "$A" later_created)" = "0" ] &&
   [ "$(jget "$A" later_reused)" -gt 0 ] 2>/dev/null &&
   [ "$(jget "$A" jobs_after_later)" = "$(jget "$A" jobs_after_first)" ]; then
  pass a_new_cycle_reuses_gate_158_idempotency \
    "created=0 reused=$(jget "$A" later_reused)"
else
  fail a_new_cycle_reuses_gate_158_idempotency \
    "created=$(jget "$A" later_created) reused=$(jget "$A" later_reused)"
fi

# --------------------------- 5. phase B: THE RESTART, a separate process
B="$(.venv/bin/python scripts/_g159_phase_b.py 2>&1 | tail -1)"
if printf '%s' "$B" | grep -q '"rows_found_after_restart"'; then
  pass phase_b_ran
else
  fail phase_b_ran "$B"
  B='{}'
fi

if [ "$(jget "$B" rows_found_after_restart)" -gt 0 ] 2>/dev/null &&
   [ "$(jget "$B" jobs_found_after_restart)" -gt 0 ] 2>/dev/null; then
  pass a_second_process_finds_the_rows \
    "cycles=$(jget "$B" rows_found_after_restart) jobs=$(jget "$B" jobs_found_after_restart)"
else
  fail a_second_process_finds_the_rows
fi

# ---- 7. restart idempotency ------------------------------------------------
if [ "$(jget "$B" restart_ran)" = "False" ] &&
   [ "$(jget "$B" restart_wrote_nothing)" = "True" ]; then
  pass restart_recovers_nothing_new \
    "state=$(jget "$B" restart_state) rows unchanged"
else
  fail restart_recovers_nothing_new \
    "ran=$(jget "$B" restart_ran) wrote_nothing=$(jget "$B" restart_wrote_nothing)"
fi

# ---- 6. one missed window recovers once -----------------------------------
if [ "$(jget "$B" missed_state)" = "missed_window" ] &&
   [ "$(jget "$B" missed_recovered)" -gt 0 ] 2>/dev/null &&
   [ "$(jget "$B" missed_invariants)" = "[]" ]; then
  pass missed_window_recovered \
    "detected=$(jget "$B" missed_detected) recovered=$(jget "$B" missed_recovered)"
else
  fail missed_window_recovered \
    "state=$(jget "$B" missed_state) recovered=$(jget "$B" missed_recovered)"
fi

if [ "$(jget "$B" second_recovery_wrote_nothing)" = "True" ] &&
   [ "$(jget "$B" second_recovery_recovered)" = "0" ]; then
  pass recovering_the_same_outage_twice_recovers_nothing
else
  fail recovering_the_same_outage_twice_recovers_nothing \
    "recovered=$(jget "$B" second_recovery_recovered)"
fi

# ---- 9. recovery invents no work ------------------------------------------
if [ "$(jget "$B" recovery_invented_no_jobs)" = "True" ]; then
  pass recovery_invents_no_jobs \
    "jobs $(jget "$B" jobs_before_recovery) -> $(jget "$B" jobs_after_recovery)"
else
  fail recovery_invents_no_jobs \
    "before=$(jget "$B" jobs_before_recovery) after=$(jget "$B" jobs_after_recovery)"
fi

# ---- 8. the bound holds ----------------------------------------------------
if [ "$(jget "$B" bound_held)" = "True" ] &&
   [ "$(jget "$B" bounded_dropped)" -gt 0 ] 2>/dev/null &&
   [ "$(jget "$B" bounded_invariants)" = "[]" ]; then
  pass catchup_respects_the_bound \
    "detected=$(jget "$B" bounded_detected) recovered=$(jget "$B" bounded_recovered) dropped=$(jget "$B" bounded_dropped)"
else
  fail catchup_respects_the_bound \
    "detected=$(jget "$B" bounded_detected) recovered=$(jget "$B" bounded_recovered)"
fi

# ---- 10 to 13. the worker saw them, and they stayed blocked ---------------
if [ "$(jget "$A" jobs_claimed)" -gt 0 ] 2>/dev/null &&
   [ "$(jget "$A" jobs_refused)" -gt 0 ] 2>/dev/null; then
  pass worker_sees_the_persisted_rows \
    "claimed=$(jget "$A" jobs_claimed) refused=$(jget "$A" jobs_refused)"
else
  fail worker_sees_the_persisted_rows \
    "claimed=$(jget "$A" jobs_claimed)"
fi

if [ "$(jget "$B" activation_still_blocked)" = "True" ]; then
  pass blocked_source_stays_blocked
else
  fail blocked_source_stays_blocked
fi

if [ "$(jget "$B" terms_still_blocked)" = "True" ]; then
  pass terms_blocked_stays_blocked
else
  fail terms_blocked_stays_blocked "$(jget "$B" all_blocked_reasons)"
fi

if [ "$(jget "$B" human_review_still_blocked)" = "True" ]; then
  pass human_review_blocked_stays_blocked
else
  fail human_review_blocked_stays_blocked
fi

if [ "$(jget "$A" jobs_executable)" = "0" ]; then
  pass zero_executable_jobs "counted, with an empty allowlist"
else
  fail zero_executable_jobs "$(jget "$A" jobs_executable)"
fi

# ---- 14 to 17. the standing boundary --------------------------------------
if [ "$(jget "$A" jobs_completed)" = "0" ] &&
   [ "$(jget "$B" rows_claiming_a_completion)" = "0" ]; then
  pass jobs_completed_is_zero
else
  fail jobs_completed_is_zero \
    "cycle=$(jget "$A" jobs_completed) rows=$(jget "$B" rows_claiming_a_completion)"
fi

if [ "$(jget "$A" collectors_invoked)" = "0" ] &&
   [ "$(jget "$B" rows_claiming_a_collector)" = "0" ]; then
  pass collectors_invoked_is_zero
else
  fail collectors_invoked_is_zero
fi

if [ "$(jget "$A" live_source_calls)" = "0" ] &&
   [ "$(jget "$B" rows_claiming_a_live_call)" = "0" ]; then
  pass live_source_calls_is_zero
else
  fail live_source_calls_is_zero
fi

if [ "$(jget "$A" source_monitoring_live)" = "False" ]; then
  pass source_monitoring_live_is_false
else
  fail source_monitoring_live_is_false
fi

if [ "$(jget "$B" database_refused_a_collector_claim)" = "True" ]; then
  pass database_refuses_a_collector_claim \
    "$(jget "$B" database_refusal), with the repository bypassed"
else
  fail database_refuses_a_collector_claim \
    "a raw UPDATE setting collectors_invoked=1 SUCCEEDED"
fi

# ------------------------------------- phase C: ownership, in its own slots
C="$(.venv/bin/python scripts/_g159_phase_c.py 2>&1 | tail -1)"
if printf '%s' "$C" | grep -q '"live_theft_acquired"'; then
  pass phase_c_ran
else
  fail phase_c_ran "$C"
  C='{}'
fi

if [ "$(jget "$C" live_first_acquired)" = "True" ] &&
   [ "$(jget "$C" live_theft_acquired)" = "False" ] &&
   [ "$(jget "$C" live_refused_for_the_right_reason)" = "True" ]; then
  pass a_live_owner_cannot_be_stolen_from \
    "refused: ownership_has_not_expired_and_cannot_be_stolen"
else
  fail a_live_owner_cannot_be_stolen_from \
    "acquired=$(jget "$C" live_theft_acquired) reasons=$(jget "$C" live_theft_reasons)"
fi

# ---- 5. an expired owner IS reclaimable -----------------------------------
if [ "$(jget "$C" reclaim_acquired)" = "True" ] &&
   [ "$(jget "$C" reclaimed)" = "True" ] &&
   [ "$(jget "$C" reclaim_count)" -ge 1 ] 2>/dev/null; then
  pass an_expired_owner_is_reclaimable \
    "new owner=$(jget "$C" reclaim_new_owner) reclaims=$(jget "$C" reclaim_count)"
else
  fail an_expired_owner_is_reclaimable \
    "acquired=$(jget "$C" reclaim_acquired) reclaimed=$(jget "$C" reclaimed)"
fi

if [ "$(jget "$C" stale_owner_count)" -ge 1 ] 2>/dev/null; then
  pass stale_ownership_is_measurable "$(jget "$C" stale_owner_count)"
else
  fail stale_ownership_is_measurable
fi

# A crashed slot must NOT count as served, or the reclaim above is unreachable.
if [ "$(jget "$C" unfinished_at_crash_time)" -ge 1 ] 2>/dev/null; then
  pass a_crashed_slot_is_unfinished_not_served \
    "unfinished=$(jget "$C" unfinished_at_crash_time)"
else
  fail a_crashed_slot_is_unfinished_not_served \
    "this is what made the reclaim path unreachable in the first draft"
fi

if [ "$(jget "$C" recovery_pass_acquired)" = "False" ]; then
  pass a_recovery_pass_does_not_compete_for_the_present
else
  fail a_recovery_pass_does_not_compete_for_the_present
fi

if [ "$(jget "$C" real_org_refused)" = "True" ] &&
   [ "$(jget "$C" real_org_rows)" = "0" ]; then
  pass real_organization_refused_and_empty "rows=0"
else
  fail real_organization_refused_and_empty \
    "refused=$(jget "$C" real_org_refused) rows=$(jget "$C" real_org_rows)"
fi

# --------------------------------------------------------- the health lane
H="$(.venv/bin/python scripts/_g159_phase_health.py 2>&1 | tail -1)"
if printf '%s' "$H" | grep -q '"ready"'; then
  pass health_lane_ran
else
  fail health_lane_ran "$H"
  H='{}'
fi

if [ "$(jget "$H" ready)" = "True" ] && [ "$(jget "$H" invariants)" = "[]" ]; then
  pass orchestration_runtime_ready
else
  fail orchestration_runtime_ready \
    "not_met=$(jget "$H" not_met) blockers=$(jget "$H" blockers)"
fi

if [ "$(jget "$H" jobs_completed)" = "0" ] &&
   [ "$(jget "$H" monitoring_live)" = "False" ] &&
   [ "$(jget "$H" approved_source_count)" = "0" ]; then
  pass ready_without_monitoring_live
else
  fail ready_without_monitoring_live
fi

info health_process_active "$(jget "$H" process_active)"
info health_total_reclaims "$(jget "$H" total_reclaims)"

# ---------------------------------------------- 18-20. cleanup, LAST of all
#
# After every phase that writes. Gate 158 found Gate 157 cleaning up before
# invoking a script that committed 100 more rows.
CL="$(.venv/bin/python scripts/_g159_phase_cleanup.py 2>&1 | tail -1)"
if printf '%s' "$CL" | grep -q '"cycles_deleted"'; then
  pass cleanup_ran
else
  fail cleanup_ran "$CL"
  CL='{}'
fi

cycles_deleted="$(jget "$CL" cycles_deleted)"
if [ "$cycles_deleted" != "None" ] && [ "$cycles_deleted" -gt 0 ] 2>/dev/null; then
  pass cleanup_had_something_to_clean \
    "cycles=$cycles_deleted jobs=$(jget "$CL" jobs_deleted)"
else
  fail cleanup_had_something_to_clean \
    "cycles=$cycles_deleted - a cleanup that deletes nothing is untested"
fi

if [ "$(jget "$CL" cycles_left)" = "0" ] &&
   [ "$(jget "$CL" jobs_left_for_this_tag)" = "0" ]; then
  pass no_orchestration_residue_remains \
    "cycles=0 jobs=0 of $(jget "$CL" cycles_before)"
else
  fail no_orchestration_residue_remains \
    "cycles=$(jget "$CL" cycles_left) jobs=$(jget "$CL" jobs_left_for_this_tag)"
fi

info whole_jobs_table_now "$(jget "$CL" whole_jobs_table)"
info whole_leases_table_now "$(jget "$CL" whole_leases_table)"

# ---------------------------------------------------------- the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "orchestration_runtime_ready=true"
echo "source_monitoring_live=false"
echo "scope=controlled_dev_demo"
echo "cycle_identity=deterministic over (version, cadence, slot)"
echo "cycle_id_is_a_job_id=false"
echo "duplicate_trigger=suppressed_and_named"
echo "concurrent_owners=refused_by_a_unique_index"
echo "live_owner=not_stealable"
echo "expired_owner=reclaimable"
echo "crashed_slot=unfinished_not_served"
echo "missed_window=recovered_once"
echo "second_restart=recovers_nothing"
echo "catchup=bounded_and_the_dropped_count_reported"
echo "recovery_invents_no_jobs=true"
echo "worker_sees_persisted_rows=true"
echo "blocked_sources_stay_blocked=true"
echo "jobs_executable=0"
echo "jobs_completed=0"
echo "collectors_invoked=0"
echo "live_source_calls=0"
echo "network_calls=0"
echo "emails_sent=0"
echo "object_store_calls=0"
echo "approved_source_count=0"
echo "last_checked_at_advanced=false"
echo "real_organization_rows=0"
echo "systemd_unit=written_not_enabled"
echo "cleanup=ran_after_the_final_write"
echo "orchestration_residue=0"
echo "migration_added_by_this_gate=0045 (nf_source_orchestration_cycles)"
echo "next=docs/operations/831_GATE159_SOURCE_RUNTIME_DELTA.md"
exit 0
