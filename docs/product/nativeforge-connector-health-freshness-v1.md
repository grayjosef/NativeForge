# Connector dry-run health & freshness (v1)

Operator-facing classification for **offline** connector dry runs that flow through
`static_fixture_connector_intake_dry_run` and `run_source_check_backed_connector_dry_run`.
All signals are deterministic and **no-network**: fixtures, Grants.gov-shaped rows, and
existing intake/source-check persistence only.

## Health status vocabulary

| Status | Meaning |
| --- | --- |
| **healthy** | At least one candidate was **accepted**, intake errors are zero, normalization succeeded, and the source was **not** overdue for its scheduled check at run start. |
| **empty** | Intake produced **no** candidates (total intake counters sum to zero). Explicitly not “healthy”. |
| **degraded** | Run finished without blocking failures, but outcomes are dominated by **zero accepts**, **duplicate/rejection load** vs accepts, or **review-required saturation** (two or more review-flagged rows and review count covers all accepts). |
| **failed** | Fixture normalization failed before intake, or intake reported **non-zero error** candidates. No fake accepts on failure paths. |
| **stale** | Same intake outcome as healthy (would otherwise be healthy), but `is_active_source_overdue` was true for the registry row **at dry-run start** (`source_freshness_service.is_active_source_overdue`). |

Warning codes (e.g. `source_check_overdue`, `connector_run_empty`, `duplicate_only_intake`,
`review_required_heavy`) refine manifests and `result_summary.warning_codes`.

## Mapping to source freshness

- **Registry freshness** uses `nativeforge.services.source_freshness_service`: effective
  deadlines from `last_checked_at`, `check_interval_days` / priority defaults, and
  `next_check_due_at`.
- Connector **stale** is evaluated once per dry run using the loaded
  `NfOpportunitySource` **before** intake; it does not introduce a second health system.
- Completing a source-check still runs `finalize_completed_source_check`, which updates
  `source_health_status`, `next_check_due_at`, consecutive empty/failure counters, and audit
  events (`SourceHealthStatus` may become `stale` at the **registry** level when the next
  deadline is in the past—distinct from connector manifest **stale**, which is
  specifically the operator signal for “good intake, overdue schedule”).

## Source-check `result_summary`

Persisted JSON follows `connector_result_summary_schema_version`:
`nf_connector_source_check_result_summary_v1` (see
`build_connector_source_check_result_summary_v1` in `connector_diagnostics.py`).

Each summary includes: `connector_id`, `connector_shape` (when known), `health_status`,
`warning_codes`, embedded `manifest` and `manifest_counts`, `intake_run_id`,
`source_check_run_id`, per-outcome counts (`accepted_count`, `duplicate_count`, etc.),
`fixture_rows` / `source_rows` when present, and `operator_diagnostic_message`.

Normalization failures additionally set `fixture_normalization_failed` and `fixture_errors`.

## Manifest alignment

`connector_run_manifest_v1.health_status` and counts match the intake summary and the
source-check `result_summary` fields for the same run. Failure paths keep accepted counts
at zero.

## No-network boundary

Connector health modules must not import HTTP clients, sockets, or cloud/LLM SDKs.
Dry-run and source-check paths remain fixture- and DB-backed only.

## Future live connectors

Live connectors should reuse the same classification inputs (intake counters, optional
review-required counts, and registry overdue state at run start). Network fetches stay out
of this module; a future adapter would populate rows then call the same intake bridge.
