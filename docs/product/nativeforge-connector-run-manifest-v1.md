# NativeForge connector run manifest v1

Offline connector dry runs (static fixture bridge, Grants.gov-shaped mapping, source-check-backed runs) attach a deterministic **`nf_connector_run_manifest_v1`** blob alongside intake outcomes so operators and evidence tooling can explain **what ran**, **which registry/source shaped it**, and **how rows flowed through normalization vs intake**.

## Producer

`nativeforge.services.source_connectors.connector_run_manifest.build_connector_run_manifest_v1`

Emitted by:

- `static_fixture_connector_intake_dry_run` (always when intake succeeds or partially completes).
- `run_source_check_backed_connector_dry_run` on success (manifest from intake bridge) or fixture normalization failure (failure manifest before intake).

## Top-level fields

| Field | Purpose |
| --- | --- |
| `schema_version` | Constant `nf_connector_run_manifest_v1`. |
| `generated_at` | UTC ISO timestamp when the manifest was assembled. |
| `dry_run` | Connector context dry-run flag (offline paths default true). |
| `connector_id` | From `ConnectorSourceConfig.connector_id`. |
| `connector_version` | Optional release/version string when callers supply it (otherwise null). |
| `connector_schema_version` | Normalization contract, from `ConnectorRunContext.normalization_schema_version`. |
| `connector_run_id` | Optional opaque run id from `ConnectorRunContext.run_id`. |
| `source_registry_id` | UUID string for the opportunity source registry row. |
| `timestamps` | Currently `manifest_generated_at` (matches `generated_at`). |
| `ids` | `source_registry_id`, `intake_run_id`, `source_check_run_id`, `connector_run_id` (mirrors top-level id where present). |
| `counts` | See below. |
| `warning_codes` | Ordered list of machine-oriented codes (e.g. `fixture_normalization_failed`, per-row `row_error:…` on failure). |
| `health_status` | Coarse label from `intake_bridge_outcome_health`: `healthy`, `empty`, `degraded`, `failed`. |
| `source_identifiers` | Optional deterministic hints: `connector_shape`, `fixture_categories`, `corpus_schema_version`, `row_shape_hints`. |
| `evidence_pack_subject_hints` | Subject paths for evidence correlation: `opportunity_source`, `intake_run`, `source_check_run` when ids exist. |

## Counts

| Key | Meaning |
| --- | --- |
| `fixture_rows` | Input dict rows for the static fixture connector path. |
| `source_rows` | Input rows for the Grants.gov-shaped dry-run path (mutually exclusive with `fixture_rows` in practice). |
| `normalized_candidates` | Rows successfully normalized into connector candidates before intake. |
| `intake_candidates` | Candidates submitted to `process_structured_candidates` (equals intake `candidate_count`). |
| `accepted` | Intake accepted into Grant Spark. |
| `duplicate` | Intake duplicate of existing spark. |
| `rejected` | Intake rejected during seed/preview. |
| `error` | Intake engine errors per candidate. |
| `review_required` | Rows whose persisted `raw_candidate_json.connector_native_relevance_v1.review_required` is true. |
| `normalization_errors` | Connector-side normalization failures before intake (failure path). |

## Diagnostics helpers

`nativeforge.services.source_connectors.connector_diagnostics` provides pure counters and warning derivation used only for manifest assembly — **no parallel diagnostics subsystem**.

## JSON serialization

Manifest dicts are JSON-serializable (`json.dumps` safe): UUIDs are already stringified in id blocks.
