# NativeForge connector operator escalation (v1)

This note describes how offline connector dry runs surface **operator escalation recommendations** alongside existing review and operator-action primitives (Sprint 29). It is purely deterministic and **never performs live scraping or remote API calls**.

## Vocabulary

| Signal | Meaning | Typical recommendation |
|--------|---------|------------------------|
| **Failed run** | Normalization failed before intake, or intake reported candidate processing errors (`health_status=failed`). | High priority: investigate connector/source failure or normalization mapping. |
| **Stale source** | Intake would be healthy by counters, but the registry was overdue for its scheduled check (`health_status=stale`). | Verify freshness cadence and registry metadata. |
| **Empty run** | Zero intake candidates produced (`health_status=empty`). | Verify upstream coverage, filters, or an intentional no-op batch. |
| **Duplicate-heavy degraded** | Duplicates dominate vs accepts (`duplicate_load_dominant`, duplicate-only intake). | Inspect dedupe keys and corpus/source overlap. |
| **Review-heavy degraded** | Most accepts still require human review (`review_required_heavy`). | Tune `connector_native_relevance_v1` precision/thresholds. |
| **Normalization errors** | Rows failed connector-side normalization (`fixture_normalization_failed`). | Inspect field mapping and fixture/schema alignment. |
| **Source-check warnings** | Check finished as `succeeded_with_warnings` without intake errors, or informational warning codes on an otherwise healthy run. | Operator-facing diagnostic note only (no default ledger spam). |
| **Healthy** | Accepts present, no blocking failures, not stale/degraded/empty. | No escalation payload by default (aside from optional low-severity diagnostic notes). |

## Recommendations vs persisted actions

- **Default:** dry runs populate `operator_escalation_recommendations` on the connector **result summary** JSON and return `connector_operator_escalations` from `run_source_check_backed_connector_dry_run`. This is advisory structured output for operators and downstream UI.
- **Not default:** persisting `nf_operator_actions` rows requires `create_operator_actions=True`. Callers should keep this **false** unless they explicitly want ledger entries. The helper de-duplicates on deterministic `decision_id` values and skips duplicates without failing the dry run.

## Relationship to existing systems

- Recommendations reuse **operator decision enums** (`OperatorDecisionAction`, `OperatorDecisionItemType`, `OperatorDecisionSeverity`) as hints for titles, severity, and verbs—no parallel action taxonomy.
- Optional persistence goes through **`operator_action_service.create_operator_action_manual`**, linking `source_registry_id`, `intake_run_id`, and `source_check_run_id` when present.

## Workbench / UI

The Discovery Operator Workbench can render `operator_escalation_recommendations` from stored source-check `result_summary_json` without new endpoints. Frontend work is **out of scope** for Sprint 29; this backend payload is the stable contract.

## No-network boundary

Escalation builders are pure Python over manifests and counters. They must not import HTTP clients or initiate network I/O. Offline fixtures and source-check-backed dry runs remain the supported validation path.
