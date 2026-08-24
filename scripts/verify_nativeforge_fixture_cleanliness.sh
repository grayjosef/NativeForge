#!/usr/bin/env bash
# Prove committed corpus/source fixtures are unchanged after running a suite.
#
# Gate 77 found a test run silently rewriting committed evidence for a real
# federal grant. Gate 77B and Gate 78E guarded the four write paths that could
# do it. This script is the outer check: it does not care *how* a fixture got
# modified, only that none did.
#
# That matters because the per-service guards protect known paths. A future
# service, or a path nobody surveyed, would slip past them. This catches the
# class rather than the instance.
#
# Usage:
#   scripts/verify_nativeforge_fixture_cleanliness.sh                  # check current state
#   scripts/verify_nativeforge_fixture_cleanliness.sh --run-suite      # run the discovery suite first
#
# Exits non-zero if any tracked fixture is dirty.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 2

RUN_SUITE=0
for arg in "$@"; do
  case "$arg" in
    --run-suite) RUN_SUITE=1 ;;
    -h|--help)
      sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "check=usage status=FAIL unknown_argument=${arg}"
      echo "RESULT=FAIL"
      exit 2 ;;
  esac
done

FAIL=0

say() {
  local name="$1" status="$2" detail="${3:-}"
  echo "check=${name} status=${status}${detail:+ ${detail}}"
  [[ "$status" == "FAIL" ]] && FAIL=1
  return 0
}

# Directories holding committed evidence. Matches SOURCE_CONTROLLED_DIRS in
# hermetic_test_guard_service so the script and the guard cannot disagree about
# what counts as protected.
WATCHED=(
  "fixtures"
  "tests/fixtures"
  "src/nativeforge/data"
)

if [[ "$RUN_SUITE" -eq 1 ]]; then
  if [[ ! -x .venv/bin/python ]]; then
    say venv_present FAIL ".venv/bin/python not found"
    echo "RESULT=FAIL"
    exit 1
  fi
  say suite_run_requested PASS "running the discovery/corpus suite"
  .venv/bin/python -m pytest -q \
    tests/test_gate78_sc_state_source_lane.py \
    tests/test_gate77b_hermetic_federal_tests.py \
    tests/test_gate77_federal_source_lane.py \
    tests/test_gate76_source_registry_native_discovery.py \
    tests/test_sprint345_nf15_corrected_corpus.py \
    tests/test_ta_tier3_foundation_adapter.py \
    tests/test_la_scale_federal_activation.py \
    >/tmp/nf_fixture_cleanliness_suite.log 2>&1
  suite_rc=$?
  if [[ "$suite_rc" -eq 0 ]]; then
    say suite_passed PASS
  else
    # A failing suite is reported but does not mask the cleanliness verdict —
    # a run that both fails and dirties fixtures should say both.
    say suite_passed FAIL "exit=${suite_rc}; see /tmp/nf_fixture_cleanliness_suite.log"
  fi
fi

for dir in "${WATCHED[@]}"; do
  if [[ ! -d "$dir" ]]; then
    say "watched_dir_present:${dir}" SKIP "not present"
    continue
  fi
  # Flag MUTATION of committed evidence: modifications, deletions, renames.
  #
  # Excluded, deliberately:
  #   ??  untracked — a suite-created scratch file is not a rewrite of evidence
  #   A   staged addition — a deliberately added new fixture is not a mutation,
  #       and a test run cannot `git add`, so this opens no hole. A suite that
  #       created a file under a watched directory would show as ?? instead.
  #
  # Everything else (" M", "M ", "MM", " D", "D ", "R ") still fails, which is
  # the case that matters: a tracked evidence file changed underneath us.
  dirty="$(git status --porcelain=v1 -- "$dir" 2>/dev/null | grep -vE '^(\?\?|A )' || true)"
  if [[ -z "$dirty" ]]; then
    say "fixtures_clean:${dir}" PASS
  else
    say "fixtures_clean:${dir}" FAIL "modified tracked files below"
    printf '%s\n' "$dirty" | sed 's/^/    /'
  fi
done

# The specific record Gate 77 nearly lost, checked by content rather than by
# git status, so it is caught even if someone commits the corruption.
SAMHSA_FIXTURE="fixtures/real_grants_corpus/nf15_eligibility_reingest_pulls.json"
if [[ -f "$SAMHSA_FIXTURE" ]]; then
  if grep -q "SAMHSA / HHS" "$SAMHSA_FIXTURE" && grep -q "SM-26-024" "$SAMHSA_FIXTURE"; then
    say samhsa_evidence_intact PASS "SM-26-024 / SAMHSA / HHS"
  else
    say samhsa_evidence_intact FAIL "recorded SAMHSA evidence missing"
  fi
  if grep -q "HHS-IHS" "$SAMHSA_FIXTURE"; then
    say no_ihs_substitution FAIL "HHS-IHS present in committed evidence"
  else
    say no_ihs_substitution PASS
  fi
  if grep -q "Connection refused" "$SAMHSA_FIXTURE"; then
    say no_connection_error_placeholder FAIL "connection-error placeholder present"
  else
    say no_connection_error_placeholder PASS
  fi
else
  say samhsa_evidence_intact SKIP "fixture not present"
fi

if [[ "$FAIL" -ne 0 ]]; then
  say result FAIL
  echo "RESULT=FAIL"
  exit 1
fi
say result PASS
echo "RESULT=PASS"
exit 0
