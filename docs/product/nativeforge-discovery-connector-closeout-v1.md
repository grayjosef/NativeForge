# NativeForge discovery connector closeout (v1, Sprint 30)

This document closes out the **no-network** discovery connector subsystem as an **M0-ready foundation**. It describes supported behavior, explicit non-goals, the offline boundary, end-to-end flow, vocabulary, and a readiness checklist before any live scraping.

## What the connector subsystem supports (today)

- **Source connector architecture** — offline contracts (`ConnectorSourceConfig`, `ConnectorRunContext`, normalized candidates) under `src/nativeforge/services/source_connectors/`.
- **Static fixture connector** — `dry_run_fixture_rows` turns in-memory dict rows into normalized candidates without HTTP.
- **Grants.gov-shaped path** — `grants_gov_like_to_fixture_row` / `dry_run_grants_gov_shaped_rows` for SAM/Grants.gov-like keys (still **no** live Grants.gov API).
- **Intake bridge** — `static_fixture_connector_intake_dry_run` feeds the **same** discovery intake pipeline as API-originated batches (`process_structured_candidates`).
- **Source-check-backed connector dry run** — `run_source_check_backed_connector_dry_run` creates a source-check run, runs intake, finalizes the check with `result_summary_json` blobs suitable for operators.
- **Connector run manifest** — `build_connector_run_manifest_v1` (schema `nf_connector_run_manifest_v1`): counts, health, warning codes, evidence-pack subject hints, source identifiers.
- **Diagnostics / result summary** — `build_connector_source_check_result_summary_v1` (schema `nf_connector_source_check_result_summary_v1`) aligned with manifest counters.
- **Health vocabulary** — coarse labels from `connector_health.py` (`healthy`, `empty`, `degraded`, `failed`, `stale`) driven by normalization errors, intake counters, review-required load, and overdue registry signals.
- **Operator escalation recommendations** — `build_connector_operator_escalation_recommendations` + enrichment on source-check summaries; optional persistence to `nf_operator_actions` **only** when `create_operator_actions=True` (default **false**).
- **Rich offline corpus** — JSON bundles under `fixtures/corpus/` with twelve canonical categories (`fixture_corpus.py`).
- **Evidence / operator linkage** — manifests carry `evidence_pack_subject_hints` (registry, intake run, source-check run); escalation rows include `evidence_refs` and structured subject hints for evidence tooling.

## What is explicitly NOT supported yet

- Live HTTP scraping or downloads from Grants.gov, agency sites, or RSS feeds.
- External API calls, OAuth flows, or credential-backed ingestion.
- LLM-assisted parsing or enrichment in the connector path.
- Production scheduling of connector jobs (cron/worker), tenant-specific enrichment policy engines beyond current heuristics, or automated robots/TOS enforcement.
- Frontend UX for connector operators (backend-first closeout).

## No-network boundary

The connector package must remain usable **offline**:

- No imports of `requests`, `httpx`, `aiohttp`, `urllib.request`, `socket`, LLM vendor SDKs, or cloud clients in `src/nativeforge/services/source_connectors/*.py`.
- Tests scan those modules and fail if forbidden imports appear.
- Dry runs and corpus loads use **only** packaged JSON and in-memory dicts.

## Current connector flow (reference spine)

1. **Opportunity source registry** — `nf_opportunity_sources` row scopes connector metadata.
2. **Source check** — `run_source_check_backed_connector_dry_run` opens a `nf_source_check_runs` row (`running` → finalized).
3. **Connector rows** — static fixtures or Grants.gov-shaped rows in memory.
4. **Normalization** — per-row mapping + Native relevance scoring (`normalization.py`, `native_relevance.py`).
5. **Intake** — `discovery_intake_service.process_structured_candidates` persists candidates and completes the intake run.
6. **Manifest** — `build_connector_run_manifest_v1` captures deterministic diagnostics.
7. **Health** — `intake_bridge_outcome_health` + warning codes.
8. **Result summary** — stored on the source-check row (`result_summary_json`).
9. **Escalation recommendation** — merged into the same summary under `operator_escalation_recommendations`.
10. **Evidence / operator pathway** — manifest subject hints + escalation `evidence_refs` / `evidence_pack_subject_hints` for packs and manual operator actions (optional persistence).

## Health vocabulary

| Label | Meaning (connector offline heuristic) |
| --- | --- |
| `healthy` | Intake completed without blocking errors; accepted candidates present; not empty/degraded by dominance rules; source not overdue-at-start unless overridden by staleness rule after accepts. |
| `empty` | Zero intake candidates produced from the batch (all counters zero). |
| `degraded` | No accepts, duplicate/rejection-heavy outcomes, or review-required saturation vs accepts. |
| `failed` | Normalization failed before intake, or intake reported candidate processing errors. |
| `stale` | Accept path succeeded but the registry was **overdue** for its scheduled check when the run started (`source_check_overdue`). |

Exact ordering is implemented in `intake_bridge_outcome_health`.

## Escalation vocabulary

Recommendations use `CONNECTOR_OPERATOR_ESCALATION_SCHEMA_VERSION` (`nf_connector_operator_escalation_v1`). Representative `escalation_type` values include:

- `normalization_mapping_failure` — fixture rows failed connector normalization.
- `connector_run_failed` — intake errors after normalization.
- `source_coverage_verification` — empty connector batch (`connector_run_empty`).
- `source_freshness_verification` — overdue source (`source_check_overdue`).
- `dedupe_source_overlap` — duplicate-heavy intake vs accepts.
- `native_relevance_rule_precision` — review-required saturation.
- `operator_diagnostic_note` — informational (typically **no** `nf_operator_actions` row; `should_create_action` false).

## Live connector readiness checklist

Before enabling live scraping per source:

- [ ] **Auth / secrets** — vault storage, rotation, least-privilege credentials for each upstream.
- [ ] **Rate limits** — respect publisher limits; backoff and circuit-breaking.
- [ ] **Robots.txt / TOS** — legal review and documented allow/deny per domain.
- [ ] **Schema drift monitoring** — alerts when upstream field shapes diverge from normalization assumptions.
- [ ] **Retry / backoff** — idempotent fetch keys, jittered retries, dead-letter handling.
- [ ] **Production scheduler** — durable queue, visibility timeouts, per-tenant schedules.
- [ ] **Tenant-specific enrichment gating** — policy for who may enable aggressive relevance vs monitoring lanes.
- [ ] **Source coverage priorities** — operator-owned backlog of federal/tribal-critical feeds.
- [ ] **UI exposure** — operator dashboards for runs, manifests, escalations, evidence packs.
- [ ] **Security review** — SSRF, secret leakage in logs, supply-chain review for fetch libraries.

## Known gaps before live scraping

Same themes as the checklist, summarized: **auth/secrets**, **rate limits**, **robots/TOS review**, **schema drift monitoring**, **retry/backoff**, **production scheduler**, **tenant-specific enrichment gating**, **source coverage priorities**, **UI exposure**, **security review**.

## Related docs

- `docs/product/nativeforge-fixture-corpus-v1.md`
- `docs/product/nativeforge-connector-run-manifest-v1.md`
- `docs/product/nativeforge-connector-operator-escalation-v1.md`

## Regression surface

Sprint 30 adds `tests/test_sprint30_connector_closeout_validation.py` for end-to-end alignment across corpus runs, Grants.gov-shaped paths, health/escalation scenarios, JSON serializability, offline import boundaries, and optional `nf_operator_actions` persistence defaults.

Optional helper: `scripts/nativeforge_connector_closeout_check.sh` runs deterministic connector closeout tests and writes a log under `/tmp/`.
