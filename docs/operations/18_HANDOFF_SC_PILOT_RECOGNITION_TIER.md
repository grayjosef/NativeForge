# Handoff — SC Pilot + Recognition-Tier Eligibility Gate

**Baseline:** `ec59481` (TA Tier-3)  
**Status:** Infrastructure complete (SC-0…SC-5). **Operator fixtures required** for integration ACs.

## Operator action required

Place in `fixtures/sc_pilot/`:

1. `sc_tribal_profiles.json` (`schema_version: sc_tribal_profiles_v1`)
2. `sc_eligibility_rules.json` (`schema_version: sc_eligibility_rules_v1`)

Then run: `./scripts/sc_pilot_staging_verify.sh`

## Delivered (SC-0…SC-5)

| Sprint | What |
|--------|------|
| **SC-0** | `sc_pilot_fixture_loader_service.py` — schema validation, no synthesis |
| **SC-1** | `recognition_requirement_derivation_service.py` — rules primary, text secondary, UNKNOWN honest |
| **SC-2** | `recognition_tier_eligibility_gate_service.py` — `BLOCKER_RECOGNITION_TIER_MISMATCH` independent of evidence gap |
| **SC-3** | `sc_pilot_profile_loader_service.py` + selector extension — `public_inferred`, no evidence codes |
| **SC-4** | `sc_pilot_classify_match_orchestrator_service.py` — per-profile match set with `excluded_from_match_set` |
| **SC-5** | `tests/test_sc_pilot_recognition_tier_gate.py`, `sc_pilot_staging_verify.sh` |

## Distinct tier-mismatch proof (unit tests — green without fixtures)

AC-2 unit: state_only × federal_required → **both** `recognition_tier_mismatch` blocker **and** `eligibility_evidence_gap`, with `excluded_from_match_set: true`.

AC-3 unit: federal × federal_required → **no** `recognition_tier_mismatch` blocker (evidence gap may still apply).

## Gate matrix

| requirement | state_only | federal |
|-------------|------------|---------|
| federal_required | BLOCKED / excluded | eligible |
| state_ok / open_nonprofit | eligible | eligible |
| unknown | needs_operator_review | needs_operator_review |

## Verify-live

```bash
./scripts/sc_pilot_staging_verify.sh   # exits 2 until fixtures land
uv run pytest tests/test_sc_pilot_recognition_tier_gate.py -q
```
