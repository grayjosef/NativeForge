# NativeForge Handoff — Block NF-15: No-Evidence Honesty + Eligibility Re-Ingest (Sprints 340–348)

**Status:** Complete (local). **WAIT** — do not push unless explicitly approved.

## Summary

Locked the invariant that **missing/placeholder eligibility never means `irrelevant`**. Empty or placeholder evidence routes to `uncertain_relevance` with `eligibility_evidence_status: insufficient_data` and human review. `irrelevant` now requires **positive** non-tribal source evidence (e.g. small-business-only). Added tribal-serving agency safety net (BIA, IHS, ANA, SAMHSA, AI/AN, etc.). Fixed upstream Grants.gov parse (synopsis fallback when eligibility desc is thin) and re-ingested `nf13-real-fed-021` / `nf13-real-fed-025` with refined search.

## Guards

| Guard | Behavior |
|-------|----------|
| `no_evidence_irrelevant_guard` | Blocks `irrelevant` → `uncertain_relevance` when evidence insufficient |
| `tribal_serving_agency_safety_net` | Tribal-agency grants with empty evidence never `irrelevant` |
| `grants_gov_eligibility_parser_v2` | Includes `synopsisDesc` when `applicantEligibilityDesc` is thin |

## Upstream diagnosis (fed-021 / fed-025)

| Grant | Root cause | NF-15 fix |
|-------|------------|-----------|
| `nf13-real-fed-021` | Default keyword search hit wrong NOFO; placeholder eligibility ingested | Refined search → SM-26-024 Tribal Behavioral Health: Suicide Prevention |
| `nf13-real-fed-025` | IEGAP GAP has no posted Grants.gov NOFO; placeholder used | EPA tribal environmental TA fallback (362798) + synopsis enrichment; `reingest_program_proxy: true` |

## Re-classification (fed-021 / fed-025)

| Grant | NF-14 label | NF-15 label |
|-------|-------------|-------------|
| `nf13-real-fed-021` | `irrelevant` | `tribal_government_specific` |
| `nf13-real-fed-025` | `irrelevant` | `weak_native_relevance` |

## Corrected corpus label distribution vs NF-14

| Label | NF-14 | NF-15 | Δ |
|-------|------:|------:|--:|
| `tribal_government_specific` | 43 | 43 | 0 |
| `irrelevant` | 8 | 4 | −4 |
| `uncertain_relevance` | 2 | 4 | +2 |
| `weak_native_relevance` | 2 | 2 | 0 |
| `native_entity_eligible_broad` | 1 | 3 | +2 |
| `native_specific` | 1 | 1 | 0 |

**No tribal-federal grant in `irrelevant`** after NF-15.

## Routes

`POST .../no-evidence-honesty-reingest` (demo + real, plan-gated)

## Test baseline

Run: `ruff check . && pytest` — expect green after NF-15.

## Governance

- Staging only, **never pushed**, `stash@{0}` preserved
