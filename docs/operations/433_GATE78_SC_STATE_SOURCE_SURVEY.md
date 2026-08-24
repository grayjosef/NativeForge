# 433 — Gate 78A: South Carolina / state source survey

33 services match `sc_` / `state_` / `top15` / `recognition` / `tier2`. Two
findings shaped this gate, and one of them is a correction to Gate 77B.

## Existing SC / state coverage

| Service | What it is |
| --- | --- |
| `sc_state_source_adapter_config_service` (107 ln) | SC reference-state adapter config, curated-offline, `live_ingest_claimed: False` |
| `sc_federal_discovery_improvement_service` (228 ln) | Gate 56 — the 65% target as arithmetic, with `SC_CATEGORIES` and `RECOGNITION_ROUTES` |
| `tier2_state_portal_config_service` | per-portal Tier-2 configs |
| `tier2_state_batch_live_fetch_service`, `tier2_classify_match_orchestrator_service`, `tier2_state_honesty_regression_service` | Tier-2 state pipeline |
| `state_tribal_affairs_html_adapter_service`, `state_tribal_listing_filter_service` | state tribal-affairs pages |
| `state_source_packet_service`, `top15_source_validation_assembler_service` | state packets, top-15 validation |
| `sc_monday_*` (7 services) | the SC customer demo surface |
| `sc_pilot_*` (4 services) | SC pilot fixtures and honesty regression |

**The rule this gate must preserve already exists.**
`sc_state_source_adapter_config_service` sets:

```python
"combined_with_federal_required": True,
"organization_geography_must_not_filter_federal": True,
```

That is "SC-specific is not SC-only", already stated. Gate 78 must not
contradict it.

## Existing recognition coverage

| Service | Contribution |
| --- | --- |
| `recognition_routing_contract_service` (Block 27) | 9 `ENTITY_TYPES`; docstring: *"State-recognized status is never treated as federally recognized"* |
| `recognition_tier_eligibility_gate_service` | tier → eligibility gating |
| `recognition_requirement_derivation_service` | requirement derivation |
| `recognition_tier_explanation_service` | human-readable explanation |
| `grants_gov_applicant_type_recognition_service` | applicant-type codes → recognition |

**The state/federal recognition separation is already law in this codebase.**
Gate 78 reuses it rather than restating it.

## Existing vocabularies that must not be forked

```text
sc_federal_discovery_improvement_service (Gate 56):
  RECOGNITION_ROUTES  federally_recognized | state_recognized | native_nonprofit
                      | native_business_economic_development | unknown
  SC_CATEGORIES       education workforce housing health culture_language
                      infrastructure economic_development public_safety
                      environment_natural_resources unknown

recognition_routing_contract_service (Block 27):
  ENTITY_TYPES        9 values incl. federally_recognized_tribe,
                      state_recognized_tribe, native_serving_nonprofit
```

### Divergences from the requested vocabulary

The gate asked for `recognition_tier: ... native_business` and
`sector: ... culture, environment, general_government`. Three names differ from
what exists:

| Gate 78 asks | Existing | Resolution |
| --- | --- | --- |
| `native_business` | `native_business_economic_development` | bridge |
| `culture` | `culture_language` | bridge |
| `environment` | `environment_natural_resources` | bridge |
| `general_government` | *(absent)* | added, bridges to `unknown` in the Gate 56 scorer |

Handled the same way Gate 76 handled source types: the requested names are the
lane's vocabulary, and an explicit map projects them onto the existing sets so
the Gate 56 improvement scorer keeps working and the divergence is visible
rather than silent. Tests assert every bridge lands in the existing vocabulary.

## Gaps this gate closes

1. No **SC source record type** — nothing models an SC source's family, owning
   state agency, terms status and promotion lifecycle. The adapter config
   describes the *adapter*, not individual sources.
2. No enforcement that an SC state source cannot be federally owned.
3. No **joinable routing** that keeps `sc_state` and `federal_sc_relevant` in
   separate lanes while letting one customer view span both.
4. No SC seed catalog.

## What must not be duplicated

- The recognition separation (Block 27) — reused.
- `RECOGNITION_ROUTES` and `SC_CATEGORIES` (Gate 56) — bridged.
- The SC adapter config — untouched.
- The Gate 76 registry and Gate 77 federal lane — composed with, not replaced.

## Correction to Gate 77B: three latent persist services, not two

Gate 77B reported two latent fixture-writing services. **There are three.** My
77B survey piped its grep through `head -20` and I reported the truncated list
as complete.

Re-surveyed without truncation:

| Service | Committed fixtures written |
| --- | --- |
| `scaled_federal_corpus_persist_service` | `la_scaled_federal_grants.json` |
| `tier2_state_corpus_persist_service` | `ta_tier2_state_grants.json`, `ta_mixed_tier13_grants.json` |
| `tier3_foundation_corpus_persist_service` | `ta_tier3_foundation_grants.json`, `ta_mixed_tier13_grants.json` |

**Five committed fixtures, not three**, and `ta_mixed_tier13_grants.json` is
written by *two* services. That file is also one of the five carrying the
`nf13-real-fed-021` SAMHSA record — so the record Gate 77 nearly lost was
reachable by two more write paths than Gate 77B identified.

All three are still latent: each accepts a `path` and their tests pass
`tmp_path`. But each **defaults to a committed path**, so a caller omitting
`path` writes committed evidence. Gate 78E routes all three through
`resolve_writeback_path`.

Also confirmed writing under `fixtures/`, but to demo/artifact paths rather than
corpus evidence, and therefore out of scope here: `nm_wa_browser_demo_bridge`,
`nm_wa_operator_surfacing_demo_artifact`, `nm_wa_operator_surfacing_demo_render`,
`nofo_showcase_intelligence_pack`, `sc_monday_curated_pack`. Worth a later look.
