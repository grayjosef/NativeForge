#!/usr/bin/env bash
# Gate 167 — is there a canonical opportunity graph, and is every value in it
# traceable to bytes somebody can replay?
#
# RESULT=PASS only when the first real opportunity is persisted from stored
# Gate 163 evidence, replaying that evidence changes nothing, two sources can
# describe one opportunity without either overwriting the other, a version
# lineage survives, and the whole graph can be destroyed and rebuilt from the
# payload store with identical identifiers.
#
# THIS SCRIPT MAKES NO NETWORK CALL, and does not take anyone's word for that:
# each phase replaces `socket.socket` with one that raises and counts attempts.
#
# It derives rather than accepts. Every number below is read from a phase that
# measured it on this checkout - none is passed in by a caller.
#
# The count of canonical opportunities is REPORTED, never required to be 1. One
# real opportunity is the current state, not an architectural maximum; a
# verifier asserting 1 would have to be edited the first time a second source
# is activated, which is the thing this substrate exists to allow.
#
# The scale phase and the rebuild phase run against COPIES of the database
# file, so neither inflates nor endangers the real graph. The LAST phase
# removes this gate's fixture rows and counts what is left by SELECTing it.
#
# No secrets, tokens, credentials, request URLs or customer data. Counts,
# booleans, hashes and identifiers only.
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

require_true() {
  local value
  value="$(jget "$1" "$2")"
  if [ "$value" = "True" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$value"; fi
}

require_false() {
  local value
  value="$(jget "$1" "$2")"
  if [ "$value" = "False" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$value"; fi
}

require_zero() {
  local value
  value="$(jget "$1" "$2")"
  if [ "$value" = "0" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$value"; fi
}

require_empty_list() {
  local value
  value="$(jget "$1" "$2")"
  if [ "$value" = "[]" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$value"; fi
}

run_phase() {
  # $1 script, $2 label -> echoes the json
  local output
  output="$(.venv/bin/python "$1" 2>&1 | tail -1)"
  if ! printf '%s' "$output" | grep -q '^{'; then
    echo "check=$2_phase_ran status=FAIL" >&2
    return 1
  fi
  printf '%s' "$output"
}

if [ ! -x .venv/bin/python ]; then
  echo "check=venv_present status=FAIL"
  echo "RESULT=BLOCKED"
  echo "blocker=no_virtualenv"
  exit 0
fi

# ------------------------------------------- 1. the first real write
# PRECLEAN. The graph semantics phase replays its writes against leftover
# fixture rows, and its assertions then describe stale data instead of what
# this run wrote - proven this session by leaving residue, watching 167 fail
# with exactly that signature, clearing it, and watching the same phase report
# a clean start. Cleanup runs LAST in this verifier, which protects whatever
# comes after but left this verifier's own phases exposed to whatever came
# before. Gate 168's verifier has opened with a preclean all along.
PRECLEAN="$(run_phase scripts/_g167_phase_cleanup.py preclean)" || {
  echo "RESULT=BLOCKED"; echo "blocker=preclean_did_not_report"; exit 0; }
require_zero "$PRECLEAN" fixture_residue preclean_left_no_residue
require_true "$PRECLEAN" live_evidence_unchanged preclean_kept_live_evidence

WRITE="$(run_phase scripts/_g167_phase_first_write.py first_write)" || {
  echo "RESULT=BLOCKED"; echo "blocker=first_write_phase_did_not_report"; exit 0; }

require_true "$WRITE" hash_verified evidence_hash_verified
require_true "$WRITE" every_field_traces_to_a_raw_key \
  unsupported_fields_not_invented
require_true "$WRITE" every_provenance_row_names_evidence \
  field_provenance_complete
require_true "$WRITE" opportunity_number_preserved
require_true "$WRITE" source_record_id_preserved
require_true "$WRITE" http_status_remains_unknown
require_true "$WRITE" raw_payload_immutable
require_empty_list "$WRITE" normalizer_invariant_failures
require_empty_list "$WRITE" identity_invariant_failures

# 167F. Replaying identical evidence must change nothing at all.
require_true "$WRITE" replay_is_idempotent
require_true "$WRITE" replay_wrote_nothing
require_true "$WRITE" identity_stable_across_replay identity_stable

info canonical_id "$(jget "$WRITE" composite_key)"
info fields_not_supported_by_this_source "$(jget "$WRITE" fields_not_supported)"
info fields_absent_from_this_record "$(jget "$WRITE" fields_absent)"

# ------------------------------------ 2. versions, sources, conflicts
SEM="$(run_phase scripts/_g167_phase_graph_semantics.py semantics)" || {
  echo "RESULT=BLOCKED"; echo "blocker=semantics_phase_did_not_report"; exit 0; }

# 167G
# The phase reports what it started from; this is where that is ACTED on.
# A dirty start makes every assertion below describe stale rows.
require_true "$SEM" g_started_from_a_clean_fixture \
  semantics_started_from_a_clean_fixture
info g_versions_present_before_this_run "$(jget "$SEM" g_versions_present_before_this_run)"
require_true "$SEM" g_title_change_new_version version_lineage_supported
require_true "$SEM" g_title_change_same_canonical
require_true "$SEM" g_previous_versions_retained
require_true "$SEM" g_lineage_is_a_chain
require_true "$SEM" g_current_pointer_is_newest
require_true "$SEM" g_deadline_is_material material_change_identified
require_false "$SEM" g_title_is_material immaterial_change_not_flagged

# 167H
require_true "$SEM" h_same_canonical multi_source_identity_supported
require_true "$SEM" h_one_canonical_for_two_sources
require_true "$SEM" h_outcome_is_multi_source

# 167I
require_true "$SEM" i_conflict_on_close_date conflicts_representable
require_true "$SEM" i_both_values_retained
require_true "$SEM" i_both_sources_identified
require_true "$SEM" i_conflict_group_links_both_sides
require_true "$SEM" i_no_silent_overwrite
require_true "$SEM" i_canonical_flags_the_conflict
require_true "$SEM" i_disputed_value_did_not_become_canonical

# 167J
require_true "$SEM" j_forecast_is_a_distinct_canonical \
  forecast_and_posted_are_not_merged
require_true "$SEM" j_forecast_and_synopsis_share_a_group \
  forecast_to_posted_supported
require_true "$SEM" j_transition_is_queryable

require_true "$SEM" real_opportunity_untouched

info version_count_after_changes "$(jget "$SEM" g_version_count)"
info conflicting_fields "$(jget "$SEM" i_conflicts_detected)"

# --------------------------- 3. tenancy, health, rebuild from evidence
REBUILD="$(run_phase scripts/_g167_phase_rebuild.py rebuild)" || {
  echo "RESULT=BLOCKED"; echo "blocker=rebuild_phase_did_not_report"; exit 0; }

# 167L
require_true "$REBUILD" graph_is_global tenant_duplication_absent
require_empty_list "$REBUILD" tenant_columns_found_in_graph
require_true "$REBUILD" no_per_tenant_duplication

# 167N
require_true "$REBUILD" canonical_graph_ready
require_empty_list "$REBUILD" health_named_gaps
require_empty_list "$REBUILD" health_invariant_failures
require_true "$REBUILD" no_field_has_two_current_values

# 167M
require_true "$REBUILD" rebuild_reproduces_the_graph rebuild_without_network
require_true "$REBUILD" same_canonical_identity
require_true "$REBUILD" same_version_identities
require_true "$REBUILD" same_provenance_identities
require_true "$REBUILD" every_rebuilt_observation_verified_its_hash
require_true "$REBUILD" isolated_copy_removed

info organizations_present "$(jget "$REBUILD" organizations_present)"
info tenant_tables_referencing_an_opportunity \
  "$(jget "$REBUILD" tenant_tables_referencing_an_opportunity)"

# ------------------------------------------------------- 4. scale
SCALE="$(run_phase scripts/_g167_phase_scale.py scale)" || {
  echo "RESULT=BLOCKED"; echo "blocker=scale_phase_did_not_report"; exit 0; }

require_true "$SCALE" reached_target_opportunities
require_true "$SCALE" reached_target_observations
require_true "$SCALE" all_probed_lookups_use_an_index
require_true "$SCALE" fixture_database_removed
require_zero "$SCALE" rows_written_to_the_real_database

info scale_row_counts "$(jget "$SCALE" row_counts)"
info scale_writes_per_second "$(jget "$SCALE" writes_per_second)"
info scale_ms_per_observation "$(jget "$SCALE" ms_per_observation)"
info lookup_by_identity_ms "$(jget "$SCALE" lookup_by_identity_ms)"
info lookup_by_source_record_ms "$(jget "$SCALE" lookup_by_source_record_ms)"
info lookup_current_version_ms "$(jget "$SCALE" lookup_current_version_ms)"
info lookup_field_provenance_ms "$(jget "$SCALE" lookup_field_provenance_ms)"
info lookup_by_deadline_ms "$(jget "$SCALE" lookup_by_deadline_ms)"
info db_growth_mb "$(jget "$SCALE" db_growth_mb)"
info opportunities_with_two_sources "$(jget "$SCALE" opportunities_with_two_sources)"
info opportunities_with_multiple_versions \
  "$(jget "$SCALE" opportunities_with_multiple_versions)"
info scale_limits_not_measured "$(jget "$SCALE" not_measured)"

# ----------------------------------------- 5. cleanup. NOTHING AFTER.
CLEAN="$(run_phase scripts/_g167_phase_cleanup.py cleanup)" || {
  echo "RESULT=BLOCKED"; echo "blocker=cleanup_phase_did_not_report"; exit 0; }

require_zero "$CLEAN" fixture_residue
require_true "$CLEAN" residue_was_counted
require_true "$CLEAN" refused_to_remove_the_real_opportunity
require_true "$CLEAN" real_opportunity_present first_live_opportunity_persisted
require_true "$CLEAN" live_evidence_unchanged
require_empty_list "$CLEAN" detail cleanup_reported_no_errors

info rows_removed "$(jget "$CLEAN" rows_removed)"
info real_opportunity "$(jget "$CLEAN" real_opportunity)"
info real_opportunity_provenance_rows \
  "$(jget "$CLEAN" real_opportunity_provenance_rows)"
info raw_payload_rows "$(jget "$CLEAN" raw_payload_rows)"

# ------------------------------------------------------ 6. the network
W_NET="$(jget "$WRITE" network_attempts_during_this_phase)"
S_NET="$(jget "$SEM" network_attempts_during_this_phase)"
R_NET="$(jget "$REBUILD" network_attempts_during_this_phase)"
C_NET="$(jget "$SCALE" network_attempts_during_this_phase)"
X_NET="$(jget "$CLEAN" network_attempts_during_this_phase)"
TOTAL_NET=$(( ${W_NET:-1} + ${S_NET:-1} + ${R_NET:-1} + ${C_NET:-1} + ${X_NET:-1} ))
info network_requests_during_gate167 "$TOTAL_NET"
if [ "$TOTAL_NET" = "0" ]; then
  pass network_requests_during_gate167_is_zero
else
  fail network_requests_during_gate167_is_zero "n=$TOTAL_NET"
fi

if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  echo "gate167_ready=false"
  exit 0
fi

echo "RESULT=PASS"
echo "canonical_store_exists=true"
echo "first_live_opportunity_persisted=true"
echo "raw_evidence_linked=true"
echo "field_provenance_complete=true"
echo "identity_stable=true"
echo "replay_idempotent=true"
echo "multi_source_identity_supported=true"
echo "conflicts_representable=true"
echo "version_lineage_supported=true"
echo "forecast_to_posted_supported=true"
echo "tenant_duplication_absent=true"
echo "rebuild_without_network=true"
echo "unsupported_fields_not_invented=true"
echo "network_requests=0"
echo "gate167_ready=true"
