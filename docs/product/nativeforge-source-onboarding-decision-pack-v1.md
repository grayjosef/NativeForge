# NativeForge source onboarding decision pack (v1)

## Purpose

The onboarding decision pack (`schema_version: nf_source_onboarding_decision_pack_v1`) is the **final planning/review gate** between **`nf_source_candidate_registry_v1`** and any future workflow that could promote a candidate into an **active** opportunity source. It produces an **operator-ready review package**: prioritized candidate review rows, deterministic operator checks, sequenced **batch review plans**, activation boundaries, and risk flags—**without** activating sources, persisting registry rows, scraping, calling external APIs, running ingestion, or writing operator ledger actions.

Implementation: `nativeforge.services.source_onboarding_decision_pack_service.build_source_onboarding_decision_pack`.

Integration: `build_discovery_source_quality` attaches **`source_onboarding_decision_pack`** alongside **`source_coverage_plan`** and **`source_candidate_registry`** on **`nf_discovery_source_quality_v1`** (and therefore on operator decision pack **`source_quality`**).

## Schema (summary)

| Section | Description |
|--------|-------------|
| `organization_scope` | `organization_id`, `generated_at` |
| `decision_posture` | Posture, data quality score, active source count, candidate counts (`ready_for_review_count`, `legal_tos_review_count`, `deferred_count`), `recommended_batch_size` |
| `candidate_reviews` | Per-candidate review rows (see below) |
| `batch_review_plan` | Ordered batches with `candidate_ids`, `focus_lanes`, `required_checks`; **`should_create_action` always `false`** |
| `activation_boundary` | Explicit **`may_activate_sources: false`** and human/legal/TOS/freshness/provenance/dedupe requirements |
| `risk_flags` | Deterministic posture/candidate signals |
| `summary` | Short human-readable synopsis |
| `recommended_review_interval_days` | Integer aligned with posture bands |

### Candidate review row

- **`review_recommendation`**: `ready_for_operator_review` \| `needs_research` \| `requires_legal_tos_review` \| `defer_until_lane_gap_confirmed`
- **`onboarding_readiness_score`**: Integer 0–100 (deterministic; broad Native-eligible paths stay capped)
- **`required_operator_checks`**: Deterministic checklist (public access, terms/TOS where scraping might apply, broad-eligibility human review, provenance/freshness/dedupe planning, etc.)
- **`approval_blockers`**, **`suggested_validation_steps`**, **`data_governance_notes`**, **`tribal_sovereignty_notes`**
- **`no_live_ingestion_boundary`**: **`true`**
- **`can_become_active_source`**: **`false`** by default
- **`should_create_action`**: **`false`** (no ledger coupling)

## Relationship to coverage plan and candidate registry

- **`nf_source_coverage_plan_v1`** defines lane posture and sequencing context.
- **`nf_source_candidate_registry_v1`** expands lanes into deterministic candidate targets.
- **`nf_source_onboarding_decision_pack_v1`** turns those candidates into **review choreography**: readiness labels, checks, batches, and boundaries—still **planning-only**.

## Human review gate

Promotion to an active opportunity source remains **human-approved** and **out of scope** for this sprint. Broad Native-eligible and keyword-only Native relevance remain **review-required** and **never** eligibility confirmation.

## Activation boundary

The pack always exposes **`may_activate_sources: false`** and **`requires_human_approval: true`**. No sprint 38 code path writes active sources, triggers ingestion, scrapes, or calls external services.

## Legal / Terms of Service boundary

Sources that imply scraping, catalog queries, or publisher-specific monitoring surface **`requires_legal_tos_review`** and checklist items such as **`confirm_terms_of_use_or_api_policy`** and **`confirm_robots_or_access_policy_before_scraping_future`** before any **future** connector work.

## No-live-ingestion / no-scraping boundary

Payloads are **offline deterministic**. Operators perform desk review using suggested validation steps; nothing in this layer executes crawls or ingestion.

## Provenance, freshness, dedupe

Every review row includes planning expectations for **`define_provenance_capture_plan`**, **`define_freshness_check_cadence`**, and **`define_dedupe_key_strategy`** so future activation stays governed.

## Native-first, not Native-only doctrine

Coverage spans federal, tribal, philanthropic, corporate, university, and broad Native-eligible channels. The decision pack **prioritizes Native programmatic relevance** while keeping broad channels explicitly behind human review—never keyword confirmation.

## Future candidate → active opportunity source pathway

Future sprints may approve a vetted candidate through governance steps (metadata, health expectations, legal clearance), then create registry rows and connectors. Sprint 38 stops at **operator-readable decision payloads**.

## Related documents

- Coverage plan: [nativeforge-source-coverage-plan-v1.md](./nativeforge-source-coverage-plan-v1.md)
- Candidate registry: [nativeforge-source-candidate-registry-v1.md](./nativeforge-source-candidate-registry-v1.md)
