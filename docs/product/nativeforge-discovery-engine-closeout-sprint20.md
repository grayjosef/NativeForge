# Sprint 20 — Discovery engine closeout

## Purpose

Stabilize documentation, route wiring, migration expectations, export consistency, offline-operation guards, and an end-to-end operator workflow smoke path **before** returning to UI work and later Native-focused grant sourcing/scraping.

## Current engine capabilities (backend)

- **Source registry**: CRUD-style create/list; catalog seeding; per-source freshness and scheduled-check intelligence.
- **Coverage catalog**: Coverage summary derived from registered sources.
- **Discovery intake**: Intake runs per source; structured candidate batches; candidate listing and quality scoring hooks.
- **Quality**: Offline discovery quality for intake candidates and Grant Sparks; optional review-item side effects.
- **Review queue**: List/filter/get/patch discovery review items.
- **Freshness & check runs**: Due/overdue listings; freshness summary; create/list source check runs; patch run completion.
- **Coverage gap intelligence**: Full intelligence plus filtered `coverage-gaps` and `source-recommendations` projections.
- **Operator workbench**: Unified decision pack (`operator-decision-pack` / `operator-workbench`), condensed operator-actions pack, ledger CRUD/summary.
- **Evidence packs**: Subject-specific evidence bundles (sources, candidates, sparks, review items, operator actions) plus generic path resolver.
- **Trust export**: Org JSON snapshot includes discovery summaries (review, freshness, check runs, gaps, recommendations, operator summaries, ledger samples, evidence summaries).

## Strategic product principle (sourcing phase — not implemented here)

NativeForge **prioritizes** Native-specific and tribal-focused funding, but must **not** hide broader federal, state, foundation, or corporate opportunities where Native governments, tribal organizations, Native-serving nonprofits, tribal colleges, Alaska Native or Native Hawaiian entities, or related applicants are eligible or competitive. Future sourcing/scraping should combine explicit Native-targeted feeds with **ranked** broader feeds using relevance, eligibility, geography, mission fit, and competitiveness — not naive title filtering.

## Intentionally not implemented (post Sprint 20)

- Live Grants.gov or external grant portal ingestion.
- Web scraping / crawling pipelines.
- Network calls from discovery services (see tests — enforced offline).
- Auth/RBAC beyond existing dev org headers.
- LLM-based ranking or summarization inside discovery engines.

## Known technical risks

- **Schema drift**: Several payloads omit per-row `schema_version` (e.g., review items, check runs); UI must coordinate with this inventory when locking contracts.
- **Alembic lineage**: Sprint migrations jump from revision `0015` to `0018` (no `0016`/`0017` files); linear chain remains valid with head `0018`.
- **Duplicate route surfaces**: Demo (`/v1/nf/demo/orgs/...`) and real (`/v1/nf/real/orgs/...`) planes duplicate routes; clients must target the correct plane.

## Known product risks

- **Coverage gaps** are heuristic until fed by richer external catalogs; operators should treat recommendations as prioritization aids.
- **Decision packs** aggregate offline signals only; they do not guarantee completeness of real-world funding landscapes without future ingestion.

## Recommended next UI surfaces

- Operator Workbench  
- Review Queue  
- Source Registry + Freshness  
- Coverage Gap Intelligence  
- Operator Action Ledger  
- Evidence Pack Viewer  

## Next phases

1. **UI pass** on the surfaces above against these stable routes and schemas.  
2. **Native-focused sourcing/scraping architecture** with broader eligibility and relevance ranking (per strategic principle above).

## References

- Endpoint inventory: `docs/product/nativeforge-discovery-engine-api-inventory.md`
- Schema inventory: `docs/product/nativeforge-discovery-schema-inventory.md`
