#!/usr/bin/env bash
# Gate 170 — does NativeForge know what changed, how much it matters, which
# source proves it, and where sources disagree?
#
# RESULT=PASS only when a shortened deadline is CRITICAL and an extended one
# is not, an amended opportunity stays one opportunity while a new fiscal year
# does not, two sources reporting one change produce one event, a conflict
# keeps both facts and its start time, and an unchanged observation costs
# almost nothing.
#
# THIS SCRIPT MAKES NO NETWORK CALL, and does not take anyone's word for that:
# each phase replaces `socket.socket` with one that raises and counts attempts.
#
# Materiality is asserted per case, not as a summary boolean. "The grid is
# fine" would let one severity regression hide behind ten passes - and the one
# that matters most is the deadline direction, because getting it backwards
# means telling a Tribe it has more time when it has less.
#
# Throughput values are INFO. What is asserted is structural: unchanged
# polling is cheaper than changed, and no observation triggers a history scan.
#
# Phases that write run against COPIES of the database file. The LAST phase
# removes fixture rows and counts what is left by SELECTing it.
#
# No secrets, tokens, credentials, request URLs or customer data.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT" || exit 1

FAILED=""
pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
info() { echo "check=$1 status=INFO ${2:-}"; }

jget() {
  printf '%s' "$1" | .venv/bin/python -c \
    'import json,sys;print(json.load(sys.stdin).get(sys.argv[1]))' "$2" \
    2>/dev/null || echo "None"
}

jpath() {
  printf '%s' "$1" | .venv/bin/python -c \
    'import json,sys
d=json.load(sys.stdin)
for k in sys.argv[1].split("."):
    d = (d or {}).get(k) if isinstance(d, dict) else None
print(d)' "$2" 2>/dev/null || echo "None"
}

require_true() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "True" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_false() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "False" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_zero() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "0" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_empty_list() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "[]" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_equals() {
  # $1 json, $2 dotted path, $3 expected, $4 label
  local v; v="$(jpath "$1" "$2")"
  if [ "$v" = "$3" ]; then
    pass "${4:-$2}" "value=$v"
  else
    fail "${4:-$2}" "expected=$3 got=$v"
  fi
}

run_phase() {
  local out
  out="$(.venv/bin/python "$1" 2>&1 | tail -1)"
  printf '%s' "$out" | grep -q '^{' || return 1
  printf '%s' "$out"
}

if [ ! -x .venv/bin/python ]; then
  echo "check=venv_present status=FAIL"; echo "RESULT=BLOCKED"
  echo "blocker=no_virtualenv"; exit 0
fi

# ------------------------------------- 0. normalize fixture state
#
# Gate 169 established why: leftover fixture rows make a later phase's writes
# no-ops, and the phase then reports that the engine stopped working. A stale
# fixture and a regression must not look alike.
PRECLEAN="$(run_phase scripts/_g167_phase_cleanup.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=preclean_did_not_report"; exit 0; }
info fixture_rows_cleared_before_measuring "$(jget "$PRECLEAN" rows_removed)"
require_true "$PRECLEAN" real_opportunity_present preclean_kept_the_real_opportunity

# --------------------------- 1. taxonomy, materiality, deadlines
SEM="$(run_phase scripts/_g170_phase_semantics.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=semantics_did_not_report"; exit 0; }

# 170B
require_true "$SEM" b_every_change_type_is_classified
require_empty_list "$SEM" b_types_without_a_rule materiality_rules_named
require_false "$SEM" b_llm_used no_llm_decided_a_change

# 170C/D - per case, because direction is the thing most worth getting right.
require_equals "$SEM" d_materiality_grid.deadline_shortened.materiality \
  CRITICAL shortened_deadline_is_critical
require_equals "$SEM" d_materiality_grid.deadline_extended.materiality \
  MATERIAL extended_deadline_is_material
require_equals "$SEM" d_materiality_grid.cancelled.materiality \
  CRITICAL cancellation_is_critical
require_equals "$SEM" d_materiality_grid.closed.materiality \
  CRITICAL closure_is_critical
require_equals "$SEM" d_materiality_grid.number_changed.materiality \
  CRITICAL number_change_is_critical
require_equals "$SEM" d_materiality_grid.eligibility.materiality \
  MATERIAL eligibility_change_is_material
require_equals "$SEM" d_materiality_grid.forecast_to_posted.materiality \
  MATERIAL forecast_to_posted_is_material
require_equals "$SEM" d_materiality_grid.cosmetic_title.materiality \
  NON_MATERIAL cosmetic_title_is_not_material
require_equals "$SEM" d_materiality_grid.source_url.materiality \
  INFORMATIONAL source_url_move_is_informational
require_true "$SEM" d_direction_produces_different_types field_diff_ready
require_true "$SEM" d_every_case_named_a_rule materiality_ready

# 170E
require_true "$SEM" e_multi_valued_shapes_are_flagged deadline_change_ready
require_true "$SEM" e_single_shape_is_not_flagged_as_multi
require_true "$SEM" e_shape_travels_with_the_event

# 170F
require_true "$SEM" f_amendment_same_canonical amendment_detection_ready
require_true "$SEM" f_amendment_created_no_new_canonical
require_true "$SEM" f_amendment_created_a_version
require_true "$SEM" f_shortened_deadline_is_critical
require_true "$SEM" f_recurrence_is_a_different_canonical recurrence_not_amendment
require_true "$SEM" c_first_is_not_an_amendment

# 170H
require_true "$SEM" h_one_semantic_event_not_two multi_source_corroboration
require_true "$SEM" h_sweep_produced_one_event
require_true "$SEM" h_sequential_agreement_created_no_event
require_true "$SEM" h_timing_still_visible

# 170I
require_true "$SEM" i_conflict_recorded conflicts_preserved
require_true "$SEM" i_both_sides_preserved
require_true "$SEM" i_has_first_detected
require_true "$SEM" i_has_last_observed
require_true "$SEM" i_unsigned_resolution_refused
require_true "$SEM" i_resolution_recorded conflict_resolution_supported
require_true "$SEM" i_competing_facts_preserved
require_true "$SEM" i_resolution_kept_every_fact
require_true "$SEM" i_resolved_field_is_no_longer_open
require_true "$SEM" i_unresolved_field_is_still_open

# 170J
require_true "$SEM" j_posted_to_closed_seen
require_true "$SEM" j_reopened_seen
require_true "$SEM" j_lifecycle_did_not_fork_the_opportunity

# 170K
require_true "$SEM" k_customer_safe
require_empty_list "$SEM" k_forbidden_markers_found
require_empty_list "$SEM" k_invariant_failures
require_zero "$SEM" k_notifications_sent no_notification_was_sent
require_true "$SEM" k_importance_is_customer_vocabulary
require_true "$SEM" k_no_unknown_change_events_reach_a_customer

# 170L
require_true "$SEM" l_replay_is_a_true_noop change_events_idempotent
require_true "$SEM" l_noop_wrote_no_version
require_true "$SEM" l_noop_wrote_no_event
require_true "$SEM" l_noop_wrote_no_conflict
require_zero "$SEM" rows_written_to_the_real_database semantics_wrote_nothing_real

info change_type_count "$(jget "$SEM" b_change_type_count)"
info deadline_event_type "$(jget "$SEM" f_deadline_event_type)"
info deadline_event_rule "$(jget "$SEM" f_deadline_event_rule)"
info corroborating_source_count "$(jget "$SEM" h_corroborating_source_count)"
info competing_values "$(jget "$SEM" i_competing_values)"
info noop_statements "$(jget "$SEM" l_noop_statements)"
info customer_sample "$(jget "$SEM" k_sample)"

# ------------------------------------------- 2. rebuild from evidence
REB="$(run_phase scripts/_g170_phase_rebuild.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=rebuild_did_not_report"; exit 0; }

require_true "$REB" graph_emptied
require_true "$REB" rebuild_is_deterministic replay_without_network
require_true "$REB" same_event_ids
require_true "$REB" same_change_types
require_true "$REB" same_materiality
require_true "$REB" same_evidence
require_true "$REB" same_deadline_shapes
require_true "$REB" second_rebuild_wrote_nothing
require_true "$REB" human_identity_decisions_replayed_from_storage \
  gate169_identity_semantics_preserved
require_true "$REB" isolated_copy_removed
require_zero "$REB" rows_written_to_the_real_database rebuild_wrote_nothing_real

info events_rebuilt "$(jget "$REB" events_after_rebuild)"
info payloads_survived_the_rebuild "$(jget "$REB" payloads_survived)"

# ------------------------------------------------------- 3. scale
SCALE="$(run_phase scripts/_g170_phase_scale.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=scale_did_not_report"; exit 0; }

require_true "$SCALE" unchanged_observation_noop unchanged_observation_cheap
require_true "$SCALE" unchanged_is_cheaper_than_changed
require_true "$SCALE" unchanged_wrote_no_versions
require_true "$SCALE" unchanged_wrote_no_events
require_true "$SCALE" no_full_history_scan_per_observation
require_true "$SCALE" all_change_lookups_use_an_index
require_true "$SCALE" reached_target_opportunities
require_true "$SCALE" reached_target_observations
require_zero "$SCALE" rows_written_to_the_real_database scale_wrote_nothing_real

info scale_row_counts "$(jget "$SCALE" row_counts)"
info changed_statements_per_observation \
  "$(jget "$SCALE" changed_statements_per_observation)"
info unchanged_statements_per_observation \
  "$(jget "$SCALE" unchanged_statements_per_observation)"
info unchanged_throughput_multiple "$(jget "$SCALE" unchanged_throughput_multiple)"
info changed_observations_per_second \
  "$(jpath "$SCALE" changed_pass.observations_per_second)"
info unchanged_observations_per_second \
  "$(jpath "$SCALE" unchanged_pass.observations_per_second)"
info change_lookup_timings "$(jget "$SCALE" lookups)"
info db_growth_mb "$(jget "$SCALE" db_growth_mb)"
info conflict_sync_sample "$(jget "$SCALE" conflict_sync)"
info scale_limits_not_measured "$(jget "$SCALE" not_measured)"

# ------------------------------------------------------- 4. health
HEALTH="$(run_phase scripts/_g170_phase_health.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=health_did_not_report"; exit 0; }

require_true "$HEALTH" change_intelligence_ready
require_empty_list "$HEALTH" named_gaps
require_empty_list "$HEALTH" health_invariant_failures
require_true "$HEALTH" every_condition_in_the_vocabulary
require_true "$HEALTH" forged_readiness_is_caught
require_true "$HEALTH" unmeasured_conditions_are_named_not_assumed
require_true "$HEALTH" customer_safe
require_empty_list "$HEALTH" read_model_invariant_failures
require_zero "$HEALTH" notifications_sent

info change_conditions_measured "$(jget "$HEALTH" conditions_measured)"
info change_backfill "$(jget "$HEALTH" change_backfill)"

# ------------------ 5. Gate 168 scale semantics, still standing
PROFILE="$(run_phase scripts/_g168_phase_profile.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=gate168_profile_did_not_report"; exit 0; }

require_false "$PROFILE" per_field_fanout_present \
  gate168_scale_semantics_preserved
require_true "$PROFILE" all_statements_classified
require_true "$PROFILE" replay_is_cheaper_than_first_ingest

info statements_first_observation_with_change_events \
  "$(jpath "$PROFILE" first_observation.statements_per_observation)"
info statements_idempotent_replay \
  "$(jpath "$PROFILE" idempotent_replay.statements_per_observation)"

# ----------------------------------------- 6. cleanup. NOTHING AFTER.
CLEAN="$(run_phase scripts/_g167_phase_cleanup.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=cleanup_did_not_report"; exit 0; }

require_zero "$CLEAN" fixture_residue
require_true "$CLEAN" residue_was_counted
require_true "$CLEAN" real_opportunity_present
require_true "$CLEAN" live_evidence_unchanged
require_empty_list "$CLEAN" detail cleanup_reported_no_errors

info rows_removed "$(jget "$CLEAN" rows_removed)"
info raw_payload_rows "$(jget "$CLEAN" raw_payload_rows)"

# ------------------------------------------------------- 7. the network
S_NET="$(jget "$SEM" network_attempts_during_this_phase)"
R_NET="$(jget "$REB" network_attempts_during_this_phase)"
C_NET="$(jget "$SCALE" network_attempts_during_this_phase)"
H_NET="$(jget "$HEALTH" network_attempts_during_this_phase)"
P_NET="$(jget "$PROFILE" network_attempts_during_this_phase)"
X_NET="$(jget "$CLEAN" network_attempts_during_this_phase)"
TOTAL_NET=$(( ${S_NET:-1} + ${R_NET:-1} + ${C_NET:-1} + ${H_NET:-1} \
  + ${P_NET:-1} + ${X_NET:-1} ))
info network_requests_during_gate170 "$TOTAL_NET"
if [ "$TOTAL_NET" = "0" ]; then
  pass network_requests_during_gate170_is_zero
else
  fail network_requests_during_gate170_is_zero "n=$TOTAL_NET"
fi

if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  echo "gate170_ready=false"
  exit 0
fi

echo "RESULT=PASS"
echo "field_diff_ready=true"
echo "materiality_ready=true"
echo "deadline_change_ready=true"
echo "amendment_detection_ready=true"
echo "recurrence_not_amendment=true"
echo "multi_source_corroboration=true"
echo "conflicts_preserved=true"
echo "conflict_resolution_supported=true"
echo "change_events_idempotent=true"
echo "unchanged_observation_cheap=true"
echo "replay_without_network=true"
echo "gate169_identity_semantics_preserved=true"
echo "gate168_scale_semantics_preserved=true"
echo "network_requests=0"
echo "gate170_ready=true"
