#!/usr/bin/env bash
# Tier-2 state portal pilot staging verify (AC-1 through AC-5 + MT accuracy).
set -euo pipefail
cd "$(dirname "$0")/.."

export NF_APP_ENV=staging
export NF_DEV_ORG_HEADERS=true
export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./nativeforge.tier2_state.db}"
export NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true
export NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED=true

echo "=== AC-5: stash@{0} preserved ==="
git stash list | head -1
test "$(git stash list | head -1 | grep -c 'stash@{0}')" -eq 1

echo ""
echo "=== AC-3 baseline: grant pool before Tier-2 fetch ==="
uv run python -c "
from nativeforge.services.tier3_foundation_corpus_persist_service import load_mixed_tier13_corpus
from nativeforge.services.tier2_state_corpus_persist_service import load_tier2_state_corpus
mixed = load_mixed_tier13_corpus()
t2 = load_tier2_state_corpus()
nofo = sum(1 for g in t2 if g.get('no_live_nofo'))
print('before_mixed_count', len(mixed))
print('before_tier2_count', len(t2))
print('before_tier2_no_live_nofo', nofo)
"

echo ""
echo "=== AC-1/2/3/MT: live Tier-2 batch fetch + persist ==="
uv run python << 'PY'
from nativeforge.services.tier2_state_batch_live_fetch_service import run_tier2_state_batch_live_fetch
from nativeforge.services.tier2_state_corpus_persist_service import (
    persist_tier2_batch_to_corpus,
)
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_mixed_tier13_corpus,
)
from nativeforge.services.tier2_state_portal_config_service import T2_PILOT_SEED_IDS

before = len(load_mixed_tier13_corpus())
batch = run_tier2_state_batch_live_fetch(list(T2_PILOT_SEED_IDS), fetch_mode="live")
persist = persist_tier2_batch_to_corpus(batch)
after = persist["after_mixed_count"]

print("pilot_seeds", len(T2_PILOT_SEED_IDS))
print("live_listings", batch["total_opportunity_count"])
print("real_fetch_payloads", batch["real_grant_count"])
print("no_live_nofo_honest", persist["no_live_nofo_count"])
print("tier2_corpus_count", persist["tier2_grant_count"])
print(f"AC-3 before_mixed={before} after_mixed={after} delta={after - before}")

mt = batch.get("mt_filter_audit") or {}
print("AC-MT mt_filter_audit", mt)
assert mt.get("accuracy_ok"), "MT filter must exclude commerce noise and keep tribal listings"
assert mt.get("generic_noise_leaked_to_included", 1) == 0
print("AC-MT sample_included", mt.get("sample_included_titles"))
print("AC-MT sample_excluded_commerce", mt.get("sample_excluded_commerce"))

for row in batch["per_source"]:
    print(
        " per_source",
        row["seed_id"],
        "listings=",
        row["opportunity_count"],
        "empty=",
        row["empty_honestly"],
    )
liaison = [r for r in batch["per_source"] if r["seed_id"].endswith(("048", "037"))]
assert all(r["empty_honestly"] for r in liaison), "AC-2: liaison seeds must be honestly empty"
PY

echo ""
echo "=== AC-1: classify + match (needs_operator_review) ==="
uv run python -c "
from nativeforge.services.tier2_classify_match_orchestrator_service import run_tier2_classify_match_block
block = run_tier2_classify_match_block(nf_live_source_ingestion=True, nf_real_resolver_validation=True)
labels = {m['match_label'] for m in block['classify_match']['matches']}
prov = {
    g.get('provenance', {}).get('platform_adapter_key')
    for g in block.get('tier2_grants', [])
}
print('tier2_grant_count', block['tier2_grant_count'])
print('match_labels', labels)
print('platform_adapter_keys', sorted(x for x in prov if x))
print('all_needs_operator_review', block['all_needs_operator_review'])
assert block['all_needs_operator_review']
assert labels == {'needs_operator_review'}
print('AC-1 OK')
"

echo ""
echo "=== AC-4: seed_id keying ==="
uv run python -c "
from nativeforge.services.tier2_state_corpus_persist_service import load_tier2_state_corpus
grants = load_tier2_state_corpus()
seed_ids = {g['source_seed_id'] for g in grants}
print('tier2_rows', len(grants), 'distinct_seed_ids', len(seed_ids))
assert len(seed_ids) == len({g['source_seed_id'] for g in grants})
print('AC-4 OK')
"

echo ""
echo "=== AC-2/AC-5: honesty + SC/OK/Tier-3 regression ==="
uv run python -c "
from nativeforge.services.tier2_state_honesty_regression_service import run_tier2_state_honesty_regression
from nativeforge.services.sc_pilot_honesty_regression_service import run_sc_pilot_honesty_regression
from nativeforge.services.ok_pilot_honesty_regression_service import run_ok_pilot_honesty_regression
from nativeforge.services.ta_tier3_honesty_regression_service import run_ta_tier3_honesty_regression
t2 = run_tier2_state_honesty_regression()
sc = run_sc_pilot_honesty_regression()
ok = run_ok_pilot_honesty_regression()
ta = run_ta_tier3_honesty_regression()
print('tier2_checks', t2['checks'])
print('mt_labels', t2.get('mt_classification_labels'))
assert t2['verification_passed']
assert sc['verification_passed']
assert ok['verification_passed']
assert ta['verification_passed']
print('AC-2/AC-5 OK')
"

echo ""
echo "=== Tier-2 state pilot staging verify: ALL ACs PASSED ==="
