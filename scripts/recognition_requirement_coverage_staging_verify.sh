#!/usr/bin/env bash
# Recognition-requirement coverage expansion staging verify (AC-1 through AC-5).
set -euo pipefail
cd "$(dirname "$0")/.."

export NF_APP_ENV=staging
export NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true
export NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED=true

echo "=== AC-5: stash@{0} preserved ==="
git stash list | head -1
test "$(git stash list | head -1 | grep -c 'stash@{0}')" -eq 1

echo ""
echo "=== AC-1: UNKNOWN before/after + honest residual breakdown ==="
uv run python << 'PY'
from collections import Counter

from nativeforge.services.grant_eligibility_conditions_service import enrich_grant_with_eligibility_metadata
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_eligibility_rules
from nativeforge.services.tier3_foundation_corpus_persist_service import load_mixed_tier13_corpus

BEFORE_UNKNOWN = 57
rules = load_sc_eligibility_rules(require_files=False)
corpus = load_mixed_tier13_corpus()
enriched = [enrich_grant_with_eligibility_metadata(g, rules=rules) for g in corpus]
unknowns = [g for g in enriched if g["recognition_requirement"] == "unknown"]
after = len(unknowns)
print("before_unknown_grants", BEFORE_UNKNOWN)
print("after_unknown_grants", after)
print("reduction", BEFORE_UNKNOWN - after)
print("before_unknown_match_rows_x10", BEFORE_UNKNOWN * 10)
print("after_unknown_match_rows_x10", after * 10)
print("recognition_requirement_sources", dict(Counter(g.get("recognition_requirement_source") for g in enriched)))

no_text = sum(1 for g in unknowns if len(str(g.get("eligibility_text") or "").strip()) < 5)
tier3 = sum(1 for g in unknowns if g.get("tier") == 3)
conflict = sum(1 for g in unknowns if g.get("recognition_requirement_source") == "conflict")
others_only = sum(
    1
    for g in unknowns
    if "Others (see text field" in str(g.get("eligibility_text") or "")
    and not str(g.get("eligibility_text") or "").startswith("Applicant types: Native American")
)
print("residual_no_eligibility_text", no_text)
print("residual_tier3", tier3)
print("residual_gg_rules_conflict", conflict)
print("residual_others_unparsed", others_only)
assert after < BEFORE_UNKNOWN
assert after <= 45
print("AC-1 OK")
PY

echo ""
echo "=== AC-2: spot-check newly derived applicant_types sample ==="
uv run python << 'PY'
from nativeforge.services.grant_eligibility_conditions_service import enrich_grant_with_eligibility_metadata
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_eligibility_rules
from nativeforge.services.tier3_foundation_corpus_persist_service import load_mixed_tier13_corpus

rules = load_sc_eligibility_rules(require_files=False)
samples = []
for g in load_mixed_tier13_corpus():
    e = enrich_grant_with_eligibility_metadata(g, rules=rules)
    if e.get("recognition_requirement_source") == "applicant_types" and e["recognition_requirement"] != "unknown":
        et = str(g.get("eligibility_text") or "")[:120]
        samples.append((g["grant_id"], e["recognition_requirement"], e.get("applicant_type_ids"), et))
for row in samples[:5]:
    print("spot_check", row)
assert len(samples) >= 10
print("AC-2 spot-check OK (applicant_types-derived grants:", len(samples), ")")
PY

echo ""
echo "=== AC-2d: 07+11 → state_ok; state-only tribe eligible ==="
uv run python << 'PY'
from nativeforge.services.grant_eligibility_conditions_service import enrich_grant_with_eligibility_metadata
from nativeforge.services.recognition_tier_eligibility_gate_service import apply_recognition_tier_eligibility_gate
from nativeforge.services.sc_pilot_profile_loader_service import resolve_sc_pilot_profile
from nativeforge.services.sc_pilot_fixture_loader_service import require_sc_pilot_fixtures

require_sc_pilot_fixtures()
grant = {
    "grant_id": "staging-ac2d",
    "eligibility_text": (
        "Applicant types: Native American tribal governments (Federally recognized); "
        "Native American tribal organizations (other than Federally recognized tribal governments)"
    ),
    "tribal_eligible": True,
}
enriched = enrich_grant_with_eligibility_metadata(grant)
assert enriched["recognition_requirement"] == "state_ok"
assert enriched["recognition_requirement_source"] == "applicant_types"
profile = resolve_sc_pilot_profile("sc_pilot_waccamaw_indian_people")
gate = apply_recognition_tier_eligibility_gate(opportunity=enriched, profile=profile)
assert gate["recognition_tier_mismatch"] is False
assert gate["excluded_from_match_set"] is False
print("AC-2d OK", enriched["recognition_requirement"], gate["outcome"])
PY

echo ""
echo "=== AC-2e: 07+12 (no 11) → dual pathway; nonprofit route for 501c3 state tribe ==="
uv run python << 'PY'
from nativeforge.services.grant_eligibility_conditions_service import enrich_grant_with_eligibility_metadata
from nativeforge.services.recognition_tier_eligibility_gate_service import apply_recognition_tier_eligibility_gate
from nativeforge.services.sc_pilot_profile_loader_service import resolve_sc_pilot_profile
from nativeforge.services.sc_pilot_fixture_loader_service import require_sc_pilot_fixtures

require_sc_pilot_fixtures()
grant = {
    "grant_id": "staging-ac2e",
    "eligibility_text": (
        "Applicant types: Native American tribal governments (Federally recognized); "
        "Nonprofits having a 501(c)(3) status with the IRS, other than institutions of higher education"
    ),
    "tribal_eligible": True,
}
enriched = enrich_grant_with_eligibility_metadata(grant)
assert enriched["recognition_requirement"] == "federal_required_for_tribal_pathway"
assert enriched["dual_pathway"]["nonprofit_alternative"] is True
profile = resolve_sc_pilot_profile("sc_pilot_catawba_indian_nation")
profile["recognition_type"] = "state_only"
profile["has_501c3"] = True
gate = apply_recognition_tier_eligibility_gate(opportunity=enriched, profile=profile)
assert gate["recognition_tier_mismatch"] is True
assert gate["tribal_pathway"]["outcome"] == "blocked"
assert gate["nonprofit_pathway"]["outcome"] == "eligible"
print("AC-2e OK", gate["outcome"])
PY

echo ""
echo "=== AC-3: tier-3 title-only stays UNKNOWN ==="
uv run python << 'PY'
from nativeforge.services.recognition_requirement_derivation_service import derive_recognition_requirement_bundle

grant = {"tier": 3, "opportunity_title": "Project Grants", "eligibility_text": "", "synopsis": "Overview only."}
bundle = derive_recognition_requirement_bundle(grant)
assert bundle["recognition_requirement"] == "unknown"
assert bundle["recognition_requirement_source"] == "unknown"
print("AC-3 OK")
PY

echo ""
echo "=== AC-4: SC pilot gate regression ==="
./scripts/sc_pilot_staging_verify.sh 2>&1 | tail -5

echo ""
echo "=== Recognition-requirement coverage staging verify: ALL ACs PASSED ==="
