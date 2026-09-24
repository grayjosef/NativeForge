#!/usr/bin/env bash
# Gate 176 — can NativeForge see funding coming before the solicitation, and
# admit what it missed after the award?
#
# RESULT=PASS only when a trace is evidence rather than an opportunity, when a
# cadence is refused below three observed cycles, when an absence cites the
# history that justifies it, when a correlation proposes without merging, when
# the coverage scorecard refuses to divide by a denominator nobody knows, and
# when all eight critical access paths find their rows by index at 120,000
# historical instances.
#
# THIS SCRIPT MAKES NO NETWORK CALL. Both phases replace `socket.socket` with
# one that raises and counts attempts, and the sum is asserted to be zero.
#
# THE MOST IMPORTANT LINE THIS SCRIPT PRINTS IS A FALSE ONE:
#
#   real_award_evidence_available_for_miss_detection=false
#
# All 2,757 award rows are Gate 138 demo fixtures on the protected demo
# organisation. Backward-error detection is built and proven and currently has
# nothing real to detect against. That is asserted FALSE deliberately: if it
# ever flips to true, somebody has either ingested real award data or
# contaminated the fixtures, and both deserve a human's attention.
#
# What is structural and what is INFO:
#
#   asserted   signal vocabulary and lifecycle, backward-error detection, the
#              demo-fixture exclusion, recurrence and its refusals, the
#              absence signal, correlation without merging, the scorecard's
#              refusal to divide, auto-onboarding prohibition, self-health
#              specificity, indexed access paths, 175 semantics, zero network
#   INFO       corpus recall and precision, query milliseconds, memory
#
# Corpus recall and precision are INFO, not assertions. They are measured
# against twenty-one cases we wrote, and promoting them to structural claims
# would turn "we handled the situations we imagined" into "our coverage is
# perfect" - which is exactly the fabricated confidence this gate exists to
# refuse.
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
require_at_least() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" != "None" ] && [ "$v" -ge "$3" ] 2>/dev/null; then
    pass "${4:-$2}" "value=$v"
  else
    fail "${4:-$2}" "expected>=$3 got=$v"
  fi
}

run_phase() {
  local out
  out="$(.venv/bin/python "$1" 2>&1 | tail -1)"
  printf '%s' "$out" | grep -q '^{' || return 1
  printf '%s' "$out"
}

echo "=== Gate 176: early signals, recurrence, and backward-error coverage ==="

PROOF="$(run_phase scripts/_g176_phase_proof.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=proof_phase_did_not_report"; exit 0; }

SCALE="$(run_phase scripts/_g176_phase_scale.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=scale_phase_did_not_report"; exit 0; }

# ---------------- 176A/B/C: the vocabulary and the lifecycle -------------
require_true "$PROOF" early_signal_types_ready
require_at_least "$PROOF" signal_type_count 13 signal_type_count

# ---------------- 176D/E: backward error detection -----------------------
require_true "$PROOF" award_backward_error_detector_ready
require_true "$PROOF" award_miss_does_not_invent_opportunity
require_true "$PROOF" demo_fixture_awards_excluded_from_real_metrics

# The honest measurement. Asserted FALSE: see the header.
require_false "$PROOF" real_award_evidence_available_for_miss_detection
info real_award_rows "value=$(jget "$PROOF" real_award_rows)"
info demo_fixture_award_rows "value=$(jget "$PROOF" demo_fixture_award_rows)"
info non_demo_award_rows "value=$(jget "$PROOF" non_demo_award_rows)"

# ---------------- 176F/G: recurrence and absence -------------------------
require_true "$PROOF" recurrence_intelligence_ready
require_true "$PROOF" insufficient_history_not_forecast
require_true "$PROOF" expected_absent_signal_ready

# ---------------- 176H: correlation --------------------------------------
require_true "$PROOF" early_signal_correlation_ready

# ---------------- 176I: the scorecard that refuses to divide -------------
require_true "$PROOF" coverage_miss_scorecard_ready
require_true "$PROOF" unknown_denominator_preserved

# ---------------- the refusal that protects the source fleet -------------
require_true "$PROOF" source_auto_onboarding_forbidden

# ---------------- 176J: the corpus ---------------------------------------
require_value "$PROOF" corpus_case_count 21 corpus_case_count
require_value "$PROOF" corpus_passed_count 21 corpus_passed_count
require_empty_list "$PROOF" corpus_failed_cases
require_true "$PROOF" every_temporal_case_pins_now
# A corpus that claimed to be world truth would be the gate's worst failure.
require_false "$PROOF" corpus_is_world_truth

# Measured against twenty-one cases we wrote. INFO, and it stays INFO.
info miss_detection_recall "value=$(jget "$PROOF" miss_detection_recall) scope=corpus_only"
info miss_detection_precision "value=$(jget "$PROOF" miss_detection_precision) scope=corpus_only"
info recurrence_false_positive_count "value=$(jget "$PROOF" recurrence_false_positive_count)"
info recurrence_unknown_count "value=$(jget "$PROOF" recurrence_unknown_count)"
info unresolved_signal_count "value=$(jget "$PROOF" unresolved_signal_count)"
info review_required_count "value=$(jget "$PROOF" review_required_count)"

# ---------------- 176K: scale and the access paths -----------------------
require_true "$SCALE" target_is_scratch scale_ran_against_scratch_db
require_at_least "$SCALE" historical_instances 100000 historical_instances
require_value "$SCALE" critical_query_count 8 critical_query_count
# No zero-row fake proof: a query returning nothing has a beautiful plan.
require_empty_list "$SCALE" zero_row_queries
require_empty_list "$SCALE" unindexed_queries
# And the scan detector must still be able to say "table scan".
require_true "$SCALE" scan_detector_still_fires
require_true "$SCALE" critical_signal_queries_indexed
require_true "$PROOF" every_critical_query_names_its_index

info slowest_critical_query_ms "value=$(jget "$SCALE" slowest_critical_query_ms)"
info scale_peak_memory_mb "value=$(jget "$SCALE" peak_memory_mb)"
info scale_load_seconds "value=$(jget "$SCALE" load_seconds)"

# ---------------- 176L: self health --------------------------------------
require_true "$PROOF" signal_self_health_ready
require_value "$PROOF" self_health_detector_count 10 self_health_detector_count

# ---------------- what came before must still hold -----------------------
require_true "$PROOF" gate175_semantics_preserved

# ---------------- the boundaries -----------------------------------------
require_zero "$PROOF" network_requests proof_phase_network_requests
require_zero "$SCALE" network_requests scale_phase_network_requests
require_zero "$PROOF" fixture_residue

require_true "$PROOF" gate176_ready

echo
if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "early_signal_types_ready=true"
echo "award_backward_error_detector_ready=true"
echo "real_award_evidence_available_for_miss_detection=false"
echo "demo_fixture_awards_excluded_from_real_metrics=true"
echo "award_miss_does_not_invent_opportunity=true"
echo "recurrence_intelligence_ready=true"
echo "insufficient_history_not_forecast=true"
echo "expected_absent_signal_ready=true"
echo "early_signal_correlation_ready=true"
echo "coverage_miss_scorecard_ready=true"
echo "unknown_denominator_preserved=true"
echo "source_auto_onboarding_forbidden=true"
echo "critical_signal_queries_indexed=true"
echo "signal_self_health_ready=true"
echo "gate175_semantics_preserved=true"
echo "network_requests=0"
echo "fixture_residue=0"
echo "gate176_ready=true"
