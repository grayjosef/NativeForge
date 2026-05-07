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

## Scoring calibration

- **data_quality_score** (0–100) is **deterministic** from persisted registry + offline intelligence only:
  - **Base**: arithmetic mean of `coverage_score`, `freshness_score`, `reliability_score`, and `yield_score` from existing coverage-gap intelligence (same inputs as Sprint 16).
  - **Penalties** (each capped so one factor cannot dominate unrealistically):
    - **Review burden**: `min(28, review_burden_score × 0.22)` — heavy operator review load lowers trust in automated throughput.
    - **Missing doctrine lanes**: `min(42, 4 × count(missing_lanes))` — structural gaps in Native priority lane representation.
    - **Weak lanes**: `min(18, 3 × count(weak_lanes))` — lanes that exist but are thin or mostly unhealthy among supporters.
  - **Clipping**: the composite is rounded and clipped to **0–100**.
- **`score_breakdown`** echoes numeric inputs and penalties for audits (additive field; safe for exports).
- **`reason_codes`** lists human- and machine-readable signals, including:
  - `score_base_intel_average:<float>` — mean of the four intel subscores before penalties.
  - `penalty_review_burden:<float>`, `penalty_missing_priority_lanes:<n>:<float>`, `penalty_weak_priority_lanes:<n>:<float>` — penalty magnitudes tied to the formula above.
  - `final_data_quality_score:<int>` — post-penalty score.
  - Semantic tags retained from v1: `no_active_sources`, `missing_priority_lanes:N`, `failing_sources:N`, `missing_recent_checks:N`, `low_coverage_score`, `low_freshness_score`, etc.

### Posture bands

- **critical**: no active registry sources.
- **weak**: composite score **< 38** **or** **≥ 10** missing doctrine lanes.
- **adequate**: composite score **< 62** **or** **≥ 5** missing lanes (and not weak).
- **strong**: composite score **≥ 62**, **< 5** missing lanes, and not weak/critical.

Lane rows still include `healthy_fraction` among sources that claim each lane.

### Recommended action vocabulary

Each row in **`recommended_operator_actions`** is JSON-serializable and uses a stable vocabulary (not raw blobs):

| Field | Purpose |
|-------|---------|
| `action_type` | Machine verb: `expand_native_priority_coverage`, `target_lane_coverage`, `diversify_source_mix`, `maintain_source_health`, `clear_overdue_source_checks`. |
| `priority` | `info` \| `low` \| `medium` \| `high` \| `critical` — aligned with operator decision severity vocabulary. |
| `title` | Short operator-facing headline. |
| `rationale` | Deterministic explanation tied to registry posture. |
| `focus_lanes` | Subset of doctrine lanes this action emphasizes (may be empty). |
| `affected_source_count` | Integer signal (e.g. health pressure count or overdue count). |
| `evidence_refs` | Deterministic string refs such as `source_registry:<uuid>` and `coverage_gap:<id>` when attention/gap rows exist. |
| `context_ids` | Duplicates `evidence_refs` when non-empty (interop convenience). |
| `should_create_action` | **Default `false`** — recommendations do **not** imply ledger writes. |

**Strong posture** caps recommendation urgency so operators do not see **high**/**critical** priorities in this layer (monitoring-style posture only).

### Action persistence boundary

- **Default**: recommendations are **read-only suggestions** in the decision pack / Workbench payload.
- **Optional**: `nativeforge.services.source_quality_operator_actions.persist_source_quality_recommendations` may create **`nf_operator_actions`** rows **only** when called with **`create_operator_actions=True`**. Even then, rows are created **only** for recommendations where **`should_create_action`** is explicitly true (defaults remain false in the generator).
- Duplicate suppression uses deterministic **`decision_id`** values (`nf_srcq:…`) and the existing operator-action repository “active by decision id” check — **no parallel ledger** and **no implicit spam**.

## Current default (Sprint 35)

Product default is **recommendations only**: `recommended_operator_actions` ships with every row’s `should_create_action: false`, and nothing is written to `nf_operator_actions` unless a caller explicitly enables persistence and opts a row in.

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
