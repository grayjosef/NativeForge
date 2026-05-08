# NativeForge source activation readiness contract (v1)

## Purpose

The activation readiness contract (`schema_version: nf_source_activation_readiness_contract_v1`) is a **planning-only, JSON-serializable governance layer** that consumes **`nf_discovery_source_quality_v1`** and the Sprint 38 **`nf_source_onboarding_decision_pack_v1`**. It states the **human approvals, evidence, operator checks, and sub-contracts** (provenance, freshness, dedupe, legal/TOS, Native relevance) that must be satisfied **before** a candidate source may be considered for a **future** human-approved activation sprint.

This sprint **does not** activate sources, write registry rows, scrape, call APIs, ingest data, or create operator ledger actions.

Implementation: `nativeforge.services.source_activation_readiness_contract_service.build_source_activation_readiness_contract`.

Integration: `build_discovery_source_quality` attaches **`source_activation_readiness_contract`** next to **`source_onboarding_decision_pack`**, **`source_candidate_registry`**, and **`source_coverage_plan`** on **`nf_discovery_source_quality_v1`** (and therefore on operator **`source_quality`** payloads). Sprint 40 adds **`source_activation_preview`** (`nf_source_activation_preview_v1`) as the next **dry-run-only** gate—see [nativeforge-source-activation-preview-v1.md](./nativeforge-source-activation-preview-v1.md).

## Schema (summary)

| Section | Description |
|--------|-------------|
| `organization_scope` | `organization_id`, `generated_at` |
| `contract_posture` | Source-quality posture, data quality score, active source count, candidate counts (`review_ready_count`, `activation_ready_count` for **conditionally_ready** signals, `blocked_count`, `legal_tos_required_count`, `human_approval_required_count`) |
| `activation_contracts` | Per-candidate rows: status (`not_ready` \| `blocked` \| `review_ready` \| `conditionally_ready`), readiness score/rationale, approvals, evidence, operator checks, blockers, nested contracts, per-candidate activation boundary (**`may_activate_source_now` always false**), **`can_become_active_source` false**, **`should_create_action` false** |
| `batch_activation_readiness` | `ordered_batches` aligned to the onboarding batch plan with `batch_status`, `required_batch_checks`, **`should_create_action` false** |
| `global_activation_boundary` | Org-wide denial of activation, DB writes, scraping, external APIs, and ledger actions in this sprint |
| `risk_flags` | Deterministic posture/candidate signals |
| `summary` | Short narrative |
| `recommended_review_interval_days` | Integer aligned with posture bands |

## Relationship to upstream artifacts

- **`nf_discovery_source_quality_v1`** (Sprint 33+) provides posture, counts, and embeddings for coverage and registry builders.
- **`nf_source_coverage_plan_v1`** (Sprint 36) drives lane posture (including overrepresented-lane maintenance context).
- **`nf_source_candidate_registry_v1`** (Sprint 37) supplies deterministic candidate seeds and metadata consumed both by the onboarding pack and this contract.
- **`nf_source_onboarding_decision_pack_v1`** (Sprint 38) supplies **`candidate_reviews`** and **`batch_review_plan`** choreography that this contract extends into activation-readiness language **without changing Sprint 38 semantics**.

## Activation boundary

Every candidate row sets **`may_activate_source_now: false`**, **`may_write_active_source_now: false`**, **`requires_human_approval: true`**, **`requires_future_activation_sprint: true`**. The global boundary repeats that **no activation, no DB writes for promotion, no scraping, no external APIs, no ledger actions** are permitted from this sprint’s contract layer.

## Human approval gate

All candidates require explicit **`operator_source_review_approval`** (plus domain-specific approvals such as provenance, freshness, dedupe, Native relevance, and legal/TOS where applicable). **`human_approval_required_count`** reflects that **every** candidate remains behind human governance.

## Legal / Terms of Service boundary

**`legal_tos_contract`** surfaces **`tos_review_required`** and **`robots_or_access_policy_review_required`** where publisher rules, catalogs, or scrape-implied acquisition paths apply. **`no_scraping_until_approved`** remains **true**.

## No-live-ingestion / no-scraping / no-API boundary

Payloads are **offline deterministic**. **`global_activation_boundary`** denies scraping and external API usage **from this governance layer**; future connector work remains out of scope here.

## Provenance requirements

**`provenance_contract`** requires publisher/owner accountability, URL or search targets, capture method, citations, and operator notes before activation planning can advance.

## Freshness requirements

**`freshness_contract`** requires explicit update frequency expectations, cadence, stale thresholds, and failure handling definitions at planning time.

## Dedupe requirements

**`dedupe_contract`** requires duplicate-key strategy, overlap review, and source priority rules before concurrent sources could be promoted safely.

## Native relevance requirements

**`native_relevance_contract`** keeps **keyword-only** Native mentions **not confirmed eligible**, routes **broad Native-eligible** lanes through **human review**, and records **tribal specificity** expectations without implying eligibility proof.

## Native-first, not Native-only doctrine

Coverage spans federal, tribal, philanthropic, corporate, university, and broad Native-eligible channels. This contract **prioritizes Native programmatic relevance** while keeping broad channels explicitly behind human review—never keyword confirmation.

## Future pathway to human-approved active source creation

A future sprint may execute governed activation: ledger-approved operator actions, registry writes, and connectors **after** the approvals and evidence in this contract are satisfied. Sprint 39 stops at **activation readiness contracts**—still **planning-only**.

## Related documents

- Activation preview (Sprint 40, dry-run): [nativeforge-source-activation-preview-v1.md](./nativeforge-source-activation-preview-v1.md)
- Onboarding decision pack: [nativeforge-source-onboarding-decision-pack-v1.md](./nativeforge-source-onboarding-decision-pack-v1.md)
- Candidate registry: [nativeforge-source-candidate-registry-v1.md](./nativeforge-source-candidate-registry-v1.md)
- Coverage plan: [nativeforge-source-coverage-plan-v1.md](./nativeforge-source-coverage-plan-v1.md)
