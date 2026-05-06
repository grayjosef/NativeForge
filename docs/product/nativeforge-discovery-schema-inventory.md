# NativeForge discovery engine — schema version inventory

This document lists **stable version identifiers** attached to discovery-related payloads as of Sprint 20. Values are defined in backend services; clients should treat unknown `schema_version` values as forward-incompatible signals until verified.

## Summary table

| Schema / payload | `schema_version` or equivalent | Owning module | Notes |
| ---------------- | ------------------------------ | ------------- | ----- |
| Discovery quality (candidate / spark bundles) | `nf_discovery_quality_v1` (`quality_schema_version` inside summaries) | `nativeforge/services/discovery_quality_service.py` — `QUALITY_SCHEMA_VERSION` | Returned by quality endpoints and nested under review/export helpers. |
| Intake run serialization | Integer `run_schema_version` (currently `1`) plus string `INTAKE_SUMMARY_VERSION` (`nf_discovery_intake_summary_v1`) where applicable | `nativeforge/services/discovery_intake_service.py` | Run rows persist `run_schema_version`; list/detail payloads expose it. |
| Coverage gap intelligence | `nf_discovery_coverage_gap_intelligence_v1` | `nativeforge/services/discovery_coverage_gap_service.py` — `SCHEMA_VERSION` | Full intelligence payload and filtered slices (`coverage-gaps`, `source-recommendations`). |
| Source freshness summary | `summary_schema_version`: `nf_source_freshness_summary_v1` | `nativeforge/services/source_freshness_service.py` — `SUMMARY_SCHEMA_VERSION` | Org export and `/discovery/sources/freshness-summary`. |
| Source freshness detail (per source) | `freshness_schema_version`: `nf_source_freshness_detail_v1` | `nativeforge/services/source_freshness_service.py` — `FRESHNESS_DETAIL_SCHEMA_VERSION` | `/discovery/sources/{source_id}/freshness`. |
| Operator decision pack / workbench | `schema_version`: `nf_discovery_operator_decision_pack_v1` | `nativeforge/services/discovery_operator_workbench_service.py` — `DECISION_PACK_SCHEMA_VERSION` | Shared by `/discovery/operator-decision-pack`, `/discovery/operator-workbench`, `/discovery/operator-actions` pack builder. |
| Operator action (single row) | `schema_version`: `nf_operator_action_v1` | `nativeforge/services/operator_action_service.py` — `NF_OPERATOR_ACTION_SCHEMA_VERSION` | Serialized operator actions; `decision_schema_version` may mirror decision pack when created from the pack. |
| Operator actions ledger list wrapper | `schema_version`: `nf_operator_actions_ledger_list_v1` | `nativeforge/api/opportunity_discovery_routes.py` — `NF_OPERATOR_ACTIONS_LEDGER_LIST_SCHEMA_VERSION` | LIST endpoint wraps rows with this list envelope version. |
| Discovery evidence pack | `schema_version`: `nf_discovery_evidence_pack_v1` | `nativeforge/services/discovery_evidence_pack_service.py` — `EVIDENCE_PACK_SCHEMA_VERSION` | Evidence pack bodies; export summary uses `nf_discovery_evidence_pack_v1_export_summary_v1` composite label for the export helper. |
| Org data JSON snapshot (trust export) | `snapshot_schema_version`: `org_data_snapshot_v1` | `nativeforge/services/trust_surface_service.py` — `ORG_DATA_SNAPSHOT_VERSION` | `/export/org-data-snapshot`; embeds discovery summaries by field name, not by nested `schema_version` on each subsection. |

## Hardening notes (optional future improvements)

- **Discovery review queue list**: Each review item dict does **not** currently expose a dedicated `schema_version`; shape is defined implicitly by `discovery_review_service.review_item_to_dict`. Consider adding a lightweight `review_item_schema_version` if UI needs explicit compatibility checks.
- **Source check run dict**: `source_freshness_service.check_run_to_dict` does not include a `schema_version`; acceptable for Sprint 20 but document-driven clients may want one later.
- **Grant Spark discovery intelligence**: `opportunity_intelligence_version` (`nf_discovery_v1`) is separate from quality schema — see opportunity discovery service usage from routes.

## Compatibility guidance

- Prefer checking **top-level** `schema_version` / `*_schema_version` on API responses before interpreting nested objects.
- Org export consumers should key off `snapshot_schema_version` plus stable **field names** for embedded discovery sections (`discovery_review_summary`, `source_freshness_summary`, etc.).
