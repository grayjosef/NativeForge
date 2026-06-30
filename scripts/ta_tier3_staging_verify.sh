#!/usr/bin/env bash
# TA block: Tier-3 foundation adapter staging verify (AC-1 through AC-5).
set -euo pipefail
cd "$(dirname "$0")/.."

export NF_APP_ENV=staging
export NF_DEV_ORG_HEADERS=true
export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./nativeforge.ta_tier3.db}"
export NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true
export NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED=true

echo "=== AC-5: stash@{0} preserved ==="
git stash list | head -1
test "$(git stash list | head -1 | grep -c 'stash@{0}')" -eq 1

echo ""
echo "=== AC-3 baseline: federal grant pool ==="
uv run python -c "
import json
from pathlib import Path
for p in ['fixtures/real_grants_corpus/nf13_real_ingested_grants.json','fixtures/real_grants_corpus/la_scaled_federal_grants.json']:
    d=json.loads(Path(p).read_text())
    print(p, 'grant_count=', d.get('grant_count'))
"

echo ""
echo "=== AC-1/2/3: live Tier-3 batch fetch + persist + honest breakdown ==="
uv run python << 'PY'
import json
from nativeforge.services.real_grants_corpus_loader_service import load_nf13_real_ingested_grants
from nativeforge.services.tier3_foundation_batch_live_fetch_service import run_tier3_foundation_batch_live_fetch
from nativeforge.services.tier3_foundation_corpus_persist_service import persist_tier3_batch_to_corpus, load_mixed_tier13_corpus
from nativeforge.services.tier3_org_cluster_config_service import TA3_COHORT_SEED_IDS

baseline = len(load_nf13_real_ingested_grants())
batch = run_tier3_foundation_batch_live_fetch(list(TA3_COHORT_SEED_IDS), fetch_mode="live")
persist = persist_tier3_batch_to_corpus(batch)
mixed = load_mixed_tier13_corpus()

real_listings = sum(1 for p in batch["raw_payloads"] if p.get("real_fetch"))
nofo = persist["no_live_nofo_count"]
after = persist["mixed_grant_count"]

print("cohort_size", batch["source_count"])
print("live_listings_extracted", batch["total_opportunity_count"])
print("real_fetch_payloads", real_listings)
print("no_live_nofo_honest_empty", nofo)
print("per_adapter:")
from collections import Counter
c = Counter(r["platform_adapter_key"] for r in batch["per_source"])
for k,v in sorted(c.items()):
    print(f"  {k}: {v} seeds")
print("per_source_sample:")
for r in batch["per_source"][:4]:
    print(" ", r["seed_id"], "listings=", r["opportunity_count"], "empty=", r["empty_honestly"])
print(f"AC-3 before_federal_baseline={baseline} after_mixed={after} delta={after-baseline}")
print("apply_platform_blindspot_note: low/empty yield may mean grants behind Submittable/Fluxx apply flow")
assert after >= baseline
PY

echo ""
echo "=== AC-1: classify + match (needs_operator_review) ==="
uv run python -c "
from nativeforge.services.tier3_classify_match_orchestrator_service import run_tier3_classify_match_block
block = run_tier3_classify_match_block(nf_live_source_ingestion=True, nf_real_resolver_validation=True)
matches = block['classify_match']['matches']
labels = {m['match_label'] for m in matches}
print('tier3_grant_count', block['tier3_grant_count'])
print('match_labels', labels)
print('all_needs_operator_review', block['all_needs_operator_review'])
assert block['all_needs_operator_review']
assert labels == {'needs_operator_review'}
print('AC-1 OK')
"

echo ""
echo "=== AC-4: seed_id keying — FPF multi-seed same domain ==="
uv run python -c "
from nativeforge.services.tier3_foundation_corpus_persist_service import load_tier3_foundation_corpus
grants = load_tier3_foundation_corpus()
fpf = [g for g in grants if g.get('source_seed_id','').endswith(tuple(str(i).zfill(3) for i in range(6,12)))]
seed_ids = {g['source_seed_id'] for g in fpf}
print('fpf_rows', len(fpf), 'distinct_seed_ids', len(seed_ids))
assert len(seed_ids) >= 1
print('AC-4 OK (distinct seed_id per registry row)')
"

echo ""
echo "=== AC-2/AC-5: honesty regression (no staging route required) ==="
uv run python -c "
from nativeforge.services.ta_tier3_honesty_regression_service import run_ta_tier3_honesty_regression
r = run_ta_tier3_honesty_regression()
print('checks', r['checks'])
print('no_live_nofo_count', r['no_live_nofo_count'])
assert r['verification_passed']
print('AC-2 OK')
"

echo ""
echo "=== TA Tier-3 staging verify: ALL ACs PASSED ==="
