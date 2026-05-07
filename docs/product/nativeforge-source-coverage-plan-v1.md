# NativeForge source coverage plan (v1)

## Purpose

The coverage plan layer (`schema_version: nf_source_coverage_plan_v1`) turns the calibrated **`nf_discovery_source_quality_v1`** payload into a **lane-specific, sequenced operator plan** for improving NativeForge’s discovery source network. It is **deterministic**, **offline**, and **JSON-serializable**—same inputs always yield the same plan.

Implementation: `nativeforge.services.source_coverage_plan_service.build_source_coverage_plan`.

Integration: `build_discovery_source_quality` attaches **`source_coverage_plan`** alongside `recommended_operator_actions`. Both remain **recommendations only**; **no ledger writes** occur from this layer.

## Payload outline

| Field | Description |
|-------|-------------|
| `schema_version` | `nf_source_coverage_plan_v1` |
| `organization_scope` | `organization_id`, `generated_at` (from source quality) |
| `coverage_posture` | `posture`, `data_quality_score`, `active_source_count` |
| `priority_lanes` | One row per doctrine lane: status, lane priority, rationale, counts, deterministic source-type hints, suggested search targets, next operator step, `evidence_refs` |
| `sequenced_plan` | Ordered steps: `step_number`, `action_type`, priority, title, rationale, `focus_lanes`, `expected_quality_impact`, `depends_on`, **`should_create_action` (always `false`)** |
| `risk_flags` | Deterministic coverage risks (e.g. missing Native-specific federal lane, philanthropic gaps, stale network, concentration, weak broad-eligibility lane) |
| `summary` | Short human-readable synopsis |
| `recommended_review_interval_days` | Deterministic integer from posture band (critical→strong) |

## Doctrine alignment

- **Native-first, not Native-only**: broad-eligibility monitoring stays in scope; keyword-only Native mentions **never** imply confirmed eligibility—plans call out **human review** where relevant.
- **Overrepresented lanes**: rebalance through **diversification** (adding underrepresented lanes)—plans avoid language that recommends deleting registry rows to fix concentration.
- **Severe health pressure** (`failing` / repeated **empty** checks): sequenced steps prioritize **`maintain_source_health`** before philanthropy/federal lane expansion when both apply.
- **Strong posture**: expansion-class steps are capped to **medium** urgency; emphasis shifts to maintenance and residual gaps.

## Operator action boundary

Coverage plan steps mirror operator vocabulary (`expand_native_priority_coverage`, `target_lane_coverage`, `diversify_source_mix`, `maintain_source_health`, etc.) but **`should_create_action` is always `false`**. Persistence remains exclusively via **`persist_source_quality_recommendations`** when explicitly enabled (see source quality command layer doc).

## Workbench

The operator decision pack **`source_quality`** object includes **`source_coverage_plan`** as a sibling field. No separate route or table is introduced.
