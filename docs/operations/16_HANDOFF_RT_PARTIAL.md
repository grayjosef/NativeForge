# Handoff — Real-Tribe Profile Phase 2 PARTIAL (RT-1, RT-3, RT-5, RT-6/7)

**Baseline:** `64b2ca0` (SH seed catalog hygiene)  
**Scope:** Consent-independent groundwork only — no real nation profile built.

## Delivered

| Sprint | What |
|--------|------|
| **RT-1** | Provenance bridge: `public_inferred`, `tribe_confirmed`, `operator_entered` in capture vocabulary; per-field provenance on NF-13 matching profile via `matching_profile_provenance_service.py`; guards block inferred→confirmed promotion and withhold `profile_evidence_codes` for `public_inferred`. |
| **RT-3** | `grant_to_matching_opportunity()` in `real_grant_opportunity_metadata_service.py` wires `program_area` / `required_geography` from explicit grant fields, Grants.gov `funding_activity_categories`, or conservative title/eligibility patterns; gaps → `None` (UNKNOWN in fit evaluators). |
| **RT-5** | `matching_profile_selector_service.py` — default `nf13_red_cedar_nation` synthetic baseline (`no_real_customer_data`); real-tribe slot deferred; wired into classify+match orchestrators. |
| **RT-6/7** | `rt_partial_honesty_regression_service.py`, `tests/test_rt_matching_profile_provenance.py`, `scripts/rt_partial_staging_verify.sh`. |

## Deferred (operator names tribe + path B)

- **RT-2** — Build real profile  
- **RT-4** — Real-profile evidence codes  

## Verify-live

```bash
chmod +x scripts/rt_partial_staging_verify.sh
./scripts/rt_partial_staging_verify.sh
```

## Key files

- `src/nativeforge/services/matching_profile_provenance_service.py`
- `src/nativeforge/services/real_grant_opportunity_metadata_service.py`
- `src/nativeforge/services/matching_profile_selector_service.py`
- `src/nativeforge/services/rt_partial_honesty_regression_service.py`
- `tests/test_rt_matching_profile_provenance.py`
- `scripts/rt_partial_staging_verify.sh`

## AC-2 improvement (nf13 corpus, Red Cedar profile)

| Dimension | Before (no metadata) | After (RT-3 wiring) |
|-----------|---------------------|---------------------|
| `program_fit` UNKNOWN | 40 | 26 |
| `geography_fit` UNKNOWN | 40 | 1 |

TEDC grant: `program_fit`/`geography_fit` → **strong**. `nf13-real-fed-001` (Aid to Tribal Governments) stays **unknown** for program fit.
