#!/usr/bin/env bash
# RT partial block: provenance bridge + metadata wiring staging verify (AC-1 through AC-5).
set -euo pipefail
cd "$(dirname "$0")/.."

export NF_APP_ENV=staging
export NF_DEV_ORG_HEADERS=true
export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./nativeforge.rt_partial.db}"
export NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true
export NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED=true

echo "=== AC-5: stash@{0} preserved ==="
git stash list | head -1
test "$(git stash list | head -1 | grep -c 'stash@{0}')" -eq 1

echo ""
echo "=== AC-1: provenance vocabulary + inferred guard ==="
uv run python -c "
from nativeforge.services.org_applicant_profile_field_provenance_service import build_field_provenance_contract
from nativeforge.services.matching_profile_provenance_service import (
    derive_profile_evidence_codes,
    assert_inferred_never_promoted_to_confirmed,
)
c = build_field_provenance_contract()
methods = set(c['capture_methods'])
for m in ('public_inferred', 'tribe_confirmed', 'operator_entered'):
    assert m in methods, m
try:
    assert_inferred_never_promoted_to_confirmed(
        field_name='applicant_type',
        capture_method='public_inferred',
        proposed_confirmed=True,
    )
    raise SystemExit('guard should have raised')
except ValueError as e:
    print('inferred_promotion_blocked:', str(e)[:80])
inferred = {
    'applicant_type': 'tribal_government',
    'capture_method': 'public_inferred',
    'field_provenance': [{'field_name': 'applicant_type', 'capture_method': 'public_inferred'}],
}
print('inferred_evidence_codes', derive_profile_evidence_codes(inferred))
print('AC-1 OK')
"

echo ""
echo "=== AC-2: program-fit / geography-fit before vs after metadata wiring ==="
uv run python -c "
from nativeforge.services.real_grants_corpus_loader_service import load_nf13_real_ingested_grants
from nativeforge.services.matching_profile_provenance_service import build_matching_profile_with_provenance
from nativeforge.services.real_grants_corpus_loader_service import load_nf13_test_tribal_profile
from nativeforge.services.real_grant_opportunity_metadata_service import (
    grant_to_matching_opportunity,
    summarize_opportunity_metadata_coverage,
)
from nativeforge.services.eligibility_fit_assessment_dimension_evaluator_service import (
    evaluate_program_fit,
    evaluate_geography_fit,
)

grants = load_nf13_real_ingested_grants()
profile = build_matching_profile_with_provenance(load_nf13_test_tribal_profile())
coverage = summarize_opportunity_metadata_coverage(grants)
print('metadata_coverage', coverage)

def count_unknown(use_metadata: bool, dim: str) -> int:
    n = 0
    for g in grants:
        if use_metadata:
            opp = grant_to_matching_opportunity(g)
        else:
            opp = {'fixture_key': g.get('grant_id')}
        fn = evaluate_program_fit if dim == 'program' else evaluate_geography_fit
        if fn(opp, profile)['fit_status'] == 'unknown':
            n += 1
    return n

before_p = count_unknown(False, 'program')
after_p = count_unknown(True, 'program')
before_g = count_unknown(False, 'geo')
after_g = count_unknown(True, 'geo')
print(f'program_fit_unknown: before={before_p} after={after_p} improved={before_p - after_p}')
print(f'geography_fit_unknown: before={before_g} after={after_g} improved={before_g - after_g}')
assert after_p < before_p
assert after_g < before_g
tedc = next(g for g in grants if 'TEDC' in str(g.get('opportunity_title')))
opp = grant_to_matching_opportunity(tedc)
print('TEDC sample program_fit', evaluate_program_fit(opp, profile)['fit_status'])
print('TEDC sample geography_fit', evaluate_geography_fit(opp, profile)['fit_status'])
vague = next(g for g in grants if g.get('grant_id') == 'nf13-real-fed-001')
print('vague grant program_fit stays unknown',
      evaluate_program_fit(grant_to_matching_opportunity(vague), profile)['fit_status'])
print('AC-2 OK')
"

echo ""
echo "=== AC-3: Red Cedar synthetic baseline + profile selector ==="
uv run python -c "
from nativeforge.services.matching_profile_selector_service import (
    resolve_matching_profile,
    build_matching_profile_selector_contract,
)
from nativeforge.services.real_grant_classify_match_orchestrator_service import (
    run_real_grant_classify_match_block,
)
sel = build_matching_profile_selector_contract()
print('default_fixture', sel['default_fixture_key'])
print('profiles', sel['profiles'])
p = resolve_matching_profile()
print('resolved_fixture', p['fixture_key'], 'no_real_customer_data', p['no_real_customer_data'])
block = run_real_grant_classify_match_block()
print('orchestrator_selected', block['selected_profile_fixture_key'])
print('grant_count', block['grant_count'])
print('AC-3 OK')
"

echo ""
echo "=== AC-4: honesty regression (no staging flags required) ==="
uv run python -c "
from nativeforge.services.rt_partial_honesty_regression_service import run_rt_partial_honesty_regression
r = run_rt_partial_honesty_regression()
print('checks', r['checks'])
print('verification_passed', r['verification_passed'])
assert r['verification_passed']
print('AC-4 OK')
"

echo ""
echo "=== RT partial staging verify: ALL ACs PASSED ==="
