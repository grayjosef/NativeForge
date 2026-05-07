# NativeForge security hardening — pass 1 (Sprint 32)

## Scope

This pass focused on **tenant/org boundaries**, **connector intelligence on the Operator Workbench**, **evidence routing**, **offline connector guardrails**, and **fixture/demo isolation**. It did not introduce a new authentication model or change database schema.

Relevant surfaces:

- `discovery_operator_workbench_service.build_workbench_connector_intelligence`
- Discovery HTTP routes (`opportunity_discovery_routes.py`) — already rely on `require_demo_org_db` / `require_real_org_db`, `_same_org`, and scoped repositories
- `discovery_evidence_pack_service.subject_path_to_type` — evidence-pack subject kind routing

## Tenant and organization boundaries

- **Demo vs real**: API prefixes (`/v1/nf/demo/orgs/...` vs `/v1/nf/real/orgs/...`) pair with `is_demo` flags on rows via repository scoping (`org_id` + `is_demo` / `OrgType`).
- **Path vs session**: Routes enforce `path org_id == authenticated org context` via `_same_org`.
- **Workbench connector intelligence**: Rolls up only source-check runs for the requested org **and** only registry sources included in the supplied registry list for that org. Connector summaries keyed by `source_registry_id` that are not part of that registry snapshot are ignored (defense in depth if data ever diverges).
- **Escalation recommendations**: Serialized escalation rows **always** bind `source_registry_id` and `source_check_run_id` to the authoritative source-check row being summarized; values embedded in stored JSON cannot override these identifiers in Workbench output.

## No-network connector boundary

- Connector modules under `nativeforge/services/source_connectors/` are intended to remain **offline**: normalization, static fixtures, Grants.gov-shaped dry runs, and `source_check_bridge.run_source_check_backed_connector_dry_run` (service-only entrypoint — not imported by HTTP discovery routers).
- Automated tests scan connector modules for imports of common outbound-network libraries (`requests`, `httpx`, `aiohttp`, etc.).

## Evidence URL safety

- HTTP handlers resolve evidence-pack subjects through `subject_path_to_type`; unknown path segments return `404` (`unknown evidence-pack subject_path`).
- Workbench UI builds evidence JSON links only from **UUID-shaped** identifiers (`looksLikeUuid`) and fixed **typed** path segments (`EvidenceKind`). Non-UUID strings (including `javascript:` URLs) do not produce navigation targets from connector intelligence ID columns.

## Dry-run / fixture data boundary

- `dry_run_fixture_rows` / `static_fixture_connector_intake_dry_run` live under `source_connectors` and `intake_bridge`; discovery routes do not import them directly.
- Persisted fixture-backed runs flow through the same intake pipeline only when invoked via explicit offline/dry-run helpers (tests and service-layer connector bridge), not generic catalog APIs.

## Risks not yet solved

- **Authentication**: Header-based dev org context (`NF_DEV_ORG_HEADERS`) is not a production tenant-isolation mechanism; future passes must integrate real authn/authz.
- **Stored JSON**: Connector `result_summary_json` remains attacker-influenced once written; pass 1 clamps escalation list size per source and binds escalation IDs; deeper schema validation may be warranted later.
- **Rate/size limits**: Large JSON blobs in summaries are not globally capped at persistence time.

## Recommended next hardening passes

1. Schema validation for connector result summaries at write time (Pydantic / JSON Schema).
2. Central policy for cross-tenant admin tooling (breakglass audit).
3. Content Security Policy and strict URL allowlists if any user-controlled URLs become clickable outside UUID-scoped evidence routes.
4. Automated dependency audit for optional networking stacks if connector ecosystem expands.
