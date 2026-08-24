# 418 — Gate 76A: Source registry survey

## The headline

**212 services already exist matching source / discovery / opportunity /
freshness / native / relevance / registry.** Two of the four services this gate
asked for substantially exist. Building all four as specified would have created
a parallel vocabulary next to working code — the failure mode Gates 61, 65 and 71
each caught in a different form.

So this gate composes where something exists and builds only the genuine gaps.

## Source registry: current state

| Service | Lines | What it is |
| --- | --- | --- |
| `opportunity_source_catalog.py` | 408 | Seed catalog, self-described "illustrative rows", stable UUIDs per plane |
| `source_candidate_registry_service.py` | 829 | Sprint 37 — candidates derived from a coverage plan, with onboarding readiness and risk flags |
| `authority_source_registry_service.py` | — | authority-proof sources, unrelated to funding sources |
| `source_coverage_plan_service.py` | — | lane-based coverage planning |
| `discovery_source_quality_service.py` | — | per-source quality signals |
| `source_ingestion_seed_loader_service.py` / `_seed_schema_service.py` | — | seed loading and schema |
| `source_seed_real_url_guard_service.py` | — | guards against fake URLs in seeds |
| `sc_state_source_adapter_config_service.py` | — | SC adapter config |
| `source_ingestion_tier1_federal / tier2_state / tier3_foundation` | — | per-tier adapters |

**Gap:** none of these is a *source record* with a promotion/retirement lifecycle
where `robots_terms_status` gates whether monitoring is permitted. The candidate
registry answers "which sources should we pursue"; it does not answer "is this
source cleared to be monitored, and is it stale or retired".

## Opportunity ingestion: current state

Sixteen `funding_opportunity_intake_*` services covering record shape, field
provenance, field confidence, missing-data flags, duplicate detection, fail-closed
gating, operator review queue, and confidence rollup. Plus
`opportunity_discovery_service.py`, `federal_opportunity_foundation_service.py`,
`sc_federal_discovery_improvement_service.py`, `combined_opportunity_workflow_service.py`.

**This is well covered.** The intake path already refuses to invent fields and
already tracks provenance and confidence per field.

## Freshness / staleness: current state

| Service | Scope |
| --- | --- |
| `source_freshness_service.py` (426 ln, Sprint 15) | **source** freshness — check intervals, next-due, overdue, check-run bookkeeping. DB-backed. |
| `gate32_source_freshness_service.py` | Block-era source freshness surface |
| `source_freshness_pilot_checker_service.py` / `_contract_service.py` | pilot checking |

**Gap, and it is a real one.** Everything here is *source* freshness — "when did
we last look at this page". Nothing models **opportunity** freshness — "is this
grant still open, was it amended, has a newer version superseded it". Those are
different questions with different consequences: a freshly-checked source can
serve an expired grant, and showing a customer an expired grant as current is the
failure that costs them a deadline.

## Native relevance: current state

Sixteen `native_relevance_classification_*` services (Sprint 189+), including an
evaluator, a label vocabulary of 8 labels, confidence tiers, an **overclaim
guard**, an **over-filter guard**, an explanation builder, and a human-review
trigger.

The evaluator already separates `_keyword_hit` from `_structured_signal`, which
is the distinction this gate cares about. Keyword-only matches do not reach the
strong labels.

**This is well covered.** The gap is not classification quality — it is that
nothing joins a classification to a *registry source* and an *opportunity
freshness state* to produce one routed, evidence-backed opportunity record.

## Quality measurement: current state

`opportunity_discovery_quality_service.py` (Gate 54) already implements the
baseline, and its docstring already states the governing rule this gate restates:

> **more rows is not better discovery.** Duplicates, stale sources, missing
> provenance and unknown eligibility are all penalised.

Six weighted components summing to 1.0: source freshness 0.20, native relevance
evidence 0.20, eligibility evidence 0.20, duplicate penalty 0.15, provenance
completeness 0.15, recognition routing completeness 0.10.

**Baseline X for the eventual 65% target already has a home.** Gate 85 should
measure with this, not invent a second scorer.

## Existing vocabularies that must not be forked

```text
opportunity_discovery_quality_service:
  SOURCE_TYPES        10 values
  FUNDING_GEOGRAPHIES south_carolina | federal | other_state | unknown
  RECOGNITION_TIERS   federally_recognized | state_recognized | native_nonprofit | unknown
  ELIGIBILITY_STATES  eligible | possibly_eligible | not_eligible | unknown

native_relevance_classification_label_vocabulary_service:
  8 labels from native_specific down to irrelevant
```

### Two divergences between the gate's requested vocabulary and what exists

**1. Source types.** The gate lists 12 names; the quality service has 10
different ones (`philanthropic_foundation` vs `foundation`,
`native_specific_intermediary` vs `native_intermediary`, and so on). Two
vocabularies for one concept would drift. Resolution: the registry uses the
gate's list and ships an explicit mapping onto the quality service's set, so the
existing scorer keeps working and the divergence is visible rather than silent.

**2. Recognition routing conflates two orthogonal axes.** The gate's list is:

```text
federally_recognized  state_recognized  native_nonprofit  native_business
native_housing  native_health  native_education  native_culture
native_infrastructure  unknown
```

The first four describe **who the applicant is**; the last five describe **what
the money is for**. A federally recognized tribe can pursue a housing grant —
those are not alternatives. Forcing one value per opportunity loses whichever
axis is not chosen, and would silently narrow eligibility.

Resolution: routing is a **set** of tags, and the service derives two projections
from it — `recognition_tier` (reusing the existing 4-value vocabulary) and
`native_sector`. Both axes survive. Documented in doc 420.

## Gaps this gate closes

1. A source record with a promotion/retirement lifecycle where unresolved
   robots/terms **blocks monitoring**.
2. Opportunity-level freshness: expired, amended, superseded, unknown — distinct
   from source freshness.
3. Evidence-gated Native relevance credit at the *opportunity* level, joining
   classification to routing.
4. A seed catalog whose lanes are categories and placeholders, explicitly not
   live coverage, with no fabricated `last_checked_at`.

## Gaps this gate does not close

- Live source coverage — nothing is fetched, nothing is monitored.
- The measured baseline X (Gate 85) and the 65% target (Gate 86).
- The scheduler (Gate 80), NOFO parser (81), duplicate/spam control (83),
  customer correction loop (84).
- Persistence: no migration, no rows.
