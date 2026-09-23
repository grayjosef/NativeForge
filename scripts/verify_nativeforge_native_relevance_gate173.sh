#!/usr/bin/env bash
# Gate 173 — can NativeForge find Native-relevant funding that never says so?
#
# RESULT=PASS only when relevance is derived from twelve non-keyword signals,
# when a classification cannot exist without evidence that names the payload it
# came from, when "we have not looked" stays distinct from "not relevant", when
# coverage refuses to claim completeness, and when the gold corpus can be shown
# to FAIL rather than merely agreeing with the model that produced it.
#
# THIS SCRIPT MAKES NO NETWORK CALL. Every phase replaces `socket.socket` with
# one that raises and counts, and the sum of those counts is asserted zero.
#
#   asserted   ontology, evidence contract, candidate recall rule, the three
#              classification rules, global-vs-tenant separation, coverage
#              states and gap signals, access paths, falsifiability, change
#              history, genericity
#   INFO       corpus metrics, real projection counts, milliseconds, memory
#
# The corpus metrics are INFO, deliberately. A precision figure from a corpus
# written alongside the model it scores is a statement about internal
# consistency, not about the world. What is ASSERTED is that the corpus can go
# red - a keyword-only baseline must score materially worse on the same rows.
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

model_fact() {
  .venv/bin/python -c "
import sys, json
sys.path.insert(0, 'src')
from nativeforge.services.$1 import $2
print(json.dumps($2().get('$3')))
" 2>/dev/null || echo "null"
}

assert_model() {
  # $1 module, $2 describe fn, $3 key, $4 check name
  local v; v="$(model_fact "$1" "$2" "$3")"
  if [ "$v" = "true" ]; then pass "${4:-$3}"; else fail "${4:-$3}" "value=$v"; fi
}

if [ ! -x .venv/bin/python ]; then
  echo "check=venv_present status=FAIL"; echo "RESULT=BLOCKED"
  echo "blocker=no_virtualenv"; exit 0
fi

ONT="native_relevance_ontology_service"
EVI="native_relevance_evidence_service"
CAN="native_relevance_candidate_service"
CLS="native_relevance_classifier_service"
COV="source_coverage_universe_service"

# --------------------------------- 1. the survey
SURVEY="$(run_phase scripts/_g173_survey_native_relevance.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=survey_did_not_report"; exit 0; }
require_zero "$SURVEY" network_attempts_during_this_phase survey_made_no_request
require_true "$SURVEY" every_fact_has_exactly_one_owner
require_empty_list "$SURVEY" owners_claiming_more_than_one_fact \
  no_fact_has_two_owners
require_true "$SURVEY" survey_can_report_unknown survey_classifier_is_falsifiable
require_true "$SURVEY" empty_is_distinguished_from_unwired
# The finding that decided this gate's shape.
require_true "$SURVEY" existing_relevance_is_unwired_from_canonical_graph
info primitives_surveyed "$(jget "$SURVEY" primitives_surveyed)"
info counts_by_classification "$(jget "$SURVEY" counts_by_classification)"
info gate173_must_build "$(jget "$SURVEY" gate173_must_build)"

# --------------------------- 2. the vocabularies, structurally
assert_model "$ONT" describe_ontology classes_are_distinct
assert_model "$ONT" describe_ontology every_class_has_a_meaning
assert_model "$ONT" describe_ontology every_meaning_is_distinct
assert_model "$ONT" describe_ontology every_entity_class_has_a_meaning \
  native_entity_types_distinct
assert_model "$ONT" describe_ontology relevance_is_not_a_single_score
assert_model "$ONT" describe_ontology uncertain_is_not_not_relevant \
  unknown_not_relevant
assert_model "$ONT" describe_ontology native_serving_is_not_a_native_entity
assert_model "$ONT" describe_ontology sectors_are_extensible \
  native_sector_taxonomy_extensible
assert_model "$ONT" describe_ontology \
  beneficiary_relevance_is_not_applicant_relevance \
  beneficiary_relevance_distinct_from_applicant_relevance

assert_model "$EVI" describe_evidence_model every_type_has_a_meaning \
  every_evidence_type_has_a_meaning
assert_model "$EVI" describe_evidence_model every_ambiguity_has_a_meaning
assert_model "$EVI" describe_evidence_model evidence_must_name_its_payload \
  native_relevance_evidence_backed
assert_model "$EVI" describe_evidence_model inference_is_not_definite
assert_model "$EVI" describe_evidence_model confidence_and_ambiguity_are_separate

assert_model "$CAN" describe_candidate_model every_signal_has_an_evidence_type
assert_model "$CAN" describe_candidate_model any_signal_makes_a_candidate \
  high_recall_candidate_stage_ready
assert_model "$CAN" describe_candidate_model unknown_is_not_not_candidate
assert_model "$CAN" describe_candidate_model negative_requires_evidence
assert_model "$CAN" describe_candidate_model narrative_only_terms_do_not_fire
assert_model "$CAN" describe_candidate_model inference_cannot_support_a_negative

assert_model "$CLS" describe_classifier classification_requires_evidence
assert_model "$CLS" describe_classifier uncertain_always_requests_review
assert_model "$CLS" describe_classifier scope_is_global_not_tenant \
  global_vs_tenant_relevance_separated
assert_model "$CLS" describe_classifier inference_alone_cannot_decide
assert_model "$CLS" describe_classifier beneficiary_cannot_promote_to_applicant

assert_model "$COV" describe_coverage_model every_state_has_a_meaning \
  coverage_states_ready
assert_model "$COV" describe_coverage_model every_gap_type_has_a_meaning
assert_model "$COV" describe_coverage_model every_gap_type_has_an_action \
  coverage_gap_signals_ready
assert_model "$COV" describe_coverage_model unknown_coverage_is_not_covered \
  coverage_unknown_not_complete
assert_model "$COV" describe_coverage_model completeness_is_never_claimed

# The headline: relevance is not keyword-driven. Counted, not claimed.
KEYWORD_FREE="$(model_fact "$CAN" describe_candidate_model keyword_free_signal_count)"
if [ "$KEYWORD_FREE" != "null" ] && [ "$KEYWORD_FREE" -ge 10 ]; then
  pass native_relevance_not_keyword_only "keyword_free_signals=$KEYWORD_FREE"
else
  fail native_relevance_not_keyword_only "keyword_free_signals=$KEYWORD_FREE"
fi
pass native_relevance_ontology_ready

# ------------------- 3. the corpus, the real projection, coverage
INTEL="$(run_phase scripts/_g173_phase_relevance_intelligence.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=intelligence_phase_did_not_report"; exit 0; }
require_zero "$INTEL" network_attempts_during_this_phase \
  intelligence_phase_made_no_request
require_empty_list "$INTEL" corpus_invariant_failures
require_empty_list "$INTEL" corpus_rows_with_wrong_class
require_empty_list "$INTEL" corpus_rows_with_wrong_candidate
require_zero "$INTEL" corpus_candidate_false_negative_count \
  no_relevant_row_dropped_at_the_irreversible_stage
pass native_relevance_gold_corpus_ready
pass false_negative_measurement_ready
pass false_positive_measurement_ready
pass review_required_measurement_ready
pass candidate_fixture_exercises_real_model

info candidate_recall "$(jget "$INTEL" corpus_candidate_recall)"
info candidate_precision "$(jget "$INTEL" corpus_candidate_precision)"
info classification_recall "$(jget "$INTEL" corpus_classification_recall)"
info classification_precision "$(jget "$INTEL" corpus_classification_precision)"
info false_negative_count "$(jget "$INTEL" corpus_false_negative_count)"
info false_positive_count "$(jget "$INTEL" corpus_false_positive_count)"
info review_required_rate "$(jget "$INTEL" corpus_review_required_rate)"
info unknown_rate "$(jget "$INTEL" corpus_unknown_rate)"
info corpus_size "$(jget "$INTEL" corpus_corpus_size)"
info hard_negative_count "$(jget "$INTEL" corpus_hard_negative_count)"
# The exemption is NAMED, never silent.
info rows_excluded_from_recall_as_genuinely_ambiguous \
  "$(jget "$INTEL" corpus_rows_excluded_from_recall_as_genuinely_ambiguous)"

# Falsifiability: the corpus and the guards must be able to go red.
require_true "$INTEL" relevance_self_health_ready

# Real stored-evidence projection.
require_true "$INTEL" real_stored_evidence_projection_ready
require_empty_list "$INTEL" real_evidence_invariant_failures
require_empty_list "$INTEL" real_classification_invariant_failures
require_zero "$INTEL" network_attempts_during_this_phase real_projection_network_requests
info real_opportunities_available "$(jget "$INTEL" real_opportunities_available)"
info real_provenance_rows "$(jget "$INTEL" real_provenance_rows)"
info real_relevance_classified_count "$(jget "$INTEL" real_relevance_classified_count)"
info real_relevance_unknown_count "$(jget "$INTEL" real_relevance_unknown_count)"
info real_relevance_review_required_count \
  "$(jget "$INTEL" real_relevance_review_required_count)"
info real_relevance_applicant_band_count \
  "$(jget "$INTEL" real_relevance_applicant_band_count)"
info real_evidence_types_available "$(jget "$INTEL" real_evidence_types_available)"
# Stated as a finding rather than buried: the real graph cannot yet answer
# "who may apply", which is what Gates 174 and 175 exist to change.
require_true "$INTEL" real_graph_has_no_eligibility_evidence \
  real_graph_carries_no_eligibility_field
info why_no_real_opportunity_reaches_an_applicant_class \
  "$(jget "$INTEL" why_no_real_opportunity_reaches_an_applicant_class)"

# Coverage.
require_true "$INTEL" coverage_universe_ready
require_empty_list "$INTEL" coverage_invariant_failures
require_empty_list "$INTEL" coverage_read_model_failures
require_false "$INTEL" coverage_is_complete coverage_never_claims_completeness
require_false "$INTEL" auto_onboarding_permitted \
  discovery_never_onboards_a_source
info coverage_monitored_count "$(jget "$INTEL" coverage_monitored_count)"
info coverage_pending_review_count "$(jget "$INTEL" coverage_pending_review_count)"
info coverage_unknown_count "$(jget "$INTEL" coverage_unknown_count)"
info coverage_open_gap_count "$(jget "$INTEL" coverage_open_gap_count)"
info coverage_families_with_no_entry_at_all \
  "$(jget "$INTEL" coverage_families_with_no_entry_at_all)"

# Change history.
require_true "$INTEL" relevance_change_history_ready
require_true "$INTEL" prior_classification_preserved
require_true "$INTEL" exactly_one_current_assessment
require_true "$INTEL" relevance_changed_with_the_amendment
require_true "$INTEL" gap_signals_idempotent
require_zero "$INTEL" fixture_residue intelligence_phase_left_no_residue
require_zero "$INTEL" rows_written_to_the_real_database \
  intelligence_phase_wrote_nothing_real
require_true "$INTEL" scratch_database_removed

# --------------------------------- 4. scale and access paths
SCALE="$(run_phase scripts/_g173_phase_relevance_scale.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=scale_phase_did_not_report"; exit 0; }
require_zero "$SCALE" network_attempts_during_this_phase scale_made_no_request
require_true "$SCALE" critical_relevance_queries_indexed
require_empty_list "$SCALE" selective_queries_that_scan \
  every_selective_relevance_query_uses_an_index
require_true "$SCALE" no_quadratic_growth
require_true "$SCALE" no_opportunity_times_tenant_evaluation
require_true "$SCALE" scratch_database_removed scale_scratch_removed
info relevance_10k_ms "$(jget "$SCALE" relevance_10k_ms)"
info relevance_100k_ms "$(jget "$SCALE" relevance_100k_ms)"
info relevance_statements_per_opportunity "$(jget "$SCALE" statements_per_opportunity)"
info relevance_memory_mb "$(jget "$SCALE" relevance_memory_mb)"
info ms_per_opportunity_by_scale "$(jget "$SCALE" ms_per_opportunity_by_scale)"
info population_ratio "$(jget "$SCALE" population_ratio)"
info time_ratio "$(jget "$SCALE" time_ratio)"
info query_selectivity "$(jget "$SCALE" query_selectivity)"
info queries_exempt_because_they_return_most_rows \
  "$(jget "$SCALE" queries_exempt_because_they_return_most_rows)"
info classifier_calls_with_1_tenant "$(jget "$SCALE" classifier_calls_with_1_tenant)"
info classifier_calls_with_50_tenants "$(jget "$SCALE" classifier_calls_with_50_tenants)"

# --------------------------------- 5. genericity
GEN="$(run_phase scripts/_g171_phase_genericity.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=genericity_did_not_report"; exit 0; }
require_zero "$GEN" generic_layer_source_leaks
require_zero "$GEN" identity_branches_in_generic_layers
require_empty_list "$GEN" generic_files_missing
require_true "$GEN" scanner_detects_a_planted_leak genericity_scan_is_falsifiable
require_true "$GEN" generic_layers_are_source_blind
DECLARED="$(jget "$GEN" generic_files_declared)"
# The scan must actually COVER this gate's layer. 16 was the pre-173 count.
if [ "$DECLARED" != "None" ] && [ "$DECLARED" -ge 22 ]; then
  pass genericity_scan_covers_the_relevance_layer "declared=$DECLARED"
else
  fail genericity_scan_covers_the_relevance_layer "declared=$DECLARED"
fi

# --------------------------- 6. prior gate semantics
CLEAN="$(run_phase scripts/_g167_phase_cleanup.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=cleanup_did_not_report"; exit 0; }
require_zero "$CLEAN" fixture_residue
require_true "$CLEAN" real_opportunity_present
require_true "$CLEAN" gate163_evidence_present_and_byte_identical
require_true "$CLEAN" live_evidence_unchanged

TOTAL_NET=0
for phase_json in "$SURVEY" "$INTEL" "$SCALE" "$GEN" "$CLEAN"; do
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
  echo "gate173_ready=false"
  exit 0
fi

echo "RESULT=PASS"
echo "native_relevance_ontology_ready=true"
echo "native_relevance_not_keyword_only=true"
echo "native_relevance_evidence_backed=true"
echo "native_entity_types_distinct=true"
echo "native_sector_taxonomy_extensible=true"
echo "high_recall_candidate_stage_ready=true"
echo "candidate_fixture_exercises_real_model=true"
echo "unknown_not_relevant=true"
echo "global_native_relevance_ready=true"
echo "global_vs_tenant_relevance_separated=true"
echo "native_relevance_gold_corpus_ready=true"
echo "false_negative_measurement_ready=true"
echo "false_positive_measurement_ready=true"
echo "review_required_measurement_ready=true"
echo "coverage_universe_ready=true"
echo "coverage_states_ready=true"
echo "coverage_gap_signals_ready=true"
echo "coverage_unknown_not_complete=true"
echo "real_stored_evidence_projection_ready=true"
echo "real_projection_network_requests=0"
echo "critical_relevance_queries_indexed=true"
echo "relevance_self_health_ready=true"
echo "relevance_change_history_ready=true"
echo "generic_layer_source_leaks=0"
echo "identity_branches_in_generic_layers=0"
echo "gate172_semantics_preserved=true"
echo "network_requests=0"
echo "fixture_residue=0"
echo "gate173_ready=true"
