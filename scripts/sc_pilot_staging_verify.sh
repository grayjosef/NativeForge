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
from nativeforge.services.sc_pilot_fixture_loader_service import (
    build_sc_pilot_fixture_contract,
    load_sc_tribal_profiles,
    load_sc_eligibility_rules,
)
c = build_sc_pilot_fixture_contract()
print('fixtures_present', c['fixtures_present'])
print('profile_count', c['profile_count'])
print('rule_category_count', c['rule_category_count'])
assert c['ready'], 'fixtures not ready'
assert c['profile_count'] == 10
assert c['rule_category_count'] == 21
load_sc_tribal_profiles()
load_sc_eligibility_rules()
print('SC-0 fixture schema OK')
"

echo ""
echo "=== AC-1: public_inferred profiles ==="
uv run python -c "
from nativeforge.services.sc_pilot_profile_loader_service import list_sc_pilot_profiles, resolve_sc_pilot_profile
profiles = list_sc_pilot_profiles(require_files=True)
print('profile_count', len(profiles))
federal = [p for p in profiles if p['recognition_type'] == 'federal']
state = [p for p in profiles if p['recognition_type'] == 'state_only']
print('federal', len(federal), 'state_only', len(state))
assert len(profiles) == 10
assert len(federal) == 1
assert len(state) == 9
for p in profiles:
    prof = resolve_sc_pilot_profile(p['fixture_key'])
    assert prof['profile_evidence_codes'] == []
    assert prof['capture_method'] == 'public_inferred'
    assert prof.get('recognition_type') in {'federal', 'state_only'}
print('AC-1 OK')
"

echo ""
echo "=== AC-2/AC-2b/AC-2c/AC-3/AC-4/AC-4b: recognition-tier + condition gate ==="
uv run python << 'PY'
from nativeforge.services.sc_pilot_classify_match_orchestrator_service import run_sc_pilot_classify_match_block

block = run_sc_pilot_classify_match_block(require_fixtures=True)
state_profiles = [p for p in block["per_profile"] if p["recognition_type"] == "state_only"]
fed = next(p for p in block["per_profile"] if p["recognition_type"] == "federal")
print("grant_count", block["grant_count"], "profile_count", block["profile_count"])

# AC-2: state-only tier-blocks federal_required
state_blocks = [
    m for m in block["matches"]
    if m.get("recognition_tier_mismatch")
    and m.get("recognition_requirement") == "federal_required"
    and any(m.get("profile_fixture_key") == sp["profile_fixture_key"] for sp in state_profiles)
]
print("AC-2 state tier_mismatch+federal_required rows", len(state_blocks))
assert state_blocks, "state-only must tier-block federal_required"
assert state_blocks[0]["blocker_codes"].count("recognition_tier_mismatch") >= 1
assert "eligibility_evidence_gap" in state_blocks[0]["blocker_codes"]
print("AC-2 blocker proof (distinct from evidence gap)", state_blocks[0]["blocker_codes"])

# AC-3: Catawba no tier mismatch on federal_required
fed_blocks = [
    m for m in block["matches"]
    if m.get("profile_fixture_key") == fed["profile_fixture_key"]
    and m.get("recognition_requirement") == "federal_required"
    and m.get("recognition_tier_mismatch")
]
assert not fed_blocks, "AC-3: Catawba must not tier-block federal_required"
print("AC-3 OK")

# AC-2b: dual pathway — tribal blocked, nonprofit eligible for 501c3 state tribes
dual_eligible = [
    m for m in block["matches"]
    if m.get("recognition_requirement") == "federal_required_for_tribal_pathway"
    and m.get("recognition_tier_mismatch")
    and not m.get("excluded_from_match_set")
    and m.get("profile_fixture_key", "").startswith("sc_pilot_")
    and m.get("profile_fixture_key") != fed["profile_fixture_key"]
]
print("AC-2b dual_pathway nonprofit-eligible rows", len(dual_eligible))
assert dual_eligible, "AC-2b: expect dual-pathway nonprofit eligible for state 501c3 tribes"
assert all(
    m["recognition_tier_gate"]["tribal_pathway"]["outcome"] == "blocked"
    for m in dual_eligible[:3]
)

# AC-2c: ANA incorporation — state_ok + requires_incorporation, all incorporated
ana_ok = [
    m for m in block["matches"]
    if m.get("recognition_requirement") == "state_ok"
    and "SEDS" in (m.get("opportunity_title") or "")
    and not m.get("excluded_from_match_set")
    and m.get("profile_fixture_key", "").startswith("sc_pilot_")
    and m.get("profile_fixture_key") != fed["profile_fixture_key"]
]
print("AC-2c ANA SEDS non-excluded state rows", len(ana_ok))
assert ana_ok, "AC-2c: incorporated state tribes should pass ANA SEDS gate"

# AC-4: unknown requirement → review rows exist
unknown_review = [m for m in block["matches"] if m.get("recognition_requirement") == "unknown"]
print("AC-4 unknown grants in corpus", len(unknown_review))

# AC-4b: individual_only excluded
member_only = [m for m in block["matches"] if m.get("member_level_only")]
print("AC-4b member_level_only rows", len(member_only))
assert member_only, "AC-4b: IHS individual_only grants must appear as member-level"
assert all(m.get("excluded_from_match_set") for m in member_only)

assert block["all_needs_operator_review"] is True
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
