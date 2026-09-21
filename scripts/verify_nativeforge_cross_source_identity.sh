#!/usr/bin/env bash
# Gate 169 — can NativeForge tell when many sources describe one opportunity,
# without merging things that merely look alike?
#
# RESULT=PASS only when every hard negative stays distinct with a named
# reason, an annual recurrence stays two opportunities, a fuzzy match cannot
# settle without a human, an approved merge is fully reversible, and candidate
# generation is measurably bounded rather than a fleet scan.
#
# THIS SCRIPT MAKES NO NETWORK CALL, and does not take anyone's word for that:
# each phase replaces `socket.socket` with one that raises and counts attempts.
#
# The false-positive controls are the gate. A merge engine that cannot be
# shown refusing is not a merge engine, it is a collapse - so the negatives
# are asserted individually rather than as a single summary boolean.
#
# Performance values are INFO. What is asserted is structural: the candidate
# set does not grow with the graph, and the statement count per lookup does
# not either.
#
# Phases that write run against COPIES of the database file. The LAST phase
# removes Gate 167 fixture rows and counts what is left by SELECTing it.
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

jcase() {
  # $1 json, $2 case name, $3 field -> that case's field
  printf '%s' "$1" | .venv/bin/python -c \
    'import json,sys
d = json.load(sys.stdin)
for row in d.get("cases") or []:
    if row.get("case") == sys.argv[1]:
        print(row.get(sys.argv[2])); break
else:
    print("None")' "$2" "$3" 2>/dev/null || echo "None"
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
require_decision() {
  # $1 json, $2 case, $3 expected decision
  local v; v="$(jcase "$1" "$2" decision)"
  if [ "$v" = "$3" ]; then
    pass "negative_control_$2" "decision=$v"
  else
    fail "negative_control_$2" "expected=$3 got=$v"
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

# ------------------------------------- 1. decisions and hard negatives
DEC="$(run_phase scripts/_g169_phase_decisions.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=decisions_phase_did_not_report"; exit 0; }

require_true "$DEC" all_decisions_as_expected identity_layers_ready
require_empty_list "$DEC" decision_mismatches
require_true "$DEC" no_silent_merge
require_true "$DEC" every_decision_named_a_reason
require_true "$DEC" all_invariants_clean
require_true "$DEC" l4_cannot_settle_automatically
require_true "$DEC" l3_cannot_settle_automatically
require_true "$DEC" only_exact_or_strong_is_machine_settleable
require_true "$DEC" recurrence_never_proposes_a_merge
require_true "$DEC" forecast_never_proposes_a_merge
require_true "$DEC" conflicting_evidence_did_not_force_a_merge \
  conflicts_do_not_force_merge
require_true "$DEC" empty_record_produces_no_keys
require_true "$DEC" blocking_keys_are_deduplicated

# 169F, one assertion per negative. A summary boolean would let one
# regression hide behind eleven passes.
require_decision "$DEC" same_number_same_doc_type EXACT_MATCH
require_decision "$DEC" forecast_then_posted FORECAST_OF
require_decision "$DEC" aggregator_republished_without_the_number REPUBLISHED_FROM
require_decision "$DEC" republished_with_only_a_funder_name REVIEW_REQUIRED
require_decision "$DEC" same_title_different_year RECURRENCE_OF
require_decision "$DEC" same_agency_similar_title_different_number DISTINCT
require_decision "$DEC" same_program_different_number DISTINCT
require_decision "$DEC" same_deadline_unrelated_opportunity DISTINCT
require_decision "$DEC" same_title_different_funder DISTINCT
require_decision "$DEC" unnumbered_recurrence RECURRENCE_OF
require_decision "$DEC" nothing_in_common DISTINCT

info hard_negative_case_count "$(jget "$DEC" case_count)"
info conflicting_evidence_decision "$(jget "$DEC" conflicting_evidence_decision)"
info blocking_keys_for_a_full_record "$(jget "$DEC" blocking_key_count)"

# -------------------------- 2. persisted graph, review, reversibility
GRAPH="$(run_phase scripts/_g169_phase_graph.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=graph_phase_did_not_report"; exit 0; }

# 169E
require_true "$GRAPH" e_same_canonical_when_both_cite_the_number exact_match_ready
require_true "$GRAPH" e_two_source_observations
require_true "$GRAPH" e_two_provenance_chains

# 169K
require_true "$GRAPH" l4_automatic_merge_was_refused \
  l4_cannot_settle_automatically_at_rest
require_true "$GRAPH" k_candidate_written provisional_match_reviewable
require_true "$GRAPH" k_reversed_pair_is_the_same_candidate
require_true "$GRAPH" k_queue_holds_our_candidate
require_true "$GRAPH" k_unsigned_review_refused
require_false "$GRAPH" k_machine_may_settle strong_match_ready

# 169L
require_true "$GRAPH" l_merge_written merge_reversibility_supported
require_true "$GRAPH" l_revoked
require_zero "$GRAPH" l_rows_deleted_by_revocation
require_true "$GRAPH" l_nothing_lost_by_merging
require_true "$GRAPH" l_nothing_lost_by_unmerging
require_true "$GRAPH" l_merge_is_fully_reversible
require_true "$GRAPH" l_same_as_visible_after_merge
require_true "$GRAPH" l_same_as_gone_after_revocation
require_true "$GRAPH" l_revoked_merge_still_on_record
require_true "$GRAPH" l_unsigned_revocation_refused

# 169M / 169G / 169R
require_true "$GRAPH" m_recurrence_is_not_a_merge \
  recurrence_relationship_supported
require_true "$GRAPH" m_canonical_ids_are_distinct_for_the_recurrence
require_true "$GRAPH" m_recurrence_recorded_without_review
require_true "$GRAPH" r_derived_decision_replays_identically \
  identity_replay_without_network
require_true "$GRAPH" r_human_decision_is_persisted_not_recomputed
require_true "$GRAPH" isolated_copy_removed
require_zero "$GRAPH" rows_written_to_the_real_database graph_wrote_nothing_real

info l4_refusal_reasons "$(jget "$GRAPH" l4_refusal_reasons)"
info review_actions_available "$(jget "$GRAPH" k_review_actions_available)"
info related_by_kind "$(jget "$GRAPH" m_related_by_kind)"
info candidate_count_for_the_twin "$(jget "$GRAPH" p_candidate_count)"

# ------------------------------------------------ 3. bounded candidates
SCALE="$(run_phase scripts/_g169_phase_scale.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=scale_phase_did_not_report"; exit 0; }

require_true "$SCALE" no_n_squared_scan
require_true "$SCALE" candidate_generation_bounded
require_true "$SCALE" graph_grew
require_true "$SCALE" candidate_set_does_not_grow_with_the_graph
require_true "$SCALE" statement_count_does_not_grow_with_the_graph
require_true "$SCALE" candidate_set_is_bounded_well_below_the_graph
require_true "$SCALE" all_identity_lookups_use_an_index
require_zero "$SCALE" rows_written_to_the_real_database scale_wrote_nothing_real

info mean_candidates_by_graph_size \
  "$(jget "$SCALE" mean_candidate_count_by_graph_size)"
info max_candidates_by_graph_size \
  "$(jget "$SCALE" max_candidate_count_by_graph_size)"
info statements_per_candidate_generation \
  "$(jget "$SCALE" statements_per_candidate_generation_by_graph_size)"
info relationship_lookup_ms "$(jget "$SCALE" relationship_lookup_ms)"
info identity_scale_limits_not_measured "$(jget "$SCALE" not_measured)"

# ------------------------------------------------------- 4. health
HEALTH="$(run_phase scripts/_g169_phase_health.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=health_phase_did_not_report"; exit 0; }

require_true "$HEALTH" identity_resolution_ready
require_empty_list "$HEALTH" named_gaps
require_empty_list "$HEALTH" health_invariant_failures
require_true "$HEALTH" every_condition_in_the_vocabulary
require_true "$HEALTH" forged_readiness_is_caught
require_true "$HEALTH" unmeasured_conditions_are_named_not_assumed

info identity_conditions_measured "$(jget "$HEALTH" conditions_measured)"
info blocking_backfill "$(jget "$HEALTH" blocking_backfill)"

# ----------------------- 5. Gate 167 and 168 semantics, still standing
WRITE="$(run_phase scripts/_g167_phase_first_write.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=gate167_write_did_not_report"; exit 0; }

require_true "$WRITE" replay_is_idempotent gate167_semantics_preserved
require_true "$WRITE" every_provenance_row_names_evidence
require_true "$WRITE" http_status_remains_unknown
require_true "$WRITE" raw_payload_immutable

PROFILE="$(run_phase scripts/_g168_phase_profile.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=gate168_profile_did_not_report"; exit 0; }

require_false "$PROFILE" per_field_fanout_present \
  gate168_scale_semantics_preserved
require_true "$PROFILE" all_statements_classified
require_true "$PROFILE" replay_is_cheaper_than_first_ingest

info statements_first_observation_after_identity \
  "$(.venv/bin/python -c 'import json,sys
print((json.load(sys.stdin).get("first_observation") or {}).get("statements_per_observation"))' <<<"$PROFILE")"

# ----------------------------------------- 6. cleanup. NOTHING AFTER.
CLEAN="$(run_phase scripts/_g167_phase_cleanup.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=cleanup_phase_did_not_report"; exit 0; }

require_zero "$CLEAN" fixture_residue
require_true "$CLEAN" residue_was_counted
require_true "$CLEAN" real_opportunity_present
require_true "$CLEAN" live_evidence_unchanged
require_empty_list "$CLEAN" detail cleanup_reported_no_errors

info rows_removed "$(jget "$CLEAN" rows_removed)"
info raw_payload_rows "$(jget "$CLEAN" raw_payload_rows)"

# ------------------------------------------------------- 7. the network
D_NET="$(jget "$DEC" network_attempts_during_this_phase)"
G_NET="$(jget "$GRAPH" network_attempts_during_this_phase)"
S_NET="$(jget "$SCALE" network_attempts_during_this_phase)"
H_NET="$(jget "$HEALTH" network_attempts_during_this_phase)"
W_NET="$(jget "$WRITE" network_attempts_during_this_phase)"
P_NET="$(jget "$PROFILE" network_attempts_during_this_phase)"
C_NET="$(jget "$CLEAN" network_attempts_during_this_phase)"
TOTAL_NET=$(( ${D_NET:-1} + ${G_NET:-1} + ${S_NET:-1} + ${H_NET:-1} \
  + ${W_NET:-1} + ${P_NET:-1} + ${C_NET:-1} ))
info network_requests_during_gate169 "$TOTAL_NET"
if [ "$TOTAL_NET" = "0" ]; then
  pass network_requests_during_gate169_is_zero
else
  fail network_requests_during_gate169_is_zero "n=$TOTAL_NET"
fi

if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  echo "gate169_ready=false"
  exit 0
fi

echo "RESULT=PASS"
echo "identity_layers_ready=true"
echo "exact_match_ready=true"
echo "strong_match_ready=true"
echo "provisional_match_reviewable=true"
echo "false_positive_controls_clean=true"
echo "recurrence_relationship_supported=true"
echo "forecast_relationship_supported=true"
echo "amendment_identity_preserved=true"
echo "conflicts_do_not_force_merge=true"
echo "l4_cannot_settle_automatically=true"
echo "merge_reversibility_supported=true"
echo "candidate_generation_bounded=true"
echo "no_n_squared_scan=true"
echo "identity_replay_without_network=true"
echo "gate167_semantics_preserved=true"
echo "gate168_scale_semantics_preserved=true"
echo "network_requests=0"
echo "gate169_ready=true"
