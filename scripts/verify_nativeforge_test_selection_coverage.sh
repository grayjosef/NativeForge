#!/usr/bin/env bash
# Gate 84C — prove the recurring gate `-k` selection still reaches the tests
# that must never fail invisibly.
#
# Gate 84B measured the full suite for the first time and found six failing
# tests behind a regression number that had read "0 failed" for several gates.
# All six were deterministic failures; the recurring scoped `-k` simply never
# selected them.
#
# This script does not demand 100% selection - the broad expression is a
# deliberate subset and running everything takes ~35 minutes. It demands that
# the tests we know can rot silently are inside it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

# shellcheck disable=SC1091
source .venv/bin/activate

# The broad expression used by the recurring gate validation. Keep in step with
# the gate prompts; a keyword dropped here is a keyword dropped there.
#
# `fit_dimension`, `readiness` and `gate37` were added by Gate 84C. Without them
# the expression did not reach four of the six critical tests below - which is
# precisely how those tests failed unnoticed for several gates.
#
# `deadline`, `normalization` and `freshness` were added by Gate 86. Its 71 new
# tests landed in a module whose name shares no keyword with this expression,
# so only 6 of them were selected - the same failure this guard exists to catch,
# caught here by the guard rather than several gates later by accident.
#
# `awarded`, `pursuit`, `reporting`, `lifecycle`, `attachment` and `extraction`
# were added by Gate 91, for the same reason and caught the same way: 3 of its
# 67 tests were selected. Twice now the guard has caught a new module falling
# outside the expression on the gate that introduced it, which is the intended
# cadence.
GATE_K='order_independence or recognition_requirement_coverage_expansion or sprint348_nf15_closeout or fit_dimension or readiness or gate37 or audit_state or audit_refs or demo_payload or negative_intelligence or sc_customer_demo or notice_ingestion or notice_artifact or html_notice or pdf_notice or nofo or notice or amendment or eligibility_exclusion or excluded_by_evidence or funding_lane or south_carolina or sc_state or sc_source or sc_native or state_recognized or federally_recognized or grants_gov or federal or corpus or fixture or source or opportunity or discovery or stale or duplicate or native or capability or audit or invite or approval or backup or restore or storage or postgres or rls or membership or identity or oidc or auth or token or tenant or rbac or role or authority or claim or demo or deadline or normalization or freshness or awarded or pursuit or reporting or lifecycle or attachment or extraction'

# Tests that have already rotted invisibly once, plus the few whose silent loss
# would be worst. Every one is a node id, so a rename shows up here as a failure
# rather than as silent loss of coverage.
CRITICAL=(
  "tests/test_recognition_requirement_coverage_expansion.py::test_unknown_count_drops_ac1"
  "tests/test_sprint348_nf15_closeout.py::test_nf15_gate_and_closeout"
  "tests/test_sprint197_eligibility_fit_assessment_dimension_vocabulary.py::test_fit_dimensions_are_the_declared_set"
  "tests/test_sprint222_matching_readiness_readiness_evaluator.py::test_incomplete_profile_blocked_readiness"
  "tests/test_sprint4202_gate37_production_grade_hardening.py::test_busy_preview_port_blocks_serve"
  "tests/test_sprint4202_gate37_production_grade_hardening.py::test_verifier_fail_when_server_down"
  # Gate 85. Not yet rotted, but these are the two whose quiet disappearance
  # would be hardest to notice and most expensive: one holds the federally
  # recognized / state recognized split apart, the other keeps the baseline
  # from claiming a source is monitored.
  "tests/test_gate85_discovery_baseline_x.py::test_recognition_tiers_are_not_collapsed_into_one_answer"
  "tests/test_gate85_discovery_baseline_x.py::test_no_source_is_monitored"
  # Gate 86. The two that keep normalization from turning into fabrication:
  # one bounds freshness to records that have both a date and a check, the
  # other keeps the raw deadline count from moving.
  "tests/test_gate86_deadline_normalization.py::test_freshness_requires_both_a_normalized_date_and_a_check"
  "tests/test_gate86_deadline_normalization.py::test_raw_deadline_count_is_preserved"
  # Gate 91. The rule that a grant may not become an awarded record by
  # backend assignment - GrantPipelineStage.awarded is still an assignable
  # enum member, so this is the test most likely to matter and most likely
  # to be quietly lost in a refactor.
  "tests/test_gate91_awarded_vs_pursuit_reporting_parser.py::test_backend_enum_assignment_alone_is_not_a_valid_transition"
  "tests/test_gate91_awarded_vs_pursuit_reporting_parser.py::test_projected_and_active_are_structurally_distinct"
)

FAIL=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "verify=test_selection_coverage"

python -m pytest tests -q --collect-only 2>/dev/null \
  | grep '::' > "$TMP/all.txt" || true
python -m pytest tests -q --collect-only -k "$GATE_K" 2>/dev/null \
  | grep '::' > "$TMP/selected.txt" || true

TOTAL="$(wc -l < "$TMP/all.txt" | tr -d ' ')"
SELECTED="$(wc -l < "$TMP/selected.txt" | tr -d ' ')"
UNSELECTED=$((TOTAL - SELECTED))

if [[ "$TOTAL" -lt 1 ]]; then
  echo "check=collection status=FAIL collected nothing"
  echo "RESULT=FAIL"
  exit 1
fi

PCT=$(( SELECTED * 100 / TOTAL ))
echo "check=collected status=PASS total=${TOTAL}"
echo "check=selected_by_gate_expression status=PASS selected=${SELECTED} (${PCT}%)"
echo "check=unselected status=INFO unselected=${UNSELECTED}"

# Every critical test must exist, and must be inside the gate selection.
for node in "${CRITICAL[@]}"; do
  name="${node##*::}"
  if ! grep -qF "$node" "$TMP/all.txt"; then
    echo "check=critical_exists:${name} status=FAIL not collected (renamed or removed?)"
    FAIL=1
    continue
  fi
  if grep -qF "$node" "$TMP/selected.txt"; then
    echo "check=critical_selected:${name} status=PASS"
  else
    echo "check=critical_selected:${name} status=FAIL not reached by the gate -k"
    FAIL=1
  fi
done

# A selection that has collapsed to almost nothing is a broken expression, not
# a deliberate subset.
if [[ "$PCT" -lt 50 ]]; then
  echo "check=selection_breadth status=FAIL only ${PCT}% selected"
  FAIL=1
else
  echo "check=selection_breadth status=PASS ${PCT}%"
fi

if [[ "$FAIL" -eq 0 ]]; then
  echo "RESULT=PASS"
else
  echo "RESULT=FAIL"
fi
exit "$FAIL"
