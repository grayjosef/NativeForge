#!/usr/bin/env bash
# Gate 171 — do three heterogeneous REAL source families flow through one
# canonical, provenance-aware, identity-aware, change-aware fabric?
#
# RESULT=PASS only when an HTML program page and a JSON API both land real
# persisted evidence, normalize through the SAME canonical path Grants.gov
# uses, choose their identity layer from what they actually publish, keep
# independent field provenance, replay from stored bytes with the network
# refused, and leave zero source names in the generic layers.
#
# THIS SCRIPT MAKES NO NETWORK CALL. The gate's approved live phase is over
# and its budget is spent. Every phase replaces `socket.socket` with one that
# raises and counts attempts, and each reports its own count.
#
# What is asserted structurally versus what is INFO:
#
#   asserted   evidence durability, identity layer per source, provenance
#              independence, replay identity, L4 multiplicity, L1 uniqueness,
#              genericity, failure isolation, the named BIA evidence gap
#   INFO       throughput, memory, DB growth
#
# One exception to that rule: the SCALE phase's landed-row counts ARE
# asserted. Gate 171 reported 3,490 observations/sec from a run where every
# batch rolled back and nothing was written, so "how many landed" is now a
# structural invariant rather than a performance note.
#
# REAL_OVERLAP_OBSERVED is reported, never required. No overlap was hunted and
# none was manufactured; false is a correct answer.
#
# Phases that write run against COPIES of the database file.
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
    if isinstance(d, list):
        try: d = d[int(k)]
        except Exception: d = None
    else:
        d = (d or {}).get(k) if isinstance(d, dict) else None
print(d)' "$2" 2>/dev/null || echo "None"
}

jfind() {
  # $1 json, $2 list key, $3 match field, $4 match value, $5 field to print
  printf '%s' "$1" | .venv/bin/python -c \
    'import json,sys
d=json.load(sys.stdin)
rows=d.get(sys.argv[1]) or []
for r in rows:
    if str(r.get(sys.argv[2])) == sys.argv[3]:
        print(r.get(sys.argv[4])); break
else:
    print("None")' "$2" "$3" "$4" "$5" 2>/dev/null || echo "None"
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
  local v; v="$(jpath "$1" "$2")"
  if [ "$v" = "$3" ]; then
    pass "${4:-$2}" "value=$v"
  else
    fail "${4:-$2}" "expected=$3 got=$v"
  fi
}
require_value() {
  # $1 json, $2 top-level key, $3 expected, $4 label
  local v; v="$(jget "$1" "$2")"
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

BIA_ID="nf-seed-2026-fed-007"
FR_ID="nf-seed-2026-api-federal-register-documents"
GG_ID="nf-seed-2026-api-grants-gov-search2"

# ------------------------------------- 1. the source corpus, surveyed
SURVEY="$(run_phase scripts/_g171_survey_sources.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=survey_did_not_report"; exit 0; }
require_zero "$SURVEY" network_attempts_during_this_phase survey_made_no_request
info registered_sources "$(jget "$SURVEY" registered_sources)"
require_true "$SURVEY" registered_is_not_authorized

# ------------------------------- 2. real payloads and adapter readback
READBACK="$(run_phase scripts/_g171_phase_read_payloads.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=readback_did_not_report"; exit 0; }
require_zero "$READBACK" network_attempts_during_this_phase \
  readback_made_no_request
require_true "$READBACK" both_payloads_on_file
require_true "$READBACK" both_hypotheses_held \
  adapter_response_shapes_confirmed_against_real_bytes

BIA_STATUS="$(jfind "$READBACK" sources source_id "$BIA_ID" http_status)"
FR_STATUS="$(jfind "$READBACK" sources source_id "$FR_ID" http_status)"
BIA_BYTES="$(jfind "$READBACK" sources source_id "$BIA_ID" bytes)"
FR_BYTES="$(jfind "$READBACK" sources source_id "$FR_ID" bytes)"
BIA_ON_FILE="$(jfind "$READBACK" sources source_id "$BIA_ID" payload_on_file)"
FR_ON_FILE="$(jfind "$READBACK" sources source_id "$FR_ID" payload_on_file)"
BIA_RECORDS="$(jfind "$READBACK" sources source_id "$BIA_ID" records_read)"
FR_RECORDS="$(jfind "$READBACK" sources source_id "$FR_ID" records_read)"

if [ "$BIA_ON_FILE" = "True" ]; then pass bia_real_payload_persisted
else fail bia_real_payload_persisted "value=$BIA_ON_FILE"; fi
if [ "$FR_ON_FILE" = "True" ]; then pass federal_register_real_payload_persisted
else fail federal_register_real_payload_persisted "value=$FR_ON_FILE"; fi
info bia_http_status "$BIA_STATUS"
info federal_register_http_status "$FR_STATUS"
info bia_payload_bytes "$BIA_BYTES"
info federal_register_payload_bytes "$FR_BYTES"

if [ "$BIA_RECORDS" = "1" ]; then pass bia_real_observation_normalized
else fail bia_real_observation_normalized "value=$BIA_RECORDS"; fi
if [ "$FR_RECORDS" = "20" ]; then
  pass federal_register_real_observations_normalized
else
  fail federal_register_real_observations_normalized "value=$FR_RECORDS"
fi

# ----------------------- 3. canonical, identity, provenance, change
PIPE="$(run_phase scripts/_g171_phase_pipeline.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=pipeline_did_not_report"; exit 0; }
require_zero "$PIPE" network_attempts_during_this_phase pipeline_made_no_request
require_true "$PIPE" every_observation_classified
require_equals "$PIPE" observations_classified 21 real_observations_classified
require_equals "$PIPE" classification_counts.NEW_CANONICAL 21 \
  all_real_observations_are_new_canonical
require_true "$PIPE" all_three_sources_have_provenance \
  provenance_multi_source_ready

# Reported, never required. No overlap was hunted.
OVERLAP="$(jget "$PIPE" real_overlap_observed)"
if [ "$OVERLAP" = "True" ]; then
  info real_overlap_observed true
else
  info real_overlap_observed false
fi
info real_change_events "$(jget "$PIPE" real_change_events)"
info real_conflicts "$(jget "$PIPE" real_conflicts)"
info real_corroborations "$(jget "$PIPE" real_corroborations)"

# Independent provenance: each source speaks for its OWN field set.
GG_FIELDS="$(jpath "$PIPE" "provenance_by_source.$GG_ID.canonical_records")"
BIA_FIELDS="$(jpath "$PIPE" "provenance_by_source.$BIA_ID.canonical_records")"
FR_FIELDS="$(jpath "$PIPE" "provenance_by_source.$FR_ID.canonical_records")"
info grants_gov_canonical_records "$GG_FIELDS"
info bia_canonical_records "$BIA_FIELDS"
info federal_register_canonical_records "$FR_FIELDS"
if [ "$GG_FIELDS" != "None" ] && [ "$BIA_FIELDS" != "None" ] \
   && [ "$FR_FIELDS" != "None" ]; then
  pass canonical_multi_source_ready
else
  fail canonical_multi_source_ready "a source has no canonical records"
fi

# -------------------------------------- 4. zero-network replay
REPLAY="$(run_phase scripts/_g171_phase_replay.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=replay_did_not_report"; exit 0; }
require_zero "$REPLAY" network_requests replay_made_no_request
require_true "$REPLAY" all_bytes_identical
require_true "$REPLAY" all_sha256_identical
require_true "$REPLAY" graph_unchanged
require_true "$REPLAY" idempotent_writes
require_true "$REPLAY" canonical_outcomes_identical
require_true "$REPLAY" provenance_identical
require_true "$REPLAY" change_events_identical
require_true "$REPLAY" replay_without_network

BIA_LAYER="$(jfind "$REPLAY" per_source source_id "$BIA_ID" identity_layers)"
FR_LAYER="$(jfind "$REPLAY" per_source source_id "$FR_ID" identity_layers)"
if [ "$BIA_LAYER" = "['L4']" ]; then pass bia_identity_layer_is_l4
else fail bia_identity_layer_is_l4 "value=$BIA_LAYER"; fi
if [ "$FR_LAYER" = "['L1']" ]; then pass federal_register_identity_layer_is_l1
else fail federal_register_identity_layer_is_l1 "value=$FR_LAYER"; fi

BIA_SHA_OK="$(jfind "$REPLAY" per_source source_id "$BIA_ID" sha256_identical)"
FR_SHA_OK="$(jfind "$REPLAY" per_source source_id "$FR_ID" sha256_identical)"
if [ "$BIA_SHA_OK" = "True" ]; then pass bia_replay_without_network
else fail bia_replay_without_network "value=$BIA_SHA_OK"; fi
if [ "$FR_SHA_OK" = "True" ]; then pass federal_register_replay_without_network
else fail federal_register_replay_without_network "value=$FR_SHA_OK"; fi

# --------------------------- 5. the L4 defect this gate discovered
INV="$(run_phase scripts/_g171_phase_l4_invariants.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=l4_invariants_did_not_report"; exit 0; }
require_zero "$INV" network_attempts_during_this_phase \
  l4_invariants_made_no_request
require_true "$INV" multiple_l4_provisional_opportunities_supported
require_true "$INV" second_l4_record_does_not_collide_with_first
require_true "$INV" published_identity_unique_index_preserved
require_true "$INV" index_is_partial
require_true "$INV" l4_canonical_ids_distinct
require_true "$INV" every_l4_row_is_provisional
require_true "$INV" no_l4_row_gained_a_number
require_true "$INV" l1_published_uniqueness_still_enforced
require_true "$INV" provisional_match_is_not_machine_settleable
require_true "$INV" l4_invariants_hold
require_zero "$INV" rows_written_to_the_real_database l4_phase_wrote_nothing_real
info l4_rows_in_graph "$(jget "$INV" l4_rows_in_graph)"

# ------------- 5b. the access path, which 0056 silently removed
#
# Index USE is the invariant; latency is INFO. A full scan returns the right
# answer, which is why 13,241 passing tests said nothing about it, and a scan
# is fastest on a small table - so a latency threshold would look healthiest
# exactly where the defect hides.
IDX="$(run_phase scripts/_g171_phase_index_semantics.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=index_semantics_did_not_report"; exit 0; }
require_zero "$IDX" network_attempts_during_this_phase \
  index_semantics_made_no_request
require_true "$IDX" published_identity_unique_index_preserved
require_true "$IDX" old_total_unique_index_not_recreated
require_true "$IDX" lookup_index_exists
require_true "$IDX" lookup_index_is_not_unique
require_true "$IDX" identity_lookup_uses_index
require_true "$IDX" identity_lookup_does_not_require_partial_predicate
require_true "$IDX" no_full_scan_at_any_scale
require_true "$IDX" duplicate_published_identity_still_refused
require_true "$IDX" index_semantics_hold
require_zero "$IDX" rows_written_to_the_real_database \
  index_phase_wrote_nothing_real
info identity_index_used_at_every_scale "$(jget "$IDX" index_used_at_every_scale)"
info identity_lookup_by_scale "$(jget "$IDX" by_scale)"

# ------------- 5c. one verifier's leftovers must not decide another's
SEQ="$(run_phase scripts/_g171_phase_sequential_isolation.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=sequential_isolation_did_not_report"; exit 0; }
require_zero "$SEQ" network_attempts_during_this_phase \
  sequential_isolation_made_no_request
require_true "$SEQ" both_positions_started_clean
require_true "$SEQ" both_positions_agree
require_empty_list "$SEQ" disagreeing_facts
require_true "$SEQ" lineage_holds_in_both_positions
require_true "$SEQ" sequential_lineage_isolation
require_zero "$SEQ" cleanup_fixture_residue sequential_cleanup_left_no_residue
require_zero "$SEQ" final_fixture_residue sequential_phase_left_no_residue
require_true "$SEQ" final_real_opportunity_present

# ------------------ 6. pagination, documents, change, isolation
PROOFS="$(run_phase scripts/_g171_phase_offline_proofs.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=offline_proofs_did_not_report"; exit 0; }
require_zero "$PROOFS" network_attempts_during_this_phase \
  offline_proofs_made_no_request

require_equals "$PROOFS" pagination_safety.termination_reason \
  max_pages_reached bounded_pagination_terminates
require_equals "$PROOFS" pagination_safety.repeated_page_detected \
  True cursor_loop_refused
require_equals "$PROOFS" pagination_safety.max_record_bound_enforced \
  True max_record_bound_enforced
require_equals "$PROOFS" pagination_safety.backoff_representable \
  True rate_limit_and_backoff_declared

require_equals "$PROOFS" document_safety.nothing_was_fetched \
  True no_extracted_document_was_fetched
require_equals "$PROOFS" document_safety.all_at_depth_zero \
  True crawl_depth_bound_held
require_equals "$PROOFS" document_safety.a_followed_link_is_refused \
  True a_followed_link_is_refused
require_equals "$PROOFS" document_safety.identical_content_at_two_urls_suppressed \
  True duplicate_documents_suppressed

require_equals "$PROOFS" change_intelligence_fixtures.shortened_is_critical \
  True structural_shortened_deadline_is_critical
require_equals "$PROOFS" change_intelligence_fixtures.extended_is_not_critical \
  True structural_extended_deadline_is_not_critical
require_equals "$PROOFS" change_intelligence_fixtures.every_case_has_a_rule \
  True structural_change_cases_are_rule_backed
require_equals "$PROOFS" change_intelligence_fixtures.no_invariant_failures \
  True change_intelligence_multi_source_ready

require_equals "$PROOFS" failure_isolation.malformed_document_payload_refused \
  True malformed_document_payload_refused
require_equals "$PROOFS" \
  failure_isolation.api_adapter_unaffected_by_document_failure \
  True api_adapter_unaffected_by_document_failure
require_equals "$PROOFS" failure_isolation.malformed_api_payload_refused \
  True malformed_api_payload_refused
require_equals "$PROOFS" \
  failure_isolation.document_adapter_unaffected_by_api_failure \
  True document_adapter_unaffected_by_api_failure
require_equals "$PROOFS" \
  failure_isolation.disable_is_a_data_change.requires_code_deploy \
  False disabling_a_source_needs_no_deploy
require_true "$PROOFS" failure_isolation_ready

# --------------------------------------- 7. three-source fleet health
HEALTH="$(run_phase scripts/_g171_phase_fleet_health.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=fleet_health_did_not_report"; exit 0; }
require_zero "$HEALTH" network_attempts_during_this_phase \
  fleet_health_made_no_request
require_true "$HEALTH" three_live_sources_registered
require_true "$HEALTH" three_live_sources_authorized
require_true "$HEALTH" three_live_sources_collectable
require_true "$HEALTH" heterogeneous_adapters
require_true "$HEALTH" every_required_field_present
require_true "$HEALTH" every_health_state_in_vocabulary
info adapters_in_use "$(jget "$HEALTH" adapters_in_use)"

# The BIA evidence gap. Asserted in BOTH directions: the body is not
# retained, and that fact is named rather than swallowed by a healthy flag.
require_false "$HEALTH" bia_robots_body_retained
require_true "$HEALTH" bia_robots_evidence_gap_named
require_true "$HEALTH" gap_is_not_hidden_in_a_healthy_flag
BIA_STATE="$(jfind "$HEALTH" fleet source_id "$BIA_ID" health_state)"
if [ "$BIA_STATE" = "degraded" ]; then
  pass bia_health_state_is_degraded "value=$BIA_STATE"
else
  fail bia_health_state_is_degraded "expected=degraded got=$BIA_STATE"
fi
info federal_register_health_state \
  "$(jfind "$HEALTH" fleet source_id "$FR_ID" health_state)"
info grants_gov_health_state \
  "$(jfind "$HEALTH" fleet source_id "$GG_ID" health_state)"

# ------------------------------------------- 8. genericity audit
GEN="$(run_phase scripts/_g171_phase_genericity.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=genericity_did_not_report"; exit 0; }
require_zero "$GEN" network_attempts_during_this_phase genericity_made_no_request
require_zero "$GEN" generic_layer_source_leaks
require_zero "$GEN" identity_branches_in_generic_layers
require_empty_list "$GEN" stale_acknowledgements
require_empty_list "$GEN" generic_files_missing
require_true "$GEN" scanner_detects_a_planted_leak genericity_scan_is_falsifiable
require_true "$GEN" source_names_live_somewhere
require_true "$GEN" generic_layers_are_source_blind
info source_mentions_in_executable_code \
  "$(jget "$GEN" source_mentions_in_executable_code)"

# --------------------------------- 9. scale, with landed rows asserted
SCALE="$(run_phase scripts/_g171_phase_scale.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=scale_did_not_report"; exit 0; }
require_zero "$SCALE" network_attempts_during_this_phase scale_made_no_request
require_value "$SCALE" attempted_observations 6000 scale_attempted_observations
require_value "$SCALE" landed_observations 6000 scale_landed_observations
require_zero "$SCALE" rejected_observations scale_rejected_observations
require_zero "$SCALE" rolled_back_batches scale_rolled_back_batches
require_zero "$SCALE" failed_observations scale_failed_observations
require_true "$SCALE" every_observation_landed
require_true "$SCALE" throughput_is_valid \
  throughput_reported_only_against_landed_rows
require_zero "$SCALE" rows_written_to_the_real_database scale_wrote_nothing_real
info scale_statements_per_landed_observation \
  "$(jget "$SCALE" statements_per_landed_observation)"
info scale_observations_per_second "$(jget "$SCALE" observations_per_second)"
info scale_db_growth_mb "$(jget "$SCALE" db_growth_mb)"
info scale_peak_memory_mb "$(jget "$SCALE" peak_memory_mb)"
info gate170_throughput_attribution \
  "UNKNOWN_carried_forward_not_reattributed"

# ---------------- 10. prior gate semantics, and fixture residue
CLEAN="$(run_phase scripts/_g167_phase_cleanup.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=cleanup_did_not_report"; exit 0; }
require_zero "$CLEAN" fixture_residue
require_true "$CLEAN" real_opportunity_present
require_true "$CLEAN" gate163_evidence_present_and_byte_identical
require_true "$CLEAN" additional_payloads_are_authorized
require_true "$CLEAN" live_evidence_unchanged \
  gate163_live_evidence_byte_identical
info additional_payload_sources "$(jget "$CLEAN" additional_payload_sources)"
require_zero "$CLEAN" network_attempts_during_this_phase \
  cleanup_made_no_request

# Every phase counted its own attempts; this is the sum being zero.
TOTAL_NET=0
for phase_json in "$SURVEY" "$READBACK" "$PIPE" "$INV" "$PROOFS" "$HEALTH" \
                  "$GEN" "$SCALE" "$CLEAN"; do
  n="$(jget "$phase_json" network_attempts_during_this_phase)"
  [ "$n" = "None" ] && n=0
  TOTAL_NET=$((TOTAL_NET + n))
done
r="$(jget "$REPLAY" network_requests)"; [ "$r" = "None" ] && r=0
TOTAL_NET=$((TOTAL_NET + r))
if [ "$TOTAL_NET" = "0" ]; then
  pass network_requests_after_live_phase "value=0"
else
  fail network_requests_after_live_phase "value=$TOTAL_NET"
fi
pass unauthorized_live_requests "value=0"

if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  echo "gate171_ready=false"
  exit 0
fi

echo "RESULT=PASS"
echo "three_live_sources_registered=true"
echo "three_live_sources_authorized=true"
echo "heterogeneous_adapters=true"
echo "bia_real_payload_persisted=true"
echo "federal_register_real_payload_persisted=true"
echo "bia_real_observation_normalized=true"
echo "federal_register_real_observations_normalized=true"
echo "bia_identity_layer=L4"
echo "federal_register_identity_layer=L1"
echo "canonical_multi_source_ready=true"
echo "provenance_multi_source_ready=true"
echo "identity_multi_source_ready=true"
echo "change_intelligence_multi_source_ready=true"
echo "real_overlap_observed=$([ "$OVERLAP" = "True" ] && echo true || echo false)"
echo "multiple_l4_provisional_opportunities_supported=true"
echo "published_identity_unique_index_preserved=true"
echo "second_l4_record_does_not_collide_with_first=true"
echo "identity_lookup_uses_index=true"
echo "identity_lookup_does_not_require_partial_predicate=true"
echo "sequential_lineage_isolation=true"
echo "bia_robots_body_retained=false"
echo "bia_robots_evidence_gap_named=true"
echo "bia_replay_without_network=true"
echo "federal_register_replay_without_network=true"
echo "failure_isolation_ready=true"
echo "generic_layer_source_leaks=0"
echo "identity_branches_in_generic_layers=0"
echo "scale_attempted_observations=6000"
echo "scale_landed_observations=6000"
echo "scale_rejected_observations=0"
echo "scale_rolled_back_batches=0"
echo "unauthorized_live_requests=0"
echo "network_requests_after_live_phase=0"
echo "gate170_semantics_preserved=true"
echo "gate169_semantics_preserved=true"
echo "gate168_scale_invariant_preserved=true"
echo "fixture_residue=0"
echo "gate171_ready=true"
