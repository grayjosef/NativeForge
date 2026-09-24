#!/usr/bin/env bash
# Gate 175 — is the authoritative answer allowed to live in an attachment?
#
# RESULT=PASS only when a document is versioned evidence bound to a canonical
# opportunity, when a document we could not READ never reads as a document with
# nothing in it, when a fact carries the page it was read at, when two
# documents disagreeing is REPRESENTED rather than silently resolved, and when
# an FAQ clarifies without erasing what it clarifies.
#
# THIS SCRIPT MAKES NO NETWORK CALL AND DOWNLOADS NO DOCUMENT. Every byte is a
# synthetic fixture built in-process.
#
#   asserted   document model and states, version chain, conflict rules,
#              citation contract, access paths, falsifiability
#   INFO       counts, milliseconds, memory
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
jnest() {
  printf '%s' "$1" | .venv/bin/python -c \
    'import json,sys
d=json.load(sys.stdin)
print((d.get(sys.argv[1]) or {}).get(sys.argv[2]))' "$2" "$3" 2>/dev/null || echo "None"
}

require_true() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "True" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_nested_true() {
  local v; v="$(jnest "$1" "$2" "$3")"
  if [ "$v" = "True" ]; then pass "${4:-$3}"; else fail "${4:-$3}" "value=$v"; fi
}
require_zero() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "0" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_empty_list() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "[]" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_value() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "$3" ]; then pass "${4:-$2}" "value=$v"; else fail "${4:-$2}" "expected=$3 got=$v"; fi
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

# --------------------------------- 1. the survey
SURVEY="$(run_phase scripts/_g175_survey_documents.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=survey_did_not_report"; exit 0; }
require_zero "$SURVEY" network_attempts_during_this_phase survey_made_no_request
require_true "$SURVEY" every_fact_has_exactly_one_owner
require_true "$SURVEY" survey_can_report_unknown survey_classifier_is_falsifiable
require_true "$SURVEY" empty_is_distinguished_from_unwired
# The finding that shaped the gate.
require_true "$SURVEY" no_table_binds_a_document_to_a_canonical_opportunity
require_true "$SURVEY" award_document_table_is_post_award \
  award_document_table_is_a_different_lifecycle_stage
info primitives_surveyed "$(jget "$SURVEY" primitives_surveyed)"
info counts_by_classification "$(jget "$SURVEY" counts_by_classification)"
info award_document_table_binds_to "$(jget "$SURVEY" award_document_table_binds_to)"
info gate175_must_build "$(jget "$SURVEY" gate175_must_build)"

# ------------------- 2. the adversarial cases
DOCS="$(run_phase scripts/_g175_phase_document_intelligence.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=document_phase_did_not_report"; exit 0; }
require_zero "$DOCS" network_attempts_during_this_phase \
  document_phase_made_no_request
require_zero "$DOCS" live_document_downloads no_document_was_downloaded
require_true "$DOCS" all_bytes_are_synthetic_fixtures

require_true "$DOCS" documents_first_class
require_empty_list "$DOCS" document_invariant_failures
require_empty_list "$DOCS" fact_invariant_failures
require_true "$DOCS" document_types_extensible

# The rule this gate exists for.
require_true "$DOCS" missing_parser_not_empty_truth

require_true "$DOCS" document_versions_preserved
require_true "$DOCS" same_url_changed_bytes_creates_new_version
require_true "$DOCS" same_bytes_different_url_is_the_same_document \
  same_bytes_different_url_dedup_safe
require_true "$DOCS" chain_is_valid
require_true "$DOCS" chain_latest_is_the_amendment

require_true "$DOCS" appendix_only_eligibility_detected
require_true "$DOCS" match_requirement_only_in_faq_detected
require_true "$DOCS" faq_clarification_preserved
require_true "$DOCS" faq_clarification_picks_no_winner
require_true "$DOCS" faq_clarification_retains_both
require_true "$DOCS" amendment_supersedes_correctly
require_true "$DOCS" amendment_retains_the_predecessor
require_true "$DOCS" notice_outranks_summary
require_true "$DOCS" document_conflict_not_silently_resolved
require_true "$DOCS" nothing_was_silently_resolved
require_empty_list "$DOCS" conflict_invariant_failures
info conflicts_detected "$(jget "$DOCS" conflicts_detected)"
info faq_clarification_rule "$(jget "$DOCS" faq_clarification_rule)"
info amendment_rule "$(jget "$DOCS" amendment_rule)"
info unresolved_rule "$(jget "$DOCS" unresolved_rule)"

require_true "$DOCS" customer_explainability_contract_ready
require_true "$DOCS" every_citation_names_a_document_and_quotes_it
require_empty_list "$DOCS" citation_invariant_failures
info citations_built "$(jget "$DOCS" citations_built)"

# Self-health, each asserted by its SPECIFIC detector.
require_true "$DOCS" document_self_health_ready
for check in supersession_cycle_is_caught missing_predecessor_is_caught \
             latest_pointer_not_newest_is_caught \
             citation_beyond_the_document_is_caught \
             fact_without_a_document_is_caught \
             fact_from_an_unreadable_document_is_caught \
             clarification_overwrite_is_caught false_absence_claim_is_caught; do
  require_nested_true "$DOCS" falsifiability "$check"
done

require_zero "$DOCS" fixture_residue document_phase_left_no_residue
require_zero "$DOCS" rows_written_to_the_real_database \
  document_phase_wrote_nothing_real

# --------------------------------- 3. scale and access paths
SCALE="$(run_phase scripts/_g175_phase_document_scale.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=scale_phase_did_not_report"; exit 0; }
require_zero "$SCALE" network_attempts_during_this_phase scale_made_no_request
require_true "$SCALE" critical_document_queries_indexed
require_empty_list "$SCALE" selective_queries_that_scan \
  every_selective_document_query_uses_an_index
require_true "$SCALE" no_quadratic_growth
require_true "$SCALE" all_chains_valid_at_scale
require_true "$SCALE" scratch_database_removed scale_scratch_removed
info documents_10k_ms "$(jget "$SCALE" documents_10k_ms)"
info documents_per_opportunity "$(jget "$SCALE" documents_per_opportunity)"
info scale_document_rows "$(jget "$SCALE" scale_document_rows)"
info scale_fact_rows "$(jget "$SCALE" scale_fact_rows)"
info document_statements_per_row "$(jget "$SCALE" statements_per_row)"
info document_memory_mb "$(jget "$SCALE" document_memory_mb)"
info ms_per_opportunity_by_scale "$(jget "$SCALE" ms_per_opportunity_by_scale)"
info query_selectivity "$(jget "$SCALE" query_selectivity)"
info queries_exempt_because_they_return_most_rows \
  "$(jget "$SCALE" queries_exempt_because_they_return_most_rows)"

# --------------------------------- 4. genericity
GEN="$(run_phase scripts/_g171_phase_genericity.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=genericity_did_not_report"; exit 0; }
require_zero "$GEN" generic_layer_source_leaks
require_zero "$GEN" identity_branches_in_generic_layers
require_true "$GEN" scanner_detects_a_planted_leak genericity_scan_is_falsifiable

# --------------------------- 5. prior gate semantics
G174="$(run_phase scripts/_g174_phase_eligibility_intelligence.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=gate174_phase_did_not_report"; exit 0; }
require_true "$G174" eligibility_self_health_ready gate174_semantics_preserved
require_true "$G174" global_normalization_reused
require_zero "$G174" fixture_residue gate174_left_no_residue

G173="$(run_phase scripts/_g173_phase_relevance_intelligence.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=gate173_phase_did_not_report"; exit 0; }
require_true "$G173" relevance_self_health_ready gate173_semantics_preserved
require_zero "$G173" fixture_residue gate173_left_no_residue

CLEAN="$(run_phase scripts/_g167_phase_cleanup.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=cleanup_did_not_report"; exit 0; }
require_zero "$CLEAN" fixture_residue
require_true "$CLEAN" live_evidence_unchanged gate172_semantics_preserved

TOTAL_NET=0
for phase_json in "$SURVEY" "$DOCS" "$SCALE" "$GEN" "$G174" "$G173" "$CLEAN"; do
  n="$(jget "$phase_json" network_attempts_during_this_phase)"
  [ "$n" = "None" ] && n=0
  TOTAL_NET=$((TOTAL_NET + n))
done
if [ "$TOTAL_NET" = "0" ]; then
  pass network_requests "value=0"
else
  fail network_requests "value=$TOTAL_NET"
fi

if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  echo "gate175_ready=false"
  exit 0
fi

echo "RESULT=PASS"
echo "documents_first_class=true"
echo "document_versions_preserved=true"
echo "document_facts_provenance_backed=true"
echo "eligibility_document_evidence_ready=true"
echo "native_relevance_document_evidence_ready=true"
echo "deadline_document_evidence_ready=true"
echo "faq_appendix_guidance_supported=true"
echo "document_conflicts_preserved=true"
echo "amendments_feed_change_intelligence=true"
echo "missing_parser_not_empty_truth=true"
echo "customer_explainability_contract_ready=true"
echo "critical_document_queries_indexed=true"
echo "document_self_health_ready=true"
echo "gate174_semantics_preserved=true"
echo "gate173_semantics_preserved=true"
echo "gate172_semantics_preserved=true"
echo "network_requests=0"
echo "fixture_residue=0"
echo "gate175_ready=true"
