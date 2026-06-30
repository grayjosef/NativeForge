# Handoff — SC Pilot + Recognition-Tier Eligibility Gate (Amendment v2)

**Baseline:** `ec59481` (TA Tier-3)  
**Status:** Infrastructure complete (SC-0…SC-5 + amendment). **Operator fixtures required** for integration ACs.

## Operator action required

Place in `fixtures/sc_pilot/`:

1. `sc_tribal_profiles.json` (`schema_version: sc_tribal_profiles_v1`) — `recognition_type`, tri-state `incorporated` / `has_501c3`, `fiscal_sponsor_available`, provenance
2. `sc_eligibility_rules.json` (`schema_version: sc_eligibility_rules_v1`) — `recognition_requirement`, condition flags, `dual_pathway`

Then run: `./scripts/sc_pilot_staging_verify.sh`

## Delivered (SC-0…SC-5 + amendment)

| Sprint | What |
|--------|------|
| **SC-0** | `sc_pilot_fixture_loader_service.py` — schema validation, tri-state profile fields, condition flags on rules |
| **SC-1** | `recognition_requirement_derivation_service.py` + `grant_eligibility_conditions_service.py` |
| **SC-2** | `recognition_tier_eligibility_gate_service.py` v2 — tier + condition gate; `BLOCKER_RECOGNITION_TIER_MISMATCH` and `BLOCKER_ELIGIBILITY_CONDITION_MISMATCH` independent of evidence gap |
| **SC-3** | `sc_pilot_profile_loader_service.py` — `public_inferred`, profile condition fields |
| **SC-4** | `sc_pilot_classify_match_orchestrator_service.py` — dual-pathway / member-level observability |
| **SC-5** | `tests/test_sc_pilot_recognition_tier_gate.py`, `sc_pilot_staging_verify.sh` |

## Gate matrix (state_only tribe)

| requirement / condition | outcome |
|-------------------------|---------|
| `federal_required` | BLOCKED (`recognition_tier_mismatch`) |
| `federal_required_for_tribal_pathway` + `dual_pathway.nonprofit_alternative` | tribal path BLOCKED; nonprofit path eligible iff `has_501c3` or fiscal sponsor; unknown → review |
| `state_ok` + `requires_incorporation` | eligible iff incorporated; unknown → review |
| `open_nonprofit` + `requires_501c3` | eligible iff `has_501c3` or fiscal sponsor; unknown → review |
| `individual_only` | member-level note — excluded from org match set |
| `unknown` requirement | needs_operator_review |
| federal tribe (Catawba) | full set — no tier/condition gating |

## Unit-test AC proof (green without fixtures)

- **AC-2:** state_only × federal_required → both `recognition_tier_mismatch` and `eligibility_evidence_gap`
- **AC-2b:** dual pathway — tribal blocked + nonprofit eligible (501c3 confirmed) or review (501c3 unknown)
- **AC-2c:** ANA incorporation — incorporated eligible; unknown → review; false → blocked
- **AC-3:** federal × federal_required → no tier blocker
- **AC-4:** state_ok not tier-excluded for state-only tribe
- **AC-4b:** `individual_only` → `member_level_note`, excluded from org match set

## Verify-live

```bash
./scripts/sc_pilot_staging_verify.sh   # exits 2 until fixtures land
uv run pytest tests/test_sc_pilot_recognition_tier_gate.py -q
```
