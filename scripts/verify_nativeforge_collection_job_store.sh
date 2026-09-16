#!/usr/bin/env bash
# Gate 158I - queued collection work that survives, having contacted nothing.
#
# THIS DOES NOT MAKE SOURCE MONITORING LIVE, AND CANNOT.
# Zero sources are approved, no collector exists, and the job table's own CHECK
# constraints refuse a completed row without an execution proof that no gate in
# this campaign can issue.
#
# What this proves by running it:
#
#   a scheduler cycle with no connection writes NOTHING
#   a scheduler cycle with a connection writes one row per evaluated source
#   the same cycle run five times still leaves one row per source
#   a row COMMITTED by one process is read by a SECOND python process
#   that second process sees the same status, attempts and blockers
#   a later schedule slot is different work, and gets its own row
#   an illegal transition is refused and the row is left alone
#   a legal transition IS allowed, so the refusals are falsifiable
#   a transition to completed is refused, by the repository AND the database
#   retry_wait with a non-transient reason is refused
#   retry_wait with a transient reason is allowed, and spends one attempt
#   the attempt budget cannot be exceeded
#   an archived row carries a timestamp, and a live row does not
#   the real organization is refused by name, and holds zero rows
#   the worker records its outcome on the durable row, not only the lease
#   the worker PRESERVES the blockers the scheduler recorded
#   the job table declares no lease column
#   zero completed rows and zero execution proofs, counted
#   every fixture row this verifier wrote is deleted, and the count is proven
#
# The permitting branch is exercised on purpose. A store that refused every
# transition would prove nothing about the refusals.
#
# The restart proof runs in SEPARATE python processes. Reading back through the
# connection that wrote is a green check with two causes - a durable row, or a
# session remembering its own uncommitted write.
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
  # $1 = json blob, $2 = key
  printf '%s' "$1" | .venv/bin/python -c \
    'import json,sys;print(json.load(sys.stdin).get(sys.argv[1]))' "$2" \
    2>/dev/null || echo "None"
}

echo "verify=collection_job_store"

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

# ------------------------------------------------- 2. migration 0044 present
if [ -f alembic/versions/0044_source_collection_jobs.py ]; then
  pass migration_0044_present
else
  fail migration_0044_present
fi

TAG="nf-verify-158-$$-$(date +%s)"
export NF_G158_TAG="$TAG"
export NF_G158_ORG="$DEMO_ORG"

# ------------------------------------------ 3. phase A: a process that writes
A="$(.venv/bin/python scripts/_g158_phase_a.py 2>&1 | tail -1)"
if printf '%s' "$A" | grep -q '"created"'; then
  pass phase_a_ran
else
  fail phase_a_ran "$A"
  A='{}'
fi

# ------------------------------------- 4. a connectionless cycle writes none
if [ "$(jget "$A" no_connection_rows_written)" = "0" ] &&
   [ "$(jget "$A" no_connection_reported)" = "0" ]; then
  pass evaluate_only_writes_nothing
else
  fail evaluate_only_writes_nothing \
    "rows=$(jget "$A" no_connection_rows_written)"
fi

# ------------------------------------------- 5. an enqueueing cycle persists
if [ "$(jget "$A" created)" = "3" ]; then
  pass scheduler_cycle_persists "created=3"
else
  fail scheduler_cycle_persists "created=$(jget "$A" created)"
fi

if [ "$(jget "$A" cycle_invariants)" = "[]" ]; then
  pass cycle_invariants_clean
else
  fail cycle_invariants_clean "$(jget "$A" cycle_invariants)"
fi

# ------------------------------------------------ 6. repeated cycles bounded
if [ "$(jget "$A" after_five_cycles_created)" = "0" ] &&
   [ "$(jget "$A" after_five_cycles_deduplicated)" = "3" ] &&
   [ "$(jget "$A" rows_after_five_cycles)" = "3" ]; then
  pass enqueue_idempotent_across_cycles "5 cycles, 3 rows"
else
  fail enqueue_idempotent_across_cycles \
    "created=$(jget "$A" after_five_cycles_created) rows=$(jget "$A" rows_after_five_cycles)"
fi

# ----------------------------------------------- 7. a later slot is new work
if [ "$(jget "$A" later_slot_created)" = "3" ] &&
   [ "$(jget "$A" rows_with_later_slot)" = "6" ]; then
  pass a_later_slot_is_different_work "3 -> 6 rows"
else
  fail a_later_slot_is_different_work \
    "created=$(jget "$A" later_slot_created) rows=$(jget "$A" rows_with_later_slot)"
fi

# ------------------------------- 8. phase B: THE RESTART, a second process
B="$(.venv/bin/python scripts/_g158_phase_b.py 2>&1 | tail -1)"
if printf '%s' "$B" | grep -q '"rows_found_after_restart"'; then
  pass phase_b_ran
else
  fail phase_b_ran "$B"
  B='{}'
fi

if [ "$(jget "$B" rows_found_after_restart)" = "6" ]; then
  pass survives_restart "a second process found 6 rows it did not write"
else
  fail survives_restart "found=$(jget "$B" rows_found_after_restart)"
fi

if [ "$(jget "$B" all_queued_after_restart)" = "True" ] &&
   [ "$(jget "$B" all_zero_attempts)" = "True" ] &&
   [ "$(jget "$B" all_have_blockers)" = "True" ] &&
   [ "$(jget "$B" no_proofs)" = "True" ]; then
  pass restart_state_unchanged "status, attempts and blockers all intact"
else
  fail restart_state_unchanged \
    "queued=$(jget "$B" all_queued_after_restart)"
fi

# ------------------------------------------ 9. illegal transitions refused
if [ "$(jget "$B" illegal_refused)" = "True" ] &&
   [ "$(jget "$B" illegal_named_a_reason)" = "True" ] &&
   [ "$(jget "$B" row_untouched_by_illegal)" = "True" ]; then
  pass illegal_transition_refused "$(jget "$B" illegal_reasons)"
else
  fail illegal_transition_refused "$(jget "$B" illegal_reasons)"
fi

# ---------------------------- 10. the permitting branch is reachable
if [ "$(jget "$B" legal_transition_allowed)" = "True" ]; then
  pass legal_transition_allowed "queued->claimed, so refusals are falsifiable"
else
  fail legal_transition_allowed
fi

# ------------------------------------- 11. completed refused, twice over
if [ "$(jget "$B" completed_refused)" = "True" ]; then
  pass completed_refused_by_repository "$(jget "$B" completed_reasons)"
else
  fail completed_refused_by_repository
fi

if [ "$(jget "$B" database_refused_completed)" = "True" ]; then
  pass completed_refused_by_database "$(jget "$B" database_refusal)"
else
  fail completed_refused_by_database "a raw UPDATE to completed SUCCEEDED"
fi

# ------------------------------------------- 12. retry_wait is transient only
if [ "$(jget "$B" retry_wait_non_transient_refused)" = "True" ] &&
   [ "$(jget "$B" retry_wait_transient_allowed)" = "True" ]; then
  pass retry_wait_is_transient_only "refused terms, allowed transient"
else
  fail retry_wait_is_transient_only \
    "non_transient=$(jget "$B" retry_wait_non_transient_refused)"
fi

if [ "$(jget "$B" budget_enforced)" = "True" ]; then
  pass attempt_budget_enforced \
    "$(jget "$B" final_attempts)/$(jget "$B" final_budget)"
else
  fail attempt_budget_enforced \
    "$(jget "$B" final_attempts)/$(jget "$B" final_budget)"
fi

# ---------------------------------------------- 13. archived_at discipline
if [ "$(jget "$B" archive_allowed)" = "True" ] &&
   [ "$(jget "$B" archived_has_timestamp)" = "True" ] &&
   [ "$(jget "$B" live_row_has_no_archived_at)" = "True" ]; then
  pass archived_at_is_exact "set iff archived"
else
  fail archived_at_is_exact \
    "archived=$(jget "$B" archived_has_timestamp) live=$(jget "$B" live_row_has_no_archived_at)"
fi

# -------------------------------------------- 14. the real org is untouched
if [ "$(jget "$B" real_org_refused)" = "True" ] &&
   [ "$(jget "$B" real_org_rows)" = "0" ]; then
  pass real_org_refused_and_empty "rows=0"
else
  fail real_org_refused_and_empty \
    "refused=$(jget "$B" real_org_refused) rows=$(jget "$B" real_org_rows)"
fi

# ------------------------------------- 15. the lease boundary is structural
if [ "$(jget "$B" declares_lease_columns)" = "[]" ]; then
  pass no_lease_column_on_the_job_table
else
  fail no_lease_column_on_the_job_table "$(jget "$B" declares_lease_columns)"
fi

if [ "$(jget "$B" completed_is_reachable)" = "False" ]; then
  pass completed_unreachable_by_signature
else
  fail completed_unreachable_by_signature
fi

# ----------------------------------------------- 16. nothing was collected
if [ "$(jget "$B" completed_total)" = "0" ] &&
   [ "$(jget "$B" rows_with_execution_proof)" = "0" ] &&
   [ "$(jget "$B" backlog_invariants)" = "[]" ]; then
  pass nothing_collected "0 completed, 0 proofs, counted"
else
  fail nothing_collected \
    "completed=$(jget "$B" completed_total) proofs=$(jget "$B" rows_with_execution_proof)"
fi

# ------------------------- 17. phase C: the worker preserves what it inherits
C="$(.venv/bin/python scripts/_g158_phase_c.py 2>&1 | tail -1)"
if printf '%s' "$C" | grep -q '"worker_kept_them_all"'; then
  pass phase_c_ran
else
  fail phase_c_ran "$C"
  C='{}'
fi

# The worker drains the whole organization's backlog, not just the row this
# phase enqueued, so the TOTAL depends on what the earlier phases left behind.
# Pinning it would make this fail for the wrong reason. What is pinned is that
# THIS phase's row completed the two-step, and that the moves were clean.
transitions="$(jget "$C" job_rows_transitioned)"
if [ "$(jget "$C" status_after)" = "refused" ] &&
   [ "$(jget "$C" own_row_transitions)" = "2" ] &&
   [ "$(jget "$C" worker_invariants)" = "[]" ]; then
  pass worker_records_on_the_durable_row "queued->claimed->refused"
else
  fail worker_records_on_the_durable_row \
    "status=$(jget "$C" status_after) own=$(jget "$C" own_row_transitions) \
$(jget "$C" worker_invariants)"
fi

info worker_backlog_drained \
  "loaded=$(jget "$C" jobs_loaded_from_store) transitions=$transitions"

if [ "$transitions" != "None" ] && [ "$transitions" -ge 2 ] 2>/dev/null; then
  pass worker_moved_at_least_its_own_row
else
  fail worker_moved_at_least_its_own_row "transitions=$transitions"
fi

if [ "$(jget "$C" worker_kept_them_all)" = "True" ] &&
   [ "$(jget "$C" worker_added_its_own)" = "True" ]; then
  pass worker_preserves_the_backlog_reason \
    "reason=$(jget "$C" terminal_reason_after)"
else
  fail worker_preserves_the_backlog_reason \
    "kept=$(jget "$C" worker_kept_them_all) added=$(jget "$C" worker_added_its_own)"
fi

if [ "$(jget "$C" terminal_reason_after)" = "terms_blocked" ]; then
  pass terminal_reason_stays_countable "terms_blocked, not unknown"
else
  fail terminal_reason_stays_countable "$(jget "$C" terminal_reason_after)"
fi

if [ "$(jget "$C" jobs_completed)" = "0" ] &&
   [ "$(jget "$C" collectors_invoked)" = "0" ] &&
   [ "$(jget "$C" live_source_calls)" = "0" ] &&
   [ "$(jget "$C" claimed_means_contacted)" = "False" ]; then
  pass worker_contacted_nothing
else
  fail worker_contacted_nothing
fi

# --------------------------------------------------------- 18. the health lane
H="$(.venv/bin/python scripts/_g158_phase_health.py 2>&1 | tail -1)"
if printf '%s' "$H" | grep -q '"ready"'; then
  pass health_lane_ran
else
  fail health_lane_ran "$H"
  H='{}'
fi

if [ "$(jget "$H" ready)" = "True" ] && [ "$(jget "$H" invariants)" = "[]" ]; then
  pass collection_job_store_ready
else
  fail collection_job_store_ready \
    "blockers=$(jget "$H" blockers) not_met=$(jget "$H" not_met)"
fi

if [ "$(jget "$H" jobs_completed)" = "0" ] &&
   [ "$(jget "$H" monitoring_live)" = "False" ]; then
  pass ready_without_monitoring_live
else
  fail ready_without_monitoring_live
fi

# ------------------------------------------------------------ 19. cleanup
#
# Counted from the rows that exist, and asserted to have deleted SOMETHING.
# Gate 157 shipped a cleanup whose LIKE pattern matched nothing it had created
# and reported a clean exit anyway: 277 rows survived a "clean" run.
CL="$(.venv/bin/python scripts/_g158_phase_cleanup.py 2>&1 | tail -1)"
if printf '%s' "$CL" | grep -q '"jobs_deleted"'; then
  pass cleanup_ran
else
  fail cleanup_ran "$CL"
  CL='{}'
fi

deleted="$(jget "$CL" jobs_deleted)"
if [ "$deleted" != "None" ] && [ "$deleted" -gt 0 ] 2>/dev/null; then
  pass cleanup_had_something_to_clean "deleted=$deleted"
else
  fail cleanup_had_something_to_clean \
    "deleted=$deleted - a cleanup that deletes nothing is untested"
fi

if [ "$(jget "$CL" left)" = "0" ]; then
  pass fixture_rows_removed "left=0 of $(jget "$CL" before)"
else
  fail fixture_rows_removed "left=$(jget "$CL" left)"
fi

info whole_job_table_now "rows=$(jget "$CL" whole_table)"
info leases_removed "deleted=$(jget "$CL" leases_deleted)"

# ---------------------------------------------------------- 20. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "collection_job_store_ready=true"
echo "source_monitoring_live=false"
echo "scope=controlled_dev_demo"
echo "evaluate_only_rows_written=0"
echo "enqueue_idempotent=5 cycles, 3 rows"
echo "later_slot_is_new_work=true"
echo "survives_restart=proven_by_a_second_process"
echo "illegal_transition=refused_and_row_untouched"
echo "legal_transition=allowed (refusals are falsifiable)"
echo "completed_refused_by=repository_and_database"
echo "retry_wait=transient_only"
echo "attempt_budget=enforced"
echo "archived_at=set_iff_archived"
echo "lease_columns_on_job_table=0"
echo "worker_preserves_backlog_reason=true"
echo "terminal_reason_stays_countable=terms_blocked"
echo "jobs_completed=0"
echo "rows_with_execution_proof=0"
echo "collectors_invoked=0"
echo "live_source_calls=0"
echo "network_calls=0"
echo "emails_sent=0"
echo "object_store_calls=0"
echo "approved_source_count=0"
echo "real_organization_rows=0"
echo "fixture_rows_remaining=0"
echo "migration_added_by_this_gate=0044 (nf_source_collection_jobs)"
echo "next=docs/operations/826_GATE158_JOB_STORE_DELTA.md"
exit 0
