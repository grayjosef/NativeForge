#!/usr/bin/env bash
# Gate 168 — can the canonical graph absorb fleet-scale ingestion without
# giving up any of the evidence guarantees Gate 167 proved?
#
# RESULT=PASS only when the per-field N+1 is gone, batches are atomic under
# every failure shape, concurrent writers leave a consistent graph, the write
# path names no dialect-specific construct, and every Gate 167 semantic still
# holds afterwards.
#
# THIS SCRIPT MAKES NO NETWORK CALL, and does not take anyone's word for that:
# each phase replaces `socket.socket` with one that raises and counts attempts.
#
# Performance values are reported as INFO. They are measurements of this
# machine on this day, not correctness invariants - pinning a throughput
# number would make a slower laptop a test failure. What IS asserted is
# structural: statements per observation do not grow with the population,
# transactions stay bounded, and no statement is issued per field.
#
# The scale and concurrency phases run against COPIES of the database file.
# The LAST phase removes fixture rows and counts what is left by SELECTing it.
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
  local value; value="$(jget "$1" "$2")"
  if [ "$value" = "True" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$value"; fi
}

require_false() {
  local value; value="$(jget "$1" "$2")"
  if [ "$value" = "False" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$value"; fi
}

require_zero() {
  local value; value="$(jget "$1" "$2")"
  if [ "$value" = "0" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$value"; fi
}

require_empty_list() {
  local value; value="$(jget "$1" "$2")"
  if [ "$value" = "[]" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$value"; fi
}

require_path_true() {
  local value; value="$(jpath "$1" "$2")"
  if [ "$value" = "True" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$value"; fi
}

run_phase() {
  local output
  output="$(.venv/bin/python "$1" 2>&1 | tail -1)"
  if ! printf '%s' "$output" | grep -q '^{'; then
    return 1
  fi
  printf '%s' "$output"
}

if [ ! -x .venv/bin/python ]; then
  echo "check=venv_present status=FAIL"; echo "RESULT=BLOCKED"
  echo "blocker=no_virtualenv"; exit 0
fi

# ---------------------------------------- 0. normalize fixture state
#
# The Gate 167 semantics phases write reserved-prefix fixture rows and are not
# self-cleaning. If a previous run - or a developer invoking one phase by hand
# - left those rows behind, the next run's writes become no-ops and the phase
# reports that versioning and conflict detection stopped working. That is a
# stale fixture, not a regression, and the two must not look alike.
PRECLEAN="$(run_phase scripts/_g167_phase_cleanup.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=preclean_phase_did_not_report"; exit 0; }
info fixture_rows_cleared_before_measuring "$(jget "$PRECLEAN" rows_removed)"
require_true "$PRECLEAN" real_opportunity_present \
  preclean_kept_the_real_opportunity

# ------------------------------------------- 1. the statement profile
PROFILE="$(run_phase scripts/_g168_phase_profile.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=profile_phase_did_not_report"; exit 0; }

# Optimizing unidentified work is how a fast wrong thing gets built.
require_true "$PROFILE" all_statements_classified statement_profile_complete
require_false "$PROFILE" per_field_fanout_present per_field_n_plus_one_absent
require_true "$PROFILE" replay_is_cheaper_than_first_ingest

info statements_first_observation \
  "$(jpath "$PROFILE" first_observation.statements_per_observation)"
info statements_idempotent_replay \
  "$(jpath "$PROFILE" idempotent_replay.statements_per_observation)"
info statements_amended_observation \
  "$(jpath "$PROFILE" amended_observation.statements_per_observation)"
info statements_per_field "$(jget "$PROFILE" statements_per_field)"
info provenance_statements_first_write \
  "$(jget "$PROFILE" provenance_related_statements_first_write)"

# ------------------------------------ 2. atomicity and concurrency
ATOMIC="$(run_phase scripts/_g168_phase_atomicity.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=atomicity_phase_did_not_report"; exit 0; }

require_true "$ATOMIC" all_scenarios_atomic atomicity_preserved
require_true "$ATOMIC" concurrent_writer_invariants_clean

require_path_true "$ATOMIC" transaction_scenarios.all_valid.all_landed
require_path_true "$ATOMIC" \
  transaction_scenarios.one_duplicate.only_the_new_record_landed \
  duplicate_is_idempotent_not_an_error
require_path_true "$ATOMIC" \
  transaction_scenarios.invalid_provenance_hash.valid_records_still_committed \
  one_invalid_record_does_not_poison_the_batch
require_path_true "$ATOMIC" \
  transaction_scenarios.identity_conflict.valid_record_still_committed
require_path_true "$ATOMIC" \
  transaction_scenarios.constraint_violation.nothing_half_written
# A hook that never fires would report a clean rollback of nothing.
require_path_true "$ATOMIC" \
  transaction_scenarios.interrupted_midway.interruption_hook_fired
require_path_true "$ATOMIC" \
  transaction_scenarios.interrupted_midway.nothing_half_written

require_path_true "$ATOMIC" concurrency.no_duplicate_canonical
require_path_true "$ATOMIC" concurrency.no_duplicate_observations
require_path_true "$ATOMIC" concurrency.no_duplicate_provenance
require_path_true "$ATOMIC" concurrency.no_dangling_current_version_pointer
require_path_true "$ATOMIC" concurrency.no_orphan_versions
require_zero "$ATOMIC" rows_written_to_the_real_database \
  atomicity_wrote_nothing_real

info concurrent_writers "$(jpath "$ATOMIC" concurrency.writers)"
info concurrent_writer_errors "$(jpath "$ATOMIC" concurrency.writer_errors)"
info concurrency_engine_limitation "$(jpath "$ATOMIC" concurrency.engine_limitation)"

# ------------------------------------------------- 3. portability
PORT="$(run_phase scripts/_g168_phase_portability.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=portability_phase_did_not_report"; exit 0; }

require_true "$PORT" writer_is_database_agnostic
require_empty_list "$PORT" dialect_findings_in_the_writer
require_true "$PORT" all_techniques_present
require_path_true "$PORT" \
  sqlite_specific_in_the_test_harness_only.pragma_absent_from_the_writer

info technique_classifications "$(jget "$PORT" technique_classifications)"
info portability_unknowns "$(jget "$PORT" unknowns)"

# ------------------------------------------------------ 4. scale
SCALE="$(run_phase scripts/_g168_phase_scale.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=scale_phase_did_not_report"; exit 0; }

# Structural, not a throughput pin.
require_true "$SCALE" statement_count_is_linear_in_observations
require_true "$SCALE" transactions_are_bounded
require_true "$SCALE" no_per_field_select
require_zero "$SCALE" rows_written_to_the_real_database scale_wrote_nothing_real
require_path_true "$SCALE" runs.batched_50000.all_records_accounted_for

info statements_per_observation_by_scale \
  "$(jget "$SCALE" statements_per_observation_by_scale)"
info observations_per_second_1k \
  "$(jpath "$SCALE" runs.batched_1000.observations_per_second)"
info observations_per_second_10k \
  "$(jpath "$SCALE" runs.batched_10000.observations_per_second)"
info observations_per_second_50k \
  "$(jpath "$SCALE" runs.batched_50000.observations_per_second)"
info observations_per_second_single_record \
  "$(jpath "$SCALE" runs.single_record_1000.observations_per_second)"
info speedup_vs_gate167_baseline "$(jget "$SCALE" speedup_vs_gate167_baseline)"
info peak_memory_mb_50k "$(jpath "$SCALE" runs.batched_50000.peak_memory_mb)"
info db_growth_mb_50k "$(jpath "$SCALE" runs.batched_50000.db_growth_mb)"
info transactions_50k "$(jpath "$SCALE" runs.batched_50000.transactions)"
info lookups_50k "$(jpath "$SCALE" runs.batched_50000.lookups)"
info scale_limits_not_measured "$(jget "$SCALE" not_measured)"

# --------------------------- 5. Gate 167 semantics, after the rewrite
WRITE="$(run_phase scripts/_g167_phase_first_write.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=gate167_write_phase_did_not_report"; exit 0; }

require_true "$WRITE" replay_is_idempotent idempotency_preserved
require_true "$WRITE" replay_wrote_nothing
require_true "$WRITE" identity_stable_across_replay identity_stable
require_true "$WRITE" every_provenance_row_names_evidence \
  field_provenance_complete
require_true "$WRITE" every_field_traces_to_a_raw_key \
  unsupported_fields_not_invented
require_true "$WRITE" http_status_remains_unknown
require_true "$WRITE" raw_payload_immutable raw_evidence_linked

SEM="$(run_phase scripts/_g167_phase_graph_semantics.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=gate167_semantics_phase_did_not_report"; exit 0; }

require_true "$SEM" g_title_change_new_version version_lineage_supported
require_true "$SEM" g_lineage_is_a_chain
require_true "$SEM" g_current_pointer_is_newest
# Asserted too: a chain that walks fewer versions than exist is broken, and
# that is what separates a real lineage failure from an ambiguous sort.
require_true "$SEM" g_exactly_one_chain_root
# Reported, not asserted. `created_at` ties are possible and are NOT a
# lineage failure - but the failing battery log could not tell the two apart
# because these were computed and thrown away.
info g_version_count "$(jget "$SEM" g_version_count)"
info g_chain_walk_length "$(jget "$SEM" g_chain_walk_length)"
info g_timestamp_order_matches_supersession_order \
  "$(jget "$SEM" g_timestamp_order_matches_supersession_order)"
info g_newest_version_id "$(jget "$SEM" g_newest_version_id)"
# The PRECONDITION. This phase is not idempotent and runs here after
# first_write, so it does not start from an empty graph. A dirty start is a
# fact worth seeing - the Gate 168 lineage failure has twice been read as a
# broken chain when the question was what the phase started from.
info g_started_from_a_clean_fixture \
  "$(jget "$SEM" g_started_from_a_clean_fixture)"
info g_versions_present_before_this_run \
  "$(jget "$SEM" g_versions_present_before_this_run)"
require_true "$SEM" g_deadline_is_material
require_false "$SEM" g_title_is_material
require_true "$SEM" h_same_canonical multi_source_identity_supported
require_true "$SEM" i_conflict_on_close_date conflicts_representable
require_true "$SEM" i_no_silent_overwrite
require_true "$SEM" i_disputed_value_did_not_become_canonical
require_true "$SEM" j_forecast_and_synopsis_share_a_group \
  forecast_to_posted_supported
require_true "$SEM" real_opportunity_untouched

REBUILD="$(run_phase scripts/_g167_phase_rebuild.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=gate167_rebuild_phase_did_not_report"; exit 0; }

require_true "$REBUILD" graph_is_global tenant_duplication_absent
require_true "$REBUILD" canonical_graph_ready
require_empty_list "$REBUILD" health_named_gaps
require_true "$REBUILD" rebuild_reproduces_the_graph rebuild_without_network
require_true "$REBUILD" no_field_has_two_current_values

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

# ------------------------------------------------------ 7. the network
P_NET="$(jget "$PROFILE" network_attempts_during_this_phase)"
A_NET="$(jget "$ATOMIC" network_attempts_during_this_phase)"
O_NET="$(jget "$PORT" network_attempts_during_this_phase)"
S_NET="$(jget "$SCALE" network_attempts_during_this_phase)"
W_NET="$(jget "$WRITE" network_attempts_during_this_phase)"
M_NET="$(jget "$SEM" network_attempts_during_this_phase)"
R_NET="$(jget "$REBUILD" network_attempts_during_this_phase)"
C_NET="$(jget "$CLEAN" network_attempts_during_this_phase)"
TOTAL_NET=$(( ${P_NET:-1} + ${A_NET:-1} + ${O_NET:-1} + ${S_NET:-1} \
  + ${W_NET:-1} + ${M_NET:-1} + ${R_NET:-1} + ${C_NET:-1} ))
info network_requests_during_gate168 "$TOTAL_NET"
if [ "$TOTAL_NET" = "0" ]; then
  pass network_requests_during_gate168_is_zero
else
  fail network_requests_during_gate168_is_zero "n=$TOTAL_NET"
fi

if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  echo "gate168_ready=false"
  exit 0
fi

echo "RESULT=PASS"
echo "batch_write_path_ready=true"
echo "statement_profile_complete=true"
echo "per_field_n_plus_one_absent=true"
echo "bulk_provenance_write_ready=true"
echo "batch_identity_resolution_ready=true"
echo "idempotency_preserved=true"
echo "atomicity_preserved=true"
echo "concurrent_writer_invariants_clean=true"
echo "gate167_semantics_preserved=true"
echo "network_requests=0"
echo "gate168_ready=true"
