# NativeForge source quality command layer (v1)

## Purpose

The source quality layer (`schema_version: nf_discovery_source_quality_v1`) gives operators a **deterministic, offline** rollup of whether an organization’s discovery source registry has enough **Native-relevant coverage**, whether **priority doctrine lanes** are represented, and which sources deserve attention next. It consumes only persisted registry rows, coverage-gap intelligence, and freshness bookkeeping—**no live network**, credentials, or LLM calls.

Implementation: `nativeforge.services.discovery_source_quality_service`.

## Priority lane vocabulary

Twelve fixed lanes align with NativeForge doctrine. Each **active** registry row maps to zero or more lanes using registry metadata only (`source_type`, `funding_domains_json`, `applicant_types_json`, `covered_states_json`, `covered_regions_json`, `covered_tribal_groups_json`, names/descriptions, `native_relevance_notes`).

| Lane | Intent (abbrev.) |
|------|------------------|
| `federal_native_specific` | Federal programs strongly targeted to tribal / Native institutions (e.g. language/culture domain, BIA/IHS signals). |
| `federal_native_relevant_broad` | General federal channels that still matter for Native eligibility monitoring. |
| `tribal_government` | Tribal nation / government-class sources. |
| `tribal_college` | Tribal college / TCU-class coverage. |
| `native_nonprofit` | Native-serving nonprofit / tribal nonprofit channels. |
| `alaska_native` | Alaska Native villages, ANCs, AK geography. |
| `native_hawaiian` | Hawaiʻi / Native Hawaiian organization signals. |
| `state_local_native_relevant` | State, local, regional channels with Native relevance. |
| `foundation_native_serving` | Foundations / philanthropic networks. |
| `corporate_philanthropy` | Corporate / CSR-style philanthropy. |
| `university_research` | University research portfolios. |
| `general_broad_with_native_eligibility` | Broad eligibility / catch-all Native relevance. |

## Scoring and posture

- **data_quality_score** (0–100): blends coverage-gap subscores from existing intelligence (`coverage_score`, `freshness_score`, `reliability_score`, `yield_score`), penalizes review burden, **missing priority lanes**, and **weak lanes** (lanes supported by a single actor or mostly unhealthy supporters).
- **posture**:
  - **critical**: no active sources.
  - **weak**: low composite score or **≥10** missing doctrine lanes.
  - **adequate**: moderate composite score or **≥5** missing lanes (but not caught by weak).
  - **strong**: healthier composite and fewer structural lane gaps.

Lane rows include `healthy_fraction` among sources that claim each lane.

## Operator use

- Read **`missing_lanes`** and **`weak_lanes`** to prioritize registry expansion.
- Read **`overrepresented_lanes`** when one doctrine lane dominates the portfolio (possible imbalance).
- Use **`top_attention_sources`** for ranked remediation (failures, staleness, overdue checks, priority boosts).
- Use **`top_coverage_gaps`** for the highest-severity structural gaps from coverage-gap intelligence (same engine as Sprint 16).

## Workbench integration

`build_operator_decision_pack` adds a top-level **`source_quality`** field (full payload). `decision_summary_export` / `operator_brief` include a compact **`source_quality_summary`** (`schema_version`, `posture`, `data_quality_score`, `missing_lane_count`, `active_source_count`). Existing consumers remain compatible.

## No-network boundary

All inputs are **database-backed** registry and intelligence artifacts from prior runs. This layer does not initiate scraping, HTTP client calls, or external APIs.

## Future live-source expansion

When authenticated connectors run on a schedule, the same summary structure can absorb **live connector health** (already present in Workbench connector intelligence) and **last-ingestion counters** without changing the schema version—either by enriching lane strength from connector summaries or by bumping to `nf_discovery_source_quality_v2` if field additions require it.
