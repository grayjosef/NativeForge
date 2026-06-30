#!/usr/bin/env bash
# Grants.gov eligibility completeness staging verify (Path A AC-1 through AC-6).
set -euo pipefail
cd "$(dirname "$0")/.."

export NF_APP_ENV=staging
export NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true
export NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED=true

echo "=== AC-6: stash@{0} preserved ==="
git stash list | head -1
test "$(git stash list | head -1 | grep -c 'stash@{0}')" -eq 1

echo ""
echo "=== AC-1: TMG forecast → state_ok, source=forecast ==="
uv run python << 'PY'
from nativeforge.services.grant_eligibility_conditions_service import enrich_grant_with_eligibility_metadata
from nativeforge.services.tier3_foundation_corpus_persist_service import load_mixed_tier13_corpus

grant = next(g for g in load_mixed_tier13_corpus() if g["grant_id"] == "la-real-009")
enriched = enrich_grant_with_eligibility_metadata(
    grant, allow_live_completeness_fetch=True
)
print("grant_id", enriched["grant_id"])
print("eligibility_text_len", len(str(enriched.get("eligibility_text") or "")))
print("eligibility_text_source", enriched.get("eligibility_text_source"))
print("eligibility_provenance", enriched.get("eligibility_provenance"))
print("recognition_requirement", enriched["recognition_requirement"])
print("recognition_requirement_source", enriched.get("recognition_requirement_source"))
assert enriched["eligibility_text_source"] == "forecast"
assert enriched["recognition_requirement"] == "state_ok"
assert enriched["recognition_requirement_source"] == "forecast"
assert enriched.get("eligibility_provenance")
print("AC-1 OK")
PY

echo ""
echo "=== AC-2: empty-on-success bug fixed (la-real-035) ==="
uv run python << 'PY'
from nativeforge.services.grant_eligibility_conditions_service import enrich_grant_with_eligibility_metadata
from nativeforge.services.tier3_foundation_corpus_persist_service import load_mixed_tier13_corpus

grant = next(g for g in load_mixed_tier13_corpus() if g["grant_id"] == "la-real-035")
assert not str(grant.get("eligibility_text") or "").strip(), "baseline corpus row must be empty"
enriched = enrich_grant_with_eligibility_metadata(
    grant, allow_live_completeness_fetch=True
)
print("eligibility_text_len", len(str(enriched.get("eligibility_text") or "")))
print("eligibility_text_source", enriched.get("eligibility_text_source"))
assert len(str(enriched.get("eligibility_text") or "")) > 50
print("AC-2 OK")
PY

echo ""
echo "=== AC-3: forecast-derived accuracy spot-check ==="
uv run python << 'PY'
from nativeforge.services.grant_eligibility_conditions_service import enrich_grant_with_eligibility_metadata
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_eligibility_rules
from nativeforge.services.tier3_foundation_corpus_persist_service import load_mixed_tier13_corpus

rules = load_sc_eligibility_rules(require_files=False)
checks = []
for gid in ("la-real-009", "la-real-011", "la-real-017"):
    grant = next(g for g in load_mixed_tier13_corpus() if g["grant_id"] == gid)
    e = enrich_grant_with_eligibility_metadata(
        grant, rules=rules, allow_live_completeness_fetch=True
    )
    if e.get("recognition_requirement_source") == "forecast":
        checks.append((gid, e["recognition_requirement"], e.get("eligibility_text_source")))
        assert e["recognition_requirement"] in {"state_ok", "unknown", "open_nonprofit"}
        if "Urban Indian" in str(e.get("eligibility_text") or ""):
            assert e["recognition_requirement"] == "state_ok"
for row in checks:
    print("spot_check", row)
assert checks, "expected forecast-derived grants"
print("AC-3 OK")
PY

echo ""
echo "=== AC-4: UNKNOWN before/after + attachment inventory ==="
uv run python << 'PY'
from collections import Counter

from nativeforge.services.grant_eligibility_conditions_service import enrich_grant_with_eligibility_metadata
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_eligibility_rules
from nativeforge.services.tier3_foundation_corpus_persist_service import load_mixed_tier13_corpus

BEFORE_UNKNOWN = 43
rules = load_sc_eligibility_rules(require_files=False)
corpus = load_mixed_tier13_corpus()
enriched = [
    enrich_grant_with_eligibility_metadata(g, rules=rules, allow_live_completeness_fetch=True)
    for g in corpus
]
unknowns = [g for g in enriched if g["recognition_requirement"] == "unknown"]
after = len(unknowns)
inv_total = sum(
    (g.get("grants_gov_attachment_inventory") or {}).get("attachment_count", 0)
    for g in enriched
    if g.get("grants_gov_attachment_inventory")
)
inv_grants = sum(1 for g in enriched if (g.get("grants_gov_attachment_inventory") or {}).get("attachment_count"))
print("before_unknown", BEFORE_UNKNOWN)
print("after_unknown", after)
print("reduction", BEFORE_UNKNOWN - after)
print("forecast_sourced", sum(1 for g in enriched if g.get("eligibility_text_source") == "forecast"))
print("attachment_inventory_grants", inv_grants)
print("attachment_inventory_total_files", inv_total)
no_text = sum(1 for g in unknowns if len(str(g.get("eligibility_text") or "")) < 5)
tier3 = sum(1 for g in unknowns if g.get("tier") == 3)
print("residual_no_text", no_text)
print("residual_tier3", tier3)
assert after < BEFORE_UNKNOWN
assert after <= 40
print("AC-4 OK")
PY

echo ""
echo "=== AC-5: regression snapshot + SC pilot ==="
uv run pytest tests/test_recognition_requirement_coverage_expansion.py::test_corpus_derived_regression_snapshot tests/test_recognition_requirement_coverage_expansion.py::test_no_applicant_types_prefix_regression_snapshot -q
./scripts/sc_pilot_staging_verify.sh 2>&1 | tail -3

echo ""
echo "=== Attachment recoverable re-audit (Path B gate) ==="
./scripts/grants_gov_attachment_recoverable_reaudit.sh

echo ""
echo "=== Grants.gov eligibility completeness: ALL ACs PASSED ==="
