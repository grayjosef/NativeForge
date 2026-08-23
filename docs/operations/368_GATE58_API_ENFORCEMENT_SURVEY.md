# 368 — Gate 58A: API enforcement survey

Status: survey complete. Findings below **corrected two of my own earlier claims.**

## Files inspected

`src/nativeforge/api/` — 23 modules, 6,512 lines:
`activation_routes`, `deps`, `deps_db`, `form_package_routes`,
`grant_spark_routes`, `health`, `isolation_deps`, `isolation_routes`,
`nofo_extraction_routes`, `operator_workbench_advisory_routes`,
`opportunity_discovery_route_helpers`, `opportunity_discovery_routes`,
`opportunity_discovery_schemas`, `org_context`, `pursuit_brief_routes`,
`pursuit_routes`, `source_ingestion_routes`, `spark_scoring_routes`,
`sprint0_routes`, `stage12_guided_demo_routes`, `tribal_profile_routes`,
`trust_routes`.

## Handlers found

A real FastAPI app with paired demo/real routers per domain
(`demo_discovery_router` / `real_discovery_router`, etc.).

```text
total route handlers:            208
handlers with an org path param: 205
```

## Existing enforcement — better than previously documented

Two layers already existed:

1. **Plane isolation.** `require_demo_org_db` / `require_real_org_db` as FastAPI
   dependencies, resolving org identity from the `X-NF-Org-Id` header against
   the `NF_DEMO_ORG_IDS` allowlist (`isolation_deps.py`). Dev-only by design;
   returns 503 when `NF_DEV_ORG_HEADERS=false`.
2. **Per-org path match.** A `same_org(path_org, ctx)` check raising on
   mismatch, called inside handler bodies.

**Correction to doc 366.** The Gate 57 threat model said "none of these
contracts is enforced at an API or storage boundary yet." That was accurate for
the *Gate 51-57* contracts (seat model, authority proof, capability matrix) but
it read as though tenant isolation were unenforced. It is not: a call-graph
analysis shows **all 205 org-scoped handlers reach a tenant enforcement
primitive**, transitively. Doc 366 overstated the exposure and 372 restates it.

**Correction to my own first scan.** A direct-call-only AST scan reported 22
unenforced handlers, including 12 evidence-pack endpoints. That was a **false
positive**. Two scanner defects caused it:

- enforcement lived one call level deeper, inside the shared
  `discovery_evidence_pack_handler` helper; and
- that helper is imported under an alias
  (`discovery_evidence_pack_handler as _discovery_evidence_pack_handler`), so
  keying the call graph on definition names missed it.

After adding transitive resolution **and** import-alias resolution, the count is
**0 unenforced**. The committed test carries both fixes and a comment saying why,
because a scanner that cries wolf trains people to ignore it.

## Gaps found — the real Gate 58 work

| Concern | State before Gate 58 |
| --- | --- |
| Tenant / org isolation | **enforced** on all 205 org-scoped handlers |
| Role resolution | **absent** — no role exists in request context at all |
| Capability check (RBAC matrix) | **absent** — matrix never called from the API |
| Authority proof check | **absent** |
| Seat / membership check | **absent** |
| Audit event on tenant denial | **absent** — bare `HTTPException`, no event |
| Gate 51-57 services imported by `api/` | **zero files** |

And the structural weakness that makes all of the above harder to fix:

**`same_org` was copy-pasted into 14 modules — and had already drifted.**
Eleven copies raise `403 "path org_id does not match authenticated org"`; three
(`operator_workbench_advisory_routes`, `source_ingestion_routes`,
`stage12_guided_demo_routes`) raise `404 "organization not found"`. Fourteen
copies means no single place to add audit, and nothing stopping copy fifteen
from differing again.

The 404 variant is arguably the better practice — it does not confirm that
another organization exists — but the inconsistency means the same violation
produces different responses depending on the route.

## Proposed minimal enforcement seam

1. `services/api_enforcement_service.py` — framework-agnostic decisions
   composing the Gate 51-57 contracts. Returns decisions, never raises.
2. `api/tenant_guard.py` — thin FastAPI adapter with **two** functions,
   `guard_same_org_403` and `guard_same_org_404`, preserving each call site's
   existing status code and detail string exactly.
3. Rewire all 14 copies to delegate. One implementation, audit on every denial,
   zero API behaviour change, no handler signatures touched.
4. A committed anti-bypass test so handler 209 cannot skip enforcement silently.

Status codes are deliberately **not** unified. Tests assert 403 in several files
and 404 in others; changing an API response is out of scope for this gate and
would be a breaking change disguised as a refactor.
