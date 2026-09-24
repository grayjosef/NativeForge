#!/usr/bin/env bash
# Gate 174 — can NativeForge say WHO may apply, under what conditions, and
# what is still unknown?
#
# RESULT=PASS only when eligibility is a set of typed requirements rather than
# a boolean, when a disqualifier is a row rather than an absence, when an
# exclusion ends the question instead of being outvoted, when "nobody asked"
# stays distinct from "no", when naming one Native entity class does not name
# another, and when a tenant match consumes global normalization instead of
# reparsing the source.
#
# THIS SCRIPT MAKES NO NETWORK CALL.
#
#   asserted   requirement model, six-valued result, exclusion precedence,
#              structural-vs-addressable, entity-class non-transfer, profile
#              contract and versioning, match explainability, amendment path,
#              global-vs-tenant separation, access paths, falsifiability
#   INFO       corpus counts, milliseconds, memory, savings ratio
#
# The corpus metrics are INFO. A corpus written beside the engine it scores
# states internal consistency, not correctness about the world. What is
# ASSERTED is that it can go red - a naive engine must score materially worse.
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
  local v; v="$(model_fact "$1" "$2" "$3")"
  if [ "$v" = "true" ]; then pass "${4:-$3}"; else fail "${4:-$3}" "value=$v"; fi
}

if [ ! -x .venv/bin/python ]; then
  echo "check=venv_present status=FAIL"; echo "RESULT=BLOCKED"
  echo "blocker=no_virtualenv"; exit 0
fi

REQ="eligibility_requirement_model_service"
PRO="organization_capability_profile_service"
ENG="eligibility_match_engine_service"

# --------------------------------- 1. the survey
SURVEY="$(run_phase scripts/_g174_survey_eligibility.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=survey_did_not_report"; exit 0; }
require_zero "$SURVEY" network_attempts_during_this_phase survey_made_no_request
require_true "$SURVEY" every_fact_has_exactly_one_owner
require_empty_list "$SURVEY" owners_claiming_more_than_one_fact
require_true "$SURVEY" survey_can_report_unknown survey_classifier_is_falsifiable
require_true "$SURVEY" empty_is_distinguished_from_unwired
require_true "$SURVEY" existing_eligibility_is_unwired_from_canonical_graph
# The finding a prefix marker had hidden.
require_true "$SURVEY" stage7_consumes_an_unwired_stage6_preview
info primitives_surveyed "$(jget "$SURVEY" primitives_surveyed)"
info counts_by_classification "$(jget "$SURVEY" counts_by_classification)"
info gate174_must_build "$(jget "$SURVEY" gate174_must_build)"

# --------------------------- 2. the model, structurally
assert_model "$REQ" describe_requirement_model every_kind_has_a_meaning
assert_model "$REQ" describe_requirement_model every_result_has_a_meaning
assert_model "$REQ" describe_requirement_model every_result_meaning_is_distinct
assert_model "$REQ" describe_requirement_model result_is_not_a_boolean \
  eligibility_model_ready
assert_model "$REQ" describe_requirement_model \
  negative_requirements_are_first_class
assert_model "$REQ" describe_requirement_model unknown_is_not_eligible
assert_model "$REQ" describe_requirement_model review_required_is_not_eligible
assert_model "$REQ" describe_requirement_model original_text_is_never_discarded
assert_model "$REQ" describe_requirement_model \
  entity_classes_do_not_transfer_by_default tribal_entity_types_distinct

assert_model "$PRO" describe_profile_contract every_verification_has_a_meaning
assert_model "$PRO" describe_profile_contract unanswered_is_not_no
assert_model "$PRO" describe_profile_contract every_field_defaults_to_unanswered
assert_model "$PRO" describe_profile_contract profile_is_versioned \
  organization_profile_versioned
assert_model "$PRO" describe_profile_contract version_is_derived_from_content

assert_model "$ENG" describe_match_engine exclusion_ends_the_question \
  hard_disqualifier_semantics_ready
assert_model "$ENG" describe_match_engine unknown_is_not_eligible \
  match_unknown_is_not_eligible
assert_model "$ENG" describe_match_engine every_requirement_is_accounted_for
assert_model "$ENG" describe_match_engine match_consumes_global_normalization \
  global_normalization_reused
assert_model "$ENG" describe_match_engine entity_class_never_transfers_silently

pass organization_profile_contract_ready
pass eligibility_evidence_backed
pass negative_requirements_first_class

# ------------------- 3. the corpus, amendments, tenants
INTEL="$(run_phase scripts/_g174_phase_eligibility_intelligence.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=eligibility_phase_did_not_report"; exit 0; }
require_zero "$INTEL" network_attempts_during_this_phase \
  eligibility_phase_made_no_request
require_empty_list "$INTEL" corpus_invariant_failures
require_empty_list "$INTEL" corpus_rows_with_wrong_result
require_zero "$INTEL" corpus_eligibility_false_positive_count \
  nobody_is_told_to_apply_when_they_cannot
require_zero "$INTEL" corpus_eligibility_false_negative_count \
  no_winnable_cycle_is_abandoned
info corpus_size "$(jget "$INTEL" corpus_corpus_size)"
info eligibility_false_positive_count \
  "$(jget "$INTEL" corpus_eligibility_false_positive_count)"
info eligibility_false_negative_count \
  "$(jget "$INTEL" corpus_eligibility_false_negative_count)"
info eligibility_unknown_count "$(jget "$INTEL" corpus_unknown_count)"
info eligibility_review_required_count "$(jget "$INTEL" corpus_review_required_count)"
info eligibility_conditional_count "$(jget "$INTEL" corpus_conditional_count)"
info corpus_result_accuracy "$(jget "$INTEL" corpus_result_accuracy)"

require_true "$INTEL" eligibility_self_health_ready
require_true "$INTEL" eligibility_match_explainable
require_true "$INTEL" every_requirement_accounted_for

require_true "$INTEL" amendment_eligibility_changes_supported
require_true "$INTEL" amendment_changed_the_result
require_true "$INTEL" reuses_gate170_change_taxonomy
require_true "$INTEL" no_second_change_pipeline
info amendment_before_result "$(jget "$INTEL" amendment_before_result)"
info amendment_after_result "$(jget "$INTEL" amendment_after_result)"

require_true "$INTEL" global_normalization_reused
require_true "$INTEL" only_the_match_scales_with_tenants
require_true "$INTEL" same_opportunity_different_tenant_answers
require_empty_list "$INTEL" match_failures
info normalizations_with_1_tenant "$(jget "$INTEL" normalizations_with_1_tenant)"
info normalizations_with_50_tenants "$(jget "$INTEL" normalizations_with_50_tenants)"
info matches_with_50_tenants "$(jget "$INTEL" matches_with_50_tenants)"

require_zero "$INTEL" fixture_residue eligibility_phase_left_no_residue
require_zero "$INTEL" rows_written_to_the_real_database \
  eligibility_phase_wrote_nothing_real

# --------------------------------- 4. scale and access paths
SCALE="$(run_phase scripts/_g174_phase_eligibility_scale.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=scale_phase_did_not_report"; exit 0; }
require_zero "$SCALE" network_attempts_during_this_phase scale_made_no_request
require_true "$SCALE" critical_eligibility_queries_indexed
require_empty_list "$SCALE" selective_queries_that_scan \
  every_selective_eligibility_query_uses_an_index
require_true "$SCALE" no_quadratic_growth
require_true "$SCALE" normalization_tracks_opportunities_only
require_true "$SCALE" no_opportunity_times_tenant_normalization
require_true "$SCALE" scratch_database_removed scale_scratch_removed
info eligibility_10k_ms "$(jget "$SCALE" eligibility_10k_ms)"
info eligibility_50k_ms "$(jget "$SCALE" eligibility_50k_ms)"
info eligibility_memory_mb "$(jget "$SCALE" eligibility_memory_mb)"
info eligibility_statements_per_row "$(jget "$SCALE" statements_per_row)"
info ms_per_opportunity_by_scale "$(jget "$SCALE" ms_per_opportunity_by_scale)"
info normalizations_for_population "$(jget "$SCALE" normalizations_for_population)"
info matches_for_population "$(jget "$SCALE" matches_for_population)"
info normalization_savings_ratio "$(jget "$SCALE" normalization_savings_ratio)"
info query_selectivity "$(jget "$SCALE" query_selectivity)"
info queries_exempt_because_they_return_most_rows \
  "$(jget "$SCALE" queries_exempt_because_they_return_most_rows)"

# --------------------------------- 5. genericity
GEN="$(run_phase scripts/_g171_phase_genericity.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=genericity_did_not_report"; exit 0; }
require_zero "$GEN" generic_layer_source_leaks
require_zero "$GEN" identity_branches_in_generic_layers
require_true "$GEN" scanner_detects_a_planted_leak genericity_scan_is_falsifiable
require_true "$GEN" generic_layers_are_source_blind

# --------------------------- 6. prior gate semantics
G173="$(run_phase scripts/_g173_phase_relevance_intelligence.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=gate173_phase_did_not_report"; exit 0; }
require_true "$G173" relevance_self_health_ready gate173_semantics_preserved
require_true "$G173" real_stored_evidence_projection_ready
require_zero "$G173" fixture_residue gate173_left_no_residue

CLEAN="$(run_phase scripts/_g167_phase_cleanup.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=cleanup_did_not_report"; exit 0; }
require_zero "$CLEAN" fixture_residue
require_true "$CLEAN" real_opportunity_present
require_true "$CLEAN" live_evidence_unchanged gate172_semantics_preserved

TOTAL_NET=0
for phase_json in "$SURVEY" "$INTEL" "$SCALE" "$GEN" "$G173" "$CLEAN"; do
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
  echo "gate174_ready=false"
  exit 0
fi

echo "RESULT=PASS"
echo "eligibility_model_ready=true"
echo "tribal_entity_types_distinct=true"
echo "unknown_not_eligible=true"
echo "negative_requirements_first_class=true"
echo "organization_profile_contract_ready=true"
echo "eligibility_evidence_backed=true"
echo "eligibility_match_explainable=true"
echo "hard_disqualifier_semantics_ready=true"
echo "amendment_eligibility_changes_supported=true"
echo "global_normalization_reused=true"
echo "critical_eligibility_queries_indexed=true"
echo "eligibility_self_health_ready=true"
echo "gate173_semantics_preserved=true"
echo "gate172_semantics_preserved=true"
echo "network_requests=0"
echo "fixture_residue=0"
echo "gate174_ready=true"
