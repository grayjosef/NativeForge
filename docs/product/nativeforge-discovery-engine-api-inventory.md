# NativeForge discovery engine — API inventory (Sprint 20, verified Sprint 165)

Programmatic verification: `nativeforge.services.discovery_api_inventory_verification_service`
emits `nf_discovery_api_inventory_manifest_v1` from FastAPI OpenAPI paths (demo/real parity).

All discovery routes live in `src/nativeforge/api/opportunity_discovery_routes.py` on two parallel routers:

| Plane | Router prefix | Org dependency |
| ----- | ------------- | -------------- |
| Demo | `/v1/nf/demo/orgs` | `require_demo_org_db` |
| Real | `/v1/nf/real/orgs` | `require_real_org_db` |

Unless noted, paths below are **relative to** `{prefix}/{org_id}` (replace `{org_id}` with UUID). Both planes expose the **same** route templates; behavior differs only by org type scoping and demo isolation.

**Common request header (dev):** `X-NF-Org-Id: <org_uuid>` when `NF_DEV_ORG_HEADERS=true`.

---

## 1. Source registry & coverage catalog

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/discovery/sources` | Create an opportunity source (registry row). **201** — body `OpportunitySourceCreateBody`. |
| POST | `/discovery/sources/seed-catalog` | Seed illustrative catalog sources for the org; returns stats plus `coverage_summary`. |
| GET | `/discovery/sources` | List sources visible to the org (registry scope). |
| GET | `/discovery/coverage-summary` | JSON coverage summary over registered sources (`ods.discovery_coverage_summary`). |

**Major response fields (create/list source):** Serialized `NfOpportunitySource` via `opportunity_discovery_service.opportunity_source_to_dict` — includes `id`, `source_name`, `source_type`, verification fields, scheduling columns, health fields, etc.

**Demo vs real:** Same contracts; demo org rows follow demo RLS rules.

---

## 2. Discovery intake runs & candidates

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/discovery/sources/{source_id}/intake-runs` | Start an intake run (`DiscoveryIntakeRunCreateBody`: `intake_mode`, `operator_note`). **201** |
| GET | `/discovery/sources/{source_id}/intake-runs` | List intake runs for a source. |
| GET | `/discovery/intake-runs/{run_id}` | Get one intake run. |
| POST | `/discovery/intake-runs/{run_id}/candidates` | Process structured candidate batch (`StructuredCandidatesBatchBody`). |
| GET | `/discovery/intake-runs/{run_id}/candidates` | List normalized candidates for the run. |

**Query/body notes:** Candidate payloads are provider-specific dicts validated inside `discovery_intake_service.process_structured_candidates`.

---

## 3. Candidate & Grant Spark discovery quality

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/discovery/intake-candidates/{candidate_id}/quality` | Offline quality bundle for a candidate. Query: `create_review_item` (bool). |
| GET | `/grant-sparks/{spark_id}/discovery-quality` | Offline quality bundle for a Grant Spark (same query flag). |

**Schema:** Embeds `quality_schema_version` (`nf_discovery_quality_v1`) via discovery quality service summaries — see schema inventory.

---

## 4. Grant Spark discovery intelligence & discovery sparks

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/discovery/sparks` | Create Grant Spark from discovery seed (`DiscoverySparkCreateBody`). **201** / **409** on duplicate. |
| GET | `/discovery/sparks` | List sparks for org. |
| GET | `/grant-sparks/{spark_id}/discovery-intelligence` | Opportunity intelligence summary (`opportunity_intelligence_version`: `nf_discovery_v1`). |

---

## 5. Review queue

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/discovery/review-items` | List discovery review items. Queries: `review_status`, `review_item_type`, `priority`, `source_registry_id`, `intake_run_id`, `intake_candidate_id`, `grant_spark_id`, `open_queue_only`, `limit`. |
| GET | `/discovery/review-items/{review_item_id}` | Get one item (`discovery_review_service.get_review_item` enriched payload). |
| PATCH | `/discovery/review-items/{review_item_id}` | Patch queue fields (`ReviewItemPatchBody`). |

**Schema note:** List returns **arrays of dicts** without a top-level `schema_version` wrapper — see schema inventory hardening note.

---

## 6. Source freshness, due/overdue, check runs

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/discovery/sources/freshness-summary` | Org-wide freshness summary (`summary_schema_version` on payload). |
| GET | `/discovery/sources/due` | Sources due for check (derived). |
| GET | `/discovery/sources/overdue` | Sources overdue (derived). |
| GET | `/discovery/sources/{source_id}/freshness` | Per-source freshness detail (`freshness_schema_version`). |
| POST | `/discovery/sources/{source_id}/check-runs` | Create check run (`SourceCheckRunCreateBody`). **201** |
| GET | `/discovery/sources/{source_id}/check-runs` | List runs for source. |
| PATCH | `/discovery/source-check-runs/{check_run_id}` | Complete or update run (`SourceCheckRunPatchBody`) — updates source health via `finalize_completed_source_check`. |

---

## 7. Coverage gap intelligence & recommendations

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/discovery/coverage-gap-intelligence` | Full intelligence payload (`schema_version`: `nf_discovery_coverage_gap_intelligence_v1`). Queries: `severity`, `gap_type`, `domain`, `source_type`, `priority_level`, `limit`. |
| GET | `/discovery/coverage-gaps` | Filtered subset: `coverage_gaps` only (plus metadata). Default `limit=50`. |
| GET | `/discovery/source-recommendations` | Filtered subset: `source_recommendations` only. |

---

## 8. Operator decision pack, operator actions pack, ledger

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/discovery/operator-decision-pack` | Full operator decision payload (`schema_version` on pack). Queries: `limit`, `intake_run_limit`, `severity`, `item_type`, `action`, `source_registry_id`, `include_snapshots`. |
| GET | `/discovery/operator-workbench` | **Alias** — same handler as `operator-decision-pack`. |
| GET | `/discovery/operator-actions` | Condensed “actions” projection (`build_operator_actions_pack`). Same query params as decision pack. |
| GET | `/discovery/operator-actions-ledger/summary` | Ledger aggregates / KPI-style summary. |
| GET | `/discovery/operator-actions-ledger` | List ledger rows with wrapper `schema_version`: `nf_operator_actions_ledger_list_v1`. Supports filters: `status`, `severity`, `item_type`, `action`, `assigned_to`, `source_registry_id`, `review_item_id`, `intake_run_id`, `decision_id`, `open_only`, `limit`. |
| GET | `/discovery/operator-actions-ledger/{operator_action_id}` | Single ledger row (`nf_operator_action_v1` on row). |
| POST | `/discovery/operator-actions-ledger` | Manual create (`OperatorActionCreateManualBody`). **201** |
| POST | `/discovery/operator-actions-ledger/from-decision` | Create from decision item (`OperatorActionFromDecisionBody`). **201** — returns `{ outcome, operator_action }`. |
| PATCH | `/discovery/operator-actions-ledger/{operator_action_id}` | Patch lifecycle (`OperatorActionLedgerPatchBody`). |

---

## 9. Discovery evidence packs

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/discovery/evidence-pack/sources/{source_id}` | Evidence pack for opportunity source. |
| GET | `/discovery/evidence-pack/intake-candidates/{candidate_id}` | Evidence pack for intake candidate. |
| GET | `/discovery/evidence-pack/grant-sparks/{spark_id}` | Evidence pack for Grant Spark. |
| GET | `/discovery/evidence-pack/review-items/{review_item_id}` | Evidence pack for review item. |
| GET | `/discovery/evidence-pack/operator-actions/{operator_action_id}` | Evidence pack for operator action. |
| GET | `/discovery/evidence-pack/{subject_path}/{subject_id}` | Generic resolver — `subject_path` mapped via `discovery_evidence_pack_service.subject_path_to_type`. |

**Shared queries:** `include_audit_trail`, `include_linked_records`, `include_sections`, `audit_limit`.

**Schema:** Top-level `schema_version`: `nf_discovery_evidence_pack_v1` on pack bodies.

---

## 10. Export / trust surface (discovery sections)

Implemented in `src/nativeforge/api/trust_routes.py` (not the discovery router):

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/export/org-data-snapshot` | Org-wide JSON snapshot (`snapshot_schema_version`: `org_data_snapshot_v1`). Query: `include_sf424_previews`, `audit_sample_limit`, optional `actor_id`. |

**Discovery-related snapshot keys** (from `trust_surface_service.export_org_data_snapshot`):  
`discovery_review_summary`, `discovery_review_items_sample`, `source_freshness_summary`, `coverage_gap_intelligence`, `coverage_gap_sample`, `source_recommendations_sample`, `operator_decision_pack_summary`, `operator_workbench_summary`, `operator_priority_actions_sample`, `operator_action_ledger_summary`, `operator_actions_sample`, `evidence_pack_summary`, `evidence_subjects_sample`, `source_check_runs_sample`, and related `counts.*` entries.

---

## Known limitations

- **No external network**: Discovery engines are offline; routes do not call Grants.gov or scrapers.
- **Dual planes**: Clients must not mix demo and real org IDs across planes.
- **Pagination**: Many list endpoints use a simple `limit` cap rather than cursor pagination.
