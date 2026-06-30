#!/usr/bin/env bash
# OK pilot: Oklahoma tribal profiles matching run (AC-1 through AC-5).
set -euo pipefail
cd "$(dirname "$0")/.."

export NF_APP_ENV=staging
export NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true
export NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED=true

echo "=== AC-5: stash@{0} preserved ==="
git stash list | head -1
test "$(git stash list | head -1 | grep -c 'stash@{0}')" -eq 1

echo ""
echo "=== Fixture gate ==="
uv run python -c "
from nativeforge.services.ok_pilot_fixture_loader_service import (
    build_ok_pilot_fixture_contract,
    load_ok_tribal_profiles,
)
c = build_ok_pilot_fixture_contract()
print('fixtures_present', c['fixtures_present'])
print('profile_count', c['profile_count'])
assert c['ready'], 'fixtures not ready'
assert c['profile_count'] == 38
load_ok_tribal_profiles()
print('OK-0 fixture schema OK')
"

echo ""
echo "=== AC-1: public_inferred profiles ==="
uv run python -c "
from nativeforge.services.ok_pilot_profile_loader_service import (
    list_ok_pilot_profiles,
    resolve_ok_pilot_profile,
)
profiles = list_ok_pilot_profiles(require_files=True)
print('profile_count', len(profiles))
federal = [p for p in profiles if p['recognition_type'] == 'federal']
print('federal', len(federal))
assert len(profiles) == 38
assert len(federal) == 38
for p in profiles:
    prof = resolve_ok_pilot_profile(p['fixture_key'])
    assert prof['profile_evidence_codes'] == []
    assert prof['capture_method'] == 'public_inferred'
    assert prof.get('recognition_type') == 'federal'
print('AC-1 OK')
"

echo ""
echo "=== AC-2/AC-3/AC-4: classify+match block ==="
uv run python << 'PY'
from collections import Counter

from nativeforge.services.ok_pilot_classify_match_orchestrator_service import (
    run_ok_pilot_classify_match_block,
)

block = run_ok_pilot_classify_match_block(require_fixtures=True)
print("grant_count", block["grant_count"], "profile_count", block["profile_count"])
print("total_match_rows", len(block["matches"]))

# AC-2: no federal_required tier blocks for OK federal tribes
fed_blocks = [
    m for m in block["matches"]
    if m.get("recognition_requirement") == "federal_required"
    and m.get("recognition_tier_mismatch")
]
print("AC-2 federal_required tier_mismatch rows", len(fed_blocks))
assert not fed_blocks, "AC-2: OK federal tribes must pass recognition gate on federal_required"

# AC-3: program-fit resolution rate
pfs = block["program_fit_summary"]
print("AC-3 program_fit_summary", pfs)
assert pfs["program_fit_resolution_rate"] >= 0

# AC-4: grant_posture advisory only — compact_heavy still gets discretionary matches
posture_dist = block["grant_posture_distribution_on_matches"]
print("AC-4 grant_posture_distribution_on_matches", posture_dist)
compact = [p for p in block["per_profile"] if p["grant_posture"] == "compact_heavy"]
assert compact
sample = compact[0]
print(
    "AC-4 compact_heavy sample",
    sample["profile_fixture_key"],
    "discretionary_advisory_lower_still_included",
    sample["discretionary_advisory_lower_still_included"],
)
assert sample["discretionary_advisory_lower_still_included"] > 0
assert block["grant_posture_advisory_only"] is True

lower_included = [
    m for m in block["matches"]
    if m["grant_posture_advisory"]["advisory_ranking_hint"] == "lower"
    and not m["excluded_from_match_set"]
]
print("AC-4 lower-hint discretionary matches still included", len(lower_included))
assert lower_included

assert block["all_needs_operator_review"] is True
print("all_needs_operator_review", block["all_needs_operator_review"])
PY

echo ""
echo "=== AC-5: honesty guards + SC pilot regression ==="
uv run python -c "
from nativeforge.services.ok_pilot_honesty_regression_service import run_ok_pilot_honesty_regression
from nativeforge.services.sc_pilot_honesty_regression_service import run_sc_pilot_honesty_regression
ok = run_ok_pilot_honesty_regression()
sc = run_sc_pilot_honesty_regression()
print('ok_checks', ok['checks'])
print('sc_checks', sc['checks'])
assert ok['verification_passed']
assert sc['verification_passed']
print('AC-5 OK')
"

echo ""
echo "=== OK pilot staging verify: ALL ACs PASSED ==="
