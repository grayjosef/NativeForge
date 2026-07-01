#!/usr/bin/env bash
# Tier-3 foundation cohort-3 staging verify (AC-1 through AC-4 + activatable exhaust).
set -euo pipefail
cd "$(dirname "$0")/.."

export NF_APP_ENV=staging
export NF_DEV_ORG_HEADERS=true
export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./nativeforge.ta_tier3_c3.db}"
export NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true
export NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED=true

echo "=== AC-4: stash@{0} preserved ==="
git stash list | head -1
test "$(git stash list | head -1 | grep -c 'stash@{0}')" -eq 1

echo ""
echo "=== Ranked tail + activatable exhaust check ==="
uv run python -c "
from nativeforge.services.tier3_cohort_ranking_service import (
    build_tier3_cohort_ranking_report,
    rank_remaining_activatable_tier3_seeds,
)
from nativeforge.services.tier3_org_cluster_config_service import (
    TA3_COHORT1_SEED_IDS,
    TA3_COHORT2_SEED_IDS,
    TA3_COHORT3_SEED_IDS,
    TA3_COHORT_SEED_IDS,
)
r = build_tier3_cohort_ranking_report()
print('cohort1_size', len(TA3_COHORT1_SEED_IDS))
print('cohort2_size', len(TA3_COHORT2_SEED_IDS))
print('cohort3_size', len(TA3_COHORT3_SEED_IDS))
print('active_cohort_total', len(TA3_COHORT_SEED_IDS))
print('remaining_activatable', r['remaining_activatable_count'])
print('activatable_exhausted', r['activatable_exhausted'])
print('cohort3_domain_clusters', r['cohort3_domain_clusters'])
print('cohort3_tail_ranked:')
for row in rank_remaining_activatable_tier3_seeds():
    print(' ', row['total_score'], row['seed_id'], row['source_name'][:55])
assert len(TA3_COHORT3_SEED_IDS) == 9
assert len(TA3_COHORT_SEED_IDS) == 35
"

echo ""
echo "=== AC-3 baseline: grant pool before live cohort-3 fetch ==="
uv run python -c "
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_mixed_tier13_corpus,
    load_tier3_foundation_corpus,
)
t3 = load_tier3_foundation_corpus()
mixed = load_mixed_tier13_corpus()
nofo = sum(1 for g in t3 if g.get('no_live_nofo'))
print('before_tier3_count', len(t3))
print('before_mixed_count', len(mixed))
print('before_no_live_nofo', nofo)
"

echo ""
echo "=== AC-1/2/3: live cohort-1+2+3 fetch + persist ==="
uv run python << 'PY'
from collections import Counter

from nativeforge.services.tier3_foundation_batch_live_fetch_service import (
    run_tier3_foundation_batch_live_fetch,
)
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_mixed_tier13_corpus,
    load_tier3_foundation_corpus,
    persist_tier3_batch_to_corpus,
)
from nativeforge.services.tier3_org_cluster_config_service import (
    TA3_COHORT1_SEED_IDS,
    TA3_COHORT2_SEED_IDS,
    TA3_COHORT3_SEED_IDS,
    TA3_COHORT_SEED_IDS,
)

before_t3 = len(load_tier3_foundation_corpus())
before_mixed = len(load_mixed_tier13_corpus())

batch = run_tier3_foundation_batch_live_fetch(
    list(TA3_COHORT_SEED_IDS), fetch_mode="live"
)
persist = persist_tier3_batch_to_corpus(batch)
after_t3 = persist["tier3_grant_count"]
after_mixed = persist["mixed_grant_count"]

c3 = set(TA3_COHORT3_SEED_IDS)
per_cohort = Counter(
    "cohort3"
    if r["seed_id"] in c3
    else ("cohort2" if r["seed_id"] in set(TA3_COHORT2_SEED_IDS) else "cohort1")
    for r in batch["per_source"]
)

print("cohort3_seeds", len(TA3_COHORT3_SEED_IDS))
print("cohort_fetch_rows", dict(per_cohort))
print("live_listings_extracted", batch["total_opportunity_count"])
print(
    "real_fetch_payloads",
    sum(1 for p in batch["raw_payloads"] if p.get("real_fetch")),
)
print("no_live_nofo_honest_empty", persist["no_live_nofo_count"])
print("per_adapter:")
for k, v in sorted(
    Counter(r["platform_adapter_key"] for r in batch["per_source"]).items()
):
    print(f"  {k}: {v} seeds")
print(
    f"AC-3 before_tier3={before_t3} after_tier3={after_t3} "
    f"delta_tier3={after_t3 - before_t3}"
)
print(
    f"AC-3 before_mixed={before_mixed} after_mixed={after_mixed} "
    f"delta_mixed={after_mixed - before_mixed}"
)
assert batch["source_count"] == len(TA3_COHORT_SEED_IDS)
PY

echo ""
echo "=== AC-1: classify + match (needs_operator_review) ==="
uv run python -c "
from nativeforge.services.tier3_classify_match_orchestrator_service import run_tier3_classify_match_block
block = run_tier3_classify_match_block(nf_live_source_ingestion=True, nf_real_resolver_validation=True)
matches = block['classify_match']['matches']
labels = {m['match_label'] for m in matches}
prov = {
    g.get('provenance', {}).get('platform_adapter_key')
    for g in block.get('tier3_grants', [])
    if g.get('provenance')
}
seed_ids = {g.get('source_seed_id') for g in block.get('tier3_grants', [])}
print('tier3_grant_count', block['tier3_grant_count'])
print('distinct_source_seed_ids', len(seed_ids))
print('match_labels', labels)
print('platform_adapter_keys', sorted(x for x in prov if x))
print('all_needs_operator_review', block['all_needs_operator_review'])
assert block['all_needs_operator_review']
assert labels == {'needs_operator_review'}
print('AC-1 OK')
"

echo ""
echo "=== AC-4: seed_id keying (nativephilanthropy multi-program) ==="
uv run python -c "
from nativeforge.services.tier3_foundation_corpus_persist_service import load_tier3_foundation_corpus
grants = load_tier3_foundation_corpus()
nap_ids = {'nf-seed-2026-t3-005', 'nf-seed-2026-t3-065'}
rows = [g for g in grants if g.get('source_seed_id') in nap_ids]
seed_ids = {g['source_seed_id'] for g in rows}
print('nativephilanthropy_rows', len(rows), 'distinct_seed_ids', len(seed_ids))
assert len(seed_ids) >= 1
print('AC-4 OK')
"

echo ""
echo "=== AC-2/AC-4: honesty + SC/OK/Tier-2/Tier-3 regression ==="
uv run python -c "
from nativeforge.services.ta_tier3_honesty_regression_service import run_ta_tier3_honesty_regression
from nativeforge.services.sc_pilot_honesty_regression_service import run_sc_pilot_honesty_regression
from nativeforge.services.ok_pilot_honesty_regression_service import run_ok_pilot_honesty_regression
from nativeforge.services.tier2_state_honesty_regression_service import run_tier2_state_honesty_regression
from nativeforge.services.tier3_cohort_ranking_service import rank_remaining_activatable_tier3_seeds
ta = run_ta_tier3_honesty_regression()
sc = run_sc_pilot_honesty_regression()
ok = run_ok_pilot_honesty_regression()
t2 = run_tier2_state_honesty_regression()
remaining = len(rank_remaining_activatable_tier3_seeds())
print('ta_checks', ta['checks'])
print('remaining_activatable_tier3', remaining)
assert ta['verification_passed']
assert sc['verification_passed']
assert ok['verification_passed']
assert t2['verification_passed']
assert remaining == 0
print('AC-2/AC-4 OK — activatable Tier-3 exhausted')
"

echo ""
echo "=== Tier-3 cohort-3 staging verify: ALL ACs PASSED ==="
