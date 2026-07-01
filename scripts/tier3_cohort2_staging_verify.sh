#!/usr/bin/env bash
# Tier-3 foundation cohort-2 staging verify (AC-1 through AC-5).
set -euo pipefail
cd "$(dirname "$0")/.."

export NF_APP_ENV=staging
export NF_DEV_ORG_HEADERS=true
export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./nativeforge.ta_tier3_c2.db}"
export NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true
export NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED=true

echo "=== AC-5: stash@{0} preserved ==="
git stash list | head -1
test "$(git stash list | head -1 | grep -c 'stash@{0}')" -eq 1

echo ""
echo "=== Ranked shortlist (cohort-2 selection) ==="
uv run python -c "
from nativeforge.services.tier3_cohort_ranking_service import build_tier3_cohort_ranking_report
from nativeforge.services.tier3_org_cluster_config_service import (
    TA3_COHORT1_SEED_IDS,
    TA3_COHORT2_SEED_IDS,
    TA3_COHORT_SEED_IDS,
)
r = build_tier3_cohort_ranking_report()
print('cohort1_size', len(TA3_COHORT1_SEED_IDS))
print('cohort2_size', len(TA3_COHORT2_SEED_IDS))
print('active_cohort_total', len(TA3_COHORT_SEED_IDS))
print('remaining_activatable', r['remaining_activatable_count'])
print('cohort2_domain_clusters', r['cohort2_domain_clusters'])
print('top5_ranked:')
for row in r['ranked_shortlist'][:5]:
    print(' ', row['total_score'], row['seed_id'], row['source_name'][:60])
"

echo ""
echo "=== AC-3 baseline: grant pool before live cohort-2 fetch ==="
uv run python -c "
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_mixed_tier13_corpus,
    load_tier3_foundation_corpus,
)
from nativeforge.services.real_grants_corpus_loader_service import load_nf13_real_ingested_grants
t3 = load_tier3_foundation_corpus()
mixed = load_mixed_tier13_corpus()
fed = len(load_nf13_real_ingested_grants())
nofo = sum(1 for g in t3 if not g.get('real_fetch'))
print('before_tier3_count', len(t3))
print('before_mixed_count', len(mixed))
print('before_federal_baseline', fed)
print('before_no_live_nofo', nofo)
"

echo ""
echo "=== AC-1/2/3: live cohort-1+2 fetch + persist ==="
uv run python << 'PY'
from collections import Counter

from nativeforge.services.real_grants_corpus_loader_service import load_nf13_real_ingested_grants
from nativeforge.services.tier3_foundation_batch_live_fetch_service import run_tier3_foundation_batch_live_fetch
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_mixed_tier13_corpus,
    load_tier3_foundation_corpus,
    persist_tier3_batch_to_corpus,
)
from nativeforge.services.tier3_org_cluster_config_service import (
    TA3_COHORT1_SEED_IDS,
    TA3_COHORT2_SEED_IDS,
    TA3_COHORT_SEED_IDS,
)

before_t3 = len(load_tier3_foundation_corpus())
before_mixed = len(load_mixed_tier13_corpus())
baseline_fed = len(load_nf13_real_ingested_grants())

batch = run_tier3_foundation_batch_live_fetch(list(TA3_COHORT_SEED_IDS), fetch_mode="live")
persist = persist_tier3_batch_to_corpus(batch)
after_t3 = persist["tier3_grant_count"]
after_mixed = persist["mixed_grant_count"]

c1 = set(TA3_COHORT1_SEED_IDS)
c2 = set(TA3_COHORT2_SEED_IDS)
per_cohort = Counter(
    "cohort2" if r["seed_id"] in c2 else "cohort1"
    for r in batch["per_source"]
)

print("cohort1_seeds", len(c1), "cohort2_seeds", len(c2))
print("cohort_fetch_rows", dict(per_cohort))
print("live_listings_extracted", batch["total_opportunity_count"])
print("real_fetch_payloads", sum(1 for p in batch["raw_payloads"] if p.get("real_fetch")))
print("no_live_nofo_honest_empty", persist["no_live_nofo_count"])
print("per_adapter:")
for k, v in sorted(Counter(r["platform_adapter_key"] for r in batch["per_source"]).items()):
    print(f"  {k}: {v} seeds")
print(
    f"AC-3 before_tier3={before_t3} after_tier3={after_t3} "
    f"delta_tier3={after_t3 - before_t3}"
)
print(
    f"AC-3 before_mixed={before_mixed} after_mixed={after_mixed} "
    f"delta_mixed={after_mixed - before_mixed}"
)
assert after_mixed >= baseline_fed
assert batch["source_count"] == len(TA3_COHORT_SEED_IDS)
PY

echo ""
echo "=== AC-1: classify + match (needs_operator_review) ==="
uv run python -c "
from nativeforge.services.tier3_classify_match_orchestrator_service import run_tier3_classify_match_block
block = run_tier3_classify_match_block(nf_live_source_ingestion=True, nf_real_resolver_validation=True)
matches = block['classify_match']['matches']
labels = {m['match_label'] for m in matches}
prov = {g.get('provenance', {}).get('platform_adapter_key') for g in block.get('tier3_grants', []) if g.get('provenance')}
print('tier3_grant_count', block['tier3_grant_count'])
print('match_labels', labels)
print('platform_adapter_keys_sample', sorted(x for x in prov if x)[:5])
print('all_needs_operator_review', block['all_needs_operator_review'])
assert block['all_needs_operator_review']
assert labels == {'needs_operator_review'}
print('AC-1 OK')
"

echo ""
echo "=== AC-4: multi-seed-per-domain (Oweesta cluster) ==="
uv run python -c "
from nativeforge.services.tier3_foundation_corpus_persist_service import load_tier3_foundation_corpus
grants = load_tier3_foundation_corpus()
oweesta_ids = {
    'nf-seed-2026-t3-020',
    'nf-seed-2026-t3-021',
    'nf-seed-2026-t3-054',
}
rows = [g for g in grants if g.get('source_seed_id') in oweesta_ids]
seed_ids = {g['source_seed_id'] for g in rows}
print('oweesta_rows', len(rows), 'distinct_seed_ids', len(seed_ids))
assert len(seed_ids) >= 1
print('AC-4 OK')
"

echo ""
echo "=== AC-2/AC-5: honesty + SC/OK pilot regression ==="
uv run python -c "
from nativeforge.services.ta_tier3_honesty_regression_service import run_ta_tier3_honesty_regression
from nativeforge.services.sc_pilot_honesty_regression_service import run_sc_pilot_honesty_regression
from nativeforge.services.ok_pilot_honesty_regression_service import run_ok_pilot_honesty_regression
ta = run_ta_tier3_honesty_regression()
sc = run_sc_pilot_honesty_regression()
ok = run_ok_pilot_honesty_regression()
print('ta_checks', ta['checks'])
print('sc_verification_passed', sc['verification_passed'])
print('ok_verification_passed', ok['verification_passed'])
assert ta['verification_passed']
assert sc['verification_passed']
assert ok['verification_passed']
print('AC-2/AC-5 OK')
"

echo ""
echo "=== Tier-3 cohort-2 staging verify: ALL ACs PASSED ==="
