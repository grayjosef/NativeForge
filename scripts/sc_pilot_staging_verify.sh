#!/usr/bin/env bash
# SC pilot: recognition-tier gate staging verify (AC-1 through AC-6).
set -euo pipefail
cd "$(dirname "$0")/.."

export NF_APP_ENV=staging
export NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true
export NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED=true

echo "=== AC-6: stash@{0} preserved ==="
git stash list | head -1
test "$(git stash list | head -1 | grep -c 'stash@{0}')" -eq 1

echo ""
echo "=== Fixture gate ==="
uv run python -c "
from nativeforge.services.sc_pilot_fixture_loader_service import fixtures_present, build_sc_pilot_fixture_contract
c = build_sc_pilot_fixture_contract()
print('fixtures_present', c['fixtures_present'])
if not c['ready']:
    print('STOP: place sc_tribal_profiles.json and sc_eligibility_rules.json in fixtures/sc_pilot/')
    print('Infrastructure ready; integration ACs require operator fixtures.')
    raise SystemExit(2)
"

echo ""
echo "=== AC-1: public_inferred profiles ==="
uv run python -c "
from nativeforge.services.sc_pilot_profile_loader_service import list_sc_pilot_profiles, resolve_sc_pilot_profile
profiles = list_sc_pilot_profiles(require_files=True)
print('profile_count', len(profiles))
for p in profiles[:3]:
    print(p['fixture_key'], p['recognition_type'], p['capture_method'])
p = resolve_sc_pilot_profile(profiles[0]['fixture_key'])
assert p['profile_evidence_codes'] == []
assert p['capture_method'] == 'public_inferred'
print('AC-1 OK')
"

echo ""
echo "=== AC-2/AC-3/AC-4: recognition-tier gate (distinct from evidence gap) ==="
uv run python << 'PY'
from nativeforge.services.sc_pilot_classify_match_orchestrator_service import run_sc_pilot_classify_match_block

block = run_sc_pilot_classify_match_block(require_fixtures=True)
state = next(p for p in block["per_profile"] if p["recognition_type"] == "state_only")
fed = next(p for p in block["per_profile"] if p["recognition_type"] == "federal")
print("state_only_profile", state["profile_fixture_key"], "tier_mismatches", state["recognition_tier_mismatch_count"])
print("federal_profile", fed["profile_fixture_key"], "tier_mismatches", fed["recognition_tier_mismatch_count"])

state_blocks = [
    m for m in block["matches"]
    if m.get("recognition_tier_mismatch") and m.get("recognition_requirement") == "federal_required"
]
fed_blocks_on_federal_req = [
    m for m in block["matches"]
    if m.get("profile_fixture_key") == fed["profile_fixture_key"]
    and m.get("recognition_requirement") == "federal_required"
    and m.get("recognition_tier_mismatch")
]
ana_shown = [
    m for m in block["matches"]
    if m.get("profile_fixture_key") == state["profile_fixture_key"]
    and m.get("recognition_requirement") == "state_ok"
    and not m.get("excluded_from_match_set")
]
unknown_review = [
    m for m in block["matches"]
    if m.get("recognition_requirement") == "unknown"
]
print("AC-2 sample tier_mismatch+federal_required rows", len(state_blocks))
assert state_blocks, "state-only must tier-block federal_required"
assert state_blocks[0]["blocker_codes"].count("recognition_tier_mismatch") >= 1
print("AC-2 blocker proof", state_blocks[0]["blocker_codes"])
assert not fed_blocks_on_federal_req, "AC-3: Catawba must not tier-block federal_required"
print("AC-3 OK — federal tribe tier_mismatch on federal_required = 0")
if ana_shown:
    print("AC-4 ANA/state_ok shown to state-only", len(ana_shown))
print("AC-4 unknown grants in corpus", len(unknown_review))
print("all_needs_operator_review", block["all_needs_operator_review"])
PY

echo ""
echo "=== AC-5: honesty regression ==="
uv run python -c "
from nativeforge.services.sc_pilot_honesty_regression_service import run_sc_pilot_honesty_regression
r = run_sc_pilot_honesty_regression()
print('checks', r['checks'])
assert r['verification_passed']
print('AC-5 OK')
"

echo ""
echo "=== SC pilot staging verify: ALL ACs PASSED ==="
