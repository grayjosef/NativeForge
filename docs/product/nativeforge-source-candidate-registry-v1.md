# NativeForge source candidate registry (v1)

## Purpose

The candidate registry layer (`schema_version: nf_source_candidate_registry_v1`) turns **`nf_source_coverage_plan_v1`** lane needs into **reviewable, deterministic source-target suggestions**. It is the bridge between “coverage gaps and doctrine posture” and “operators can inspect explicit publisher-class targets before anything becomes an active opportunity source.”

Implementation: `nativeforge.services.source_candidate_registry_service.build_source_candidate_registry`.

Integration: `build_discovery_source_quality` attaches **`source_candidate_registry`** next to **`source_coverage_plan`** on the **`nf_discovery_source_quality_v1`** payload (and therefore on operator decision pack **`source_quality`**). The same build also attaches **`source_onboarding_decision_pack`** (`nf_source_onboarding_decision_pack_v1`) as the downstream onboarding review gate—see [nativeforge-source-onboarding-decision-pack-v1.md](./nativeforge-source-onboarding-decision-pack-v1.md).

## Schema

| Field | Description |
|-------|-------------|
| `schema_version` | `nf_source_candidate_registry_v1` |
| `organization_scope` | `organization_id`, `generated_at` |
| `registry_posture` | `source_quality_posture`, `data_quality_score`, `active_source_count`, `candidate_count`, `high_priority_candidate_count` |
| `candidate_sources` | Ordered candidate rows (see below) |
| `sequenced_onboarding_plan` | Mirrors coverage sequencing with **`candidate_ids`** per step; **`should_create_action` always `false`** |
| `risk_flags` | Registry-level diversification / posture signals |
| `summary` | Short synopsis |
| `recommended_review_interval_days` | Deterministic integer aligned with posture bands |

### Candidate source object

Each candidate includes:

- **`candidate_id`**: deterministic stable hash-derived identifier (`nf_src_candidate_v1_*`).
- **`lane`**: doctrine lane (aligned with Native priority lanes).
- **`source_name`**, **`source_type`**: planning labels—not live publisher identities until researched.
- **`priority`**: `critical` \| `high` \| `medium` \| `low` (strong posture caps urgency like the coverage plan).
- **`rationale`**: explicitly states **candidate-only** meaning—no implied activation or ingestion approval.
- **`suggested_url_pattern_or_search_target`**: offline search scaffolding—not a live crawl directive.
- **`expected_native_relevance`**, **`expected_update_frequency`**: planning hints only.
- **`review_status`**: always `candidate_review_required` at this layer.
- **`onboarding_readiness`**: `ready_for_review` \| `needs_research` \| `legal_tos_review_required` \| `deferred`.
- **`risk_flags`**, **`evidence_refs`**, **`next_operator_step`**.
- **`can_become_active_source`**: **`false` by default** at this layer.
- **`should_create_action`**: **`false`**—no ledger coupling.

## Lane-to-candidate mapping

Lane-specific seeds enumerate recognizable federal, philanthropic, corporate, university, and broad-eligibility **program classes** (for example federal Native-specific offices, Grants.gov catalog discipline, foundation Native networks, CSR-class philanthropy, TCU research offices, broad eligibility monitors where tribes may qualify).

Behavior bands:

- **Empty registry / critical posture**: minimum viable candidate set led by **`federal_native_specific`** seeds, plus a thin diversification slice across philanthropy, corporate philanthropy, broad-eligibility monitoring, and federal broad catalogs.
- **Missing federal Native-specific lane**: candidates for that lane trend **high/critical** urgency subject to posture caps.
- **Missing foundation / corporate philanthropy**: diversification seeds for those doctrine lanes.
- **Overrepresented lanes**: balancing targets emphasize **adding underrepresented doctrine lanes**; language avoids implying portfolio shrinkage as the remediation path.
- **Strong posture**: maintenance-scale emphasis; priorities align with coverage-plan strong caps—residual gaps treated as diligence, not emergency expansion.

## No-live-ingestion boundary

This layer **never** scrapes the web, calls external APIs, runs ingestion connectors, or persists registry rows. Outputs are **JSON-serializable planning payloads** suitable for Workbench review flows.

## Human review gate

Candidates **do not** confirm eligibility—especially for **`general_broad_with_native_eligibility`**, where keyword-only Native mentions **must not** be treated as confirmed tribal eligibility. Operators reconcile publisher rules, tribal applicability, and connector feasibility **before** activation.

## Candidate → active opportunity source (future pathway)

Future workflows may promote a candidate into **`nf_opportunity_sources`** after structured vetting (metadata mapping, health expectations, legal/TOS checks). Sprint 37 intentionally stops at **candidate records**.

## Operator action boundary

All onboarding steps set **`should_create_action`** to **`false`**. No operator-action ledger writes occur from this service.

## Native-first, not Native-only doctrine

Coverage spans federal, tribal, philanthropic, corporate, university, and broad Native-eligible channels. Broad eligibility remains in doctrine scope but stays behind explicit human review—NativeForge prioritizes Native relevance **without** pretending keyword scans establish eligibility.

## Related

- Coverage plan: [nativeforge-source-coverage-plan-v1.md](./nativeforge-source-coverage-plan-v1.md).
- Onboarding decision pack: [nativeforge-source-onboarding-decision-pack-v1.md](./nativeforge-source-onboarding-decision-pack-v1.md).
