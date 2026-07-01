#!/usr/bin/env bash
# Static extraction-gap fix staging verify (AC-1 through AC-5).
set -euo pipefail
cd "$(dirname "$0")/.."

export NF_APP_ENV=staging
export NF_DEV_ORG_HEADERS=true
export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./nativeforge.extraction_gap.db}"
export NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true
export NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED=true

echo "=== AC-5: stash@{0} preserved ==="
git stash list | head -1
test "$(git stash list | head -1 | grep -c 'stash@{0}')" -eq 1

echo ""
echo "=== AC-3 baseline: pool before re-ingest ==="
uv run python -c "
from nativeforge.services.tier2_state_corpus_persist_service import load_tier2_state_corpus
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_mixed_tier13_corpus,
    load_tier3_foundation_corpus,
)
t2 = load_tier2_state_corpus()
t3 = load_tier3_foundation_corpus()
mixed = load_mixed_tier13_corpus()
nofo_t2 = sum(1 for g in t2 if g.get('no_live_nofo'))
nofo_t3 = sum(1 for g in t3 if g.get('no_live_nofo'))
print('before_tier2', len(t2), 'nofo_t2', nofo_t2)
print('before_tier3', len(t3), 'nofo_t3', nofo_t3)
print('before_mixed', len(mixed))
"

echo ""
echo "=== AC-1/2/3: extraction-gap re-ingest ==="
uv run python << 'PY'
from nativeforge.services.static_extraction_gap_service import (
    EXTRACTION_GAP_SEED_IDS,
    GENUINELY_EMPTY_DEFERRED_SEED_IDS,
    run_extraction_gap_reingest_block,
)
from nativeforge.services.tier3_classify_match_orchestrator_service import (
    run_tier3_classify_match_block,
)

block = run_extraction_gap_reingest_block(fetch_mode="live")
print("target_seeds", len(EXTRACTION_GAP_SEED_IDS))
print("tier2_recovered", block["tier2_recovered"])
print("tier3_recovered", block["tier3_recovered"])
print("tier2_delta", block["tier2_persist"].get("inserted_count"))
print("tier3_delta", block["tier3_persist"].get("inserted_count"))
print("AC-2 per_page_audit:")
for row in block["per_page_audit"]:
    print(
        " ",
        row["seed_id"],
        "included=",
        row["included_count"],
        "excluded=",
        row["excluded_count"],
        "nav_leaked=",
        row["generic_nav_leaked"],
        "accuracy_ok=",
        row["accuracy_ok"],
    )
    if row["sample_included"]:
        print("   sample:", row["sample_included"][:2])
assert all(r["accuracy_ok"] for r in block["per_page_audit"])
assert block["tier2_recovered"] >= 1
assert block["tier3_recovered"] >= 1
total_included = sum(r["included_count"] for r in block["per_page_audit"])
assert total_included >= 4
from nativeforge.services.tier2_classify_match_orchestrator_service import (
    run_tier2_classify_match_block,
)
t2_classify = run_tier2_classify_match_block(
    nf_live_source_ingestion=True, nf_real_resolver_validation=True
)
print("tier2_classify_labels", {m["match_label"] for m in t2_classify["classify_match"]["matches"]})
classify = run_tier3_classify_match_block(
    nf_live_source_ingestion=True, nf_real_resolver_validation=True
)
labels = {m["match_label"] for m in classify["classify_match"]["matches"]}
print("classify_labels", labels, "all_review", classify["all_needs_operator_review"])
assert classify["all_needs_operator_review"]
print("deferred_empty_count", len(GENUINELY_EMPTY_DEFERRED_SEED_IDS))
from nativeforge.services.tier2_state_corpus_persist_service import load_tier2_state_corpus
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_mixed_tier13_corpus,
    load_tier3_foundation_corpus,
)
print("after_tier2", len(load_tier2_state_corpus()))
print("after_tier3", len(load_tier3_foundation_corpus()))
print("after_mixed", len(load_mixed_tier13_corpus()))
PY

echo ""
echo "=== AC-4: cohort-1 fixture regression (unchanged extract discipline) ==="
uv run python -c "
from nativeforge.services.tier3_foundation_batch_live_fetch_service import run_tier3_foundation_batch_live_fetch
from nativeforge.services.source_fetch_adapter_contract_service import FETCH_MODE_FIXTURE
from pathlib import Path
fx = Path('fixtures/source_ingestion')
fixtures = {
    'firstpeoplesfund.org': (fx / 'tier3_fpf_grants_page.html').read_text(),
    'firstnations.org': (fx / 'tier3_firstnations_grants_page.html').read_text(),
}
batch = run_tier3_foundation_batch_live_fetch(
    ['nf-seed-2026-t3-006','nf-seed-2026-t3-012'],
    fetch_mode=FETCH_MODE_FIXTURE,
    fixture_by_domain=fixtures,
)
by = {r['seed_id']: r['opportunity_count'] for r in batch['per_source']}
print('fpf_fixture_count', by.get('nf-seed-2026-t3-006'))
print('fn_fixture_count', by.get('nf-seed-2026-t3-012'))
assert by.get('nf-seed-2026-t3-006', 0) >= 1
print('AC-4 fixture regression OK')
"

echo ""
echo "=== AC-3/5: honesty regressions ==="
uv run python -c "
from nativeforge.services.sc_pilot_honesty_regression_service import run_sc_pilot_honesty_regression
from nativeforge.services.ok_pilot_honesty_regression_service import run_ok_pilot_honesty_regression
from nativeforge.services.tier2_state_honesty_regression_service import run_tier2_state_honesty_regression
from nativeforge.services.ta_tier3_honesty_regression_service import run_ta_tier3_honesty_regression
assert run_sc_pilot_honesty_regression()['verification_passed']
assert run_ok_pilot_honesty_regression()['verification_passed']
assert run_tier2_state_honesty_regression()['verification_passed']
assert run_ta_tier3_honesty_regression()['verification_passed']
print('AC-5 regressions OK')
"

echo ""
echo "=== Static extraction-gap staging verify: ALL ACs PASSED ==="
