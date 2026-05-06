# ContractForge (contract-iq) codebase audit — NativeForge readiness

**Audited repository:** `/Users/home/Code/contract-iq` (read-only).  
**Sources cited:** file paths below refer to that tree.

---

## 1. Executive summary

ContractForge is a **FastAPI + PostgreSQL + React (Vite)** multi-tenant SaaS: tenant APIs live under **`/orgs/{org_id}/…`** with JWT Auth0 or dev HS256 tokens resolving `TenantContext` (`app/lib/tenant_auth.py` lines 58–92, 141–192). There is **no `/api/contractforge` product prefix**; routers mount at the application root (`app/main.py` lines 81–133). Shared federal opportunities sit in **`contracts`** (no `org_id`); per-tenant state sits in **`contract_pipeline`**, **`org_contract_scoring`**, **`generated_drafts`**, **`response_plans`**, **`qualification_*`**, etc. (`app/db/models.py` lines 261–378, 471–668, 1205–1287, 1348–1575).

**Demo isolation already exists for ContractForge:** environment **`DEMO_ORG_IDS`** gates demo orgs (`app/config.py` lines 15–16), and **`app/lib/demo_mode.py`** (lines 41–142) defines quarantine rules so non-demo orgs do not see seeded/demo catalog rows via SQL filters and explicit API checks (`app/services/contracts_list.py` line 487; `app/api/contracts.py` lines 369–422).

**Engine maturity:** the backend carries **many pytest modules** (115 files under `tests/`), **CI** runs `ruff`, `pytest`, and a **static org_id query guard** (`/.github/workflows/ci.yml` lines 16–28; `scripts/check_org_id_predicates.py` lines 1–34). **Tenant isolation is explicitly tested** (`tests/test_tenant_isolation_smoke.py` lines 108–141; `tests/test_response_plan_api.py` line 331 “cross_org”). This is **not** greenfield scaffolding for core pursuit flows.

**Recommendation:** **Option A — same repository, additive product surface** (HTTP routes and UI basename reserved for NativeForge, parallel data model where grant semantics diverge). The codebase already favors additive routes and org-scoped enforcement; a premature “Forge Core” extraction (Option C) would fight heavy ContractForge coupling in **`contracts`** naming and scoring (`org_contract_scoring` rows 597–668). A fork (Option B) would duplicate this tenant stack unnecessarily given existing isolation patterns.

**Highest-impact gaps for NativeForge:** (1) **`organization_profiles`** are NAICS/capabilities-centric (`app/db/models.py` lines 101–134) — tribal grant profiles need a parallel or extended shape; (2) **`contracts`** + scoring tables are **contract/RFP-shaped** — grants likely need separate opportunity storage or a disciplined generalization; (3) draft review uses **`get_tenant_read`** for status transitions, so **any read-eligible role** may move drafts to `accepted` (`app/api/drafts.py` lines 193–236), which is weaker than “reviewer-only approval” in NativeForge guardrails; (4) **no RLS** — tenancy is application-layer (`app/lib/tenant_auth.py`; no Postgres RLS cited in models).

---

## 2. Product-surface recommendation (A/B/C with reasoning)

### Recommendation: **A — Same repo, separate NativeForge routes and UI surface**

**Evidence:**

1. **Routing is already modular per-domain routers**, not monolith handlers — new routers can be included alongside existing ones (`app/main.py` lines 26–133).
2. **Tenant boundary is path-parameter + dependency injection**, not a product-prefix namespace — NativeForge can mirror **`/orgs/{org_id}/…`** with grant-specific path segments or introduce an explicit **`/nativeforge/…`** mount **without** renaming ContractForge (`app/main.py` lines 86–95).
3. **Battle-tested area:** pipeline, contracts listing, scoring services, and qualification OS have extensive tests (`tests/test_pipeline.py`, `tests/test_contracts_api.py`, `tests/test_qualification_api.py`, etc.).
4. **Option C risk:** shared abstractions would require untangling **`contracts`** vs future grant NOFO rows (`app/db/models.py` lines 261–318) and contract-specific scoring dimensions (`org_contract_scoring` lines 614–668). That is **architecture-boundary work**, not audit-driven certainty.
5. **Option B cost:** duplicates Auth0/dev JWT flow (`app/lib/tenant_auth.py`), Alembic migrations (`alembic/versions/`), and CI guards — low payoff when Option A preserves one tenancy stack.

**Contradiction vs audit prompt wording:** the prompt examples use `/api/nativeforge/*`; **this app serves tenant APIs at `/orgs/…` without an `/api` prefix** (`app/main.py`). NativeForge should follow **existing URL conventions** unless the stack adds a global `/api` reverse-proxy prefix in deployment.

---

## 3. Schema audit (tables, classification, generalization recommendations)

**Authoritative table list:** 41 tables with `__tablename__` in `app/db/models.py` (lines 33–1559).

| Table | Classification | Notes / generalization recommendation |
| --- | --- | --- |
| `organizations` | **GENERIC** | Reuse as-is; consider **light extension** for product flags (NativeForge demo vs ContractForge-only) — *decision belongs in `02-architecture-boundary.md`*. |
| `users` | **GENERIC** | Reuse; `role` string column (`app/db/models.py` lines 60–65). |
| `tenant_invitations` | **GENERIC** | Reuse for onboarding invites. |
| `organization_profiles` | **AMBIGUOUS** | Heavy **contract** semantics: `naics_codes`, `capabilities`, `max_contract_size` (`app/db/models.py` lines 107–124). **Recommend split or parallel grant-profile table** rather than overloading for tribal grant fields. |
| `org_integrations` | **AMBIGUOUS** | BXI/Slack flags (`app/db/models.py` lines 137–171) — grant product may ignore or replace with integrations-specific JSON. |
| `watchlists` | **CONTRACT-SPECIFIC** | Tenant watchlists for contract discovery (`app/db/models.py` lines 174–199). NativeForge may need **grant watchlists** separately. |
| `module_event_log` | **GENERIC** (audit) | Reuse pattern for cross-module events (`app/db/models.py` lines 202–222). |
| `scrape_logs` | **CONTRACT-SPECIFIC** (global ops) | Ingestion ops log, no `org_id` (`app/db/models.py` lines 225–241). |
| `scraper_health_history` | **CONTRACT-SPECIFIC** | (`app/db/models.py` lines 244–257). |
| `contracts` | **CONTRACT-SPECIFIC** | Shared opportunity row; NAICS, SAM-shaped `raw_data`, federal scoring legacy columns (`app/db/models.py` lines 261–318). **Do not treat as grant NOFO without mapping layer.** |
| `contract_attachments` | **CONTRACT-SPECIFIC** | (`app/db/models.py` lines 404–439). |
| `enrich_jobs` | **CONTRACT-SPECIFIC** | Admin AI enrichment batches (`app/db/models.py` lines 444–467). |
| `contract_pipeline` | **AMBIGUOUS** | Per-org pipeline — **analogous** to grant pipeline but names/statuses are contract workflow (`app/db/models.py` lines 471–502). Recommend **parallel table** or generalized `opportunity_pipeline` only after `02` decision. |
| `pipeline_activities` | **AMBIGUOUS** | Audit trail (`app/db/models.py` lines 505–526). |
| `pipeline_transitions` | **AMBIGUOUS** | Auto-routing audit (`app/db/models.py` lines 530–563). |
| `fit_score_jobs` | **CONTRACT-SPECIFIC** | Batch scoring jobs (`app/db/models.py` lines 567–594). |
| `org_contract_scoring` | **CONTRACT-SPECIFIC** | Fit/PWin/priority/draft readiness/pursuit risk/bid recommendation (`app/db/models.py` lines 597–668). Grant scoring dimensions differ per NativeForge brief — **new table or versioned scoring JSON** likely cleaner than reuse. |
| `alerts` | **CONTRACT-SPECIFIC** | Match alerts (`app/db/models.py` lines 671–702). |
| `api_quota_log` | **GENERIC** (ops) | No `org_id` (`app/db/models.py` lines 705–716). |
| `bid_artifacts` | **CONTRACT-SPECIFIC** | Bid draft artifacts (`app/db/models.py` lines 719–759). |
| `bid_confidence_scores` | **CONTRACT-SPECIFIC** | (`app/db/models.py` lines 762–789). |
| `capability_gap_assessments` | **CONTRACT-SPECIFIC** | (`app/db/models.py` lines 792–831). |
| `partner_recommendation_text_cache` | **CONTRACT-SPECIFIC** | AI text cache (`app/db/models.py` lines 834–864). |
| `time_to_bid_estimates` | **CONTRACT-SPECIFIC** | (`app/db/models.py` lines 867–894). |
| `contract_pattern_observations` | **CONTRACT-SPECIFIC** | (`app/db/models.py` lines 897–920). |
| `contract_ingestion_events` | **CONTRACT-SPECIFIC** | System ingest log (`app/db/models.py` lines 923–945). |
| `scrape_failures` | **CONTRACT-SPECIFIC** | (`app/db/models.py` lines 948–966). |
| `vendor_profiles` | **CONTRACT-SPECIFIC** | USAspending cache (`app/db/models.py` lines 969–1003). |
| `vendor_awards` | **CONTRACT-SPECIFIC** | (`app/db/models.py` lines 1006–1057). |
| `federal_incumbency_cache` | **CONTRACT-SPECIFIC** | (`app/db/models.py` lines 1060–1083). |
| `sc_agency_normalization` | **CONTRACT-SPECIFIC** | SC procurement helper (`app/db/models.py` lines 1086–1099). |
| `contract_enrichment` | **CONTRACT-SPECIFIC** | Sidecar JSON (`app/db/models.py` lines 1103–1117). |
| `enrichment_jobs` | **CONTRACT-SPECIFIC** | Queue (`app/db/models.py` lines 1121–1143). |
| `llm_response_cache` | **GENERIC** | Hash-keyed LLM JSON cache (`app/db/models.py` lines 1146–1157); reuse pattern for grant LLM with different `kind` keys. |
| `competitor_stats` | **CONTRACT-SPECIFIC** | Global aggregates (`app/db/models.py` lines 1160–1177). |
| `prompt_versions` | **GENERIC** | Prompt snapshots (`app/db/models.py` lines 1181–1202). |
| `generated_drafts` | **AMBIGUOUS** | AI drafts (`app/db/models.py` lines 1205–1248). Structure fits “AI markdown + review columns”; **draft_type namespace** is contract-oriented. |
| `response_plans` | **CONTRACT-SPECIFIC** (Proposal Response Engine) | Structured plan JSON (`app/db/models.py` lines 1254–1287). |
| `draft_redlines` | **GENERIC pattern** | SME feedback (`app/db/models.py` lines 1290–1320). |
| `drafting_force_overrides` | **CONTRACT-SPECIFIC** | (`app/db/models.py` lines 1323–1345). |
| `qualification_reason_codes` | **GENERIC** | Taxonomy (`app/db/models.py` lines 1351–1367). |
| `qualification_reviews` | **AMBIGUOUS** | Review inbox — workflow parallels grant qualification (`app/db/models.py` lines 1371–1424). May **reuse** if lifecycle maps cleanly. |
| `qualification_exposures` | **AMBIGUOUS** | Analytics (`app/db/models.py` lines 1427–1455). |
| `qualification_pursuits` | **AMBIGUOUS** | Pursuit board (`app/db/models.py` lines 1458–1499). |
| `qualification_outcomes` | **CONTRACT-SPECIFIC** wording | Win/loss outcomes (`app/db/models.py` lines 1502–1549). |
| `qualification_lifecycle_events` | **AMBIGUOUS** | External lifecycle (`app/db/models.py` lines 1552–1575). |

**GENERIC tables with contract-flavored fields:** `organization_profiles.naics_codes`, `capabilities`, sizing fields (`app/db/models.py` lines 107–124) — tribal grant profile fields should **not** overload without a migration plan.

---

## 4. Services and API audit

### 4.1 Service modules (high-level classification)

| Area | Representative path | Classification |
| --- | --- | --- |
| Tenant auth | `app/lib/tenant_auth.py` | **GENERIC** — org-scoped JWT (`lines 58–192`). |
| Contracts list/today | `app/services/contracts_list.py`, `contracts_today.py` | **CONTRACT-SPECIFIC** — imports `demo_catalog_sql_filters` (`app/services/contracts_list.py` line 46). |
| Pipeline | `app/services/pipeline_service.py` | **CONTRACT-SPECIFIC** — demo quarantine (`lines 28–30`, `495–607`). |
| Scoring | `app/services/scoring/*.py` | **CONTRACT-SPECIFIC** — fit/pwin/priority/etc. |
| Ingestion AI | `app/services/ingestion/ai/enrich_run.py` | **CONTRACT-SPECIFIC** — writes shared `contracts` (`lines 22–27`). |
| Response engine | `app/services/response_engine/builder.py` | **CONTRACT-SPECIFIC** — Anthropic plan (`lines 1–12`, `101–118`). |
| Drafting | `app/services/drafting/agent.py` | **CONTRACT-SPECIFIC** — `DraftType` enum contract prose (`lines 35–41`). |
| Demo mode | `app/lib/demo_mode.py` | **GENERIC mechanism**, ContractForge-specific tags (`lines 15–18`). |

**Scaffolding vs shipped:** modules under `app/services/` are exercised by pytest broadly; **no blanket “scaffolding”** finding—specific gaps belong in section 10.

### 4.2 API routes — inventory and namespacing

**Mount pattern:** `FastAPI` includes routers **without** an `/api` prefix (`app/main.py` lines 81–133). Tenant endpoints use **`/orgs`** prefix (`app/main.py` lines 86–95).

**Representative tenant routes (router code paths):**

| HTTP | Path pattern (after prefix) | File:lines |
| --- | --- | --- |
| GET | `/{org_id}/contracts` … | `app/api/contracts.py` 220 |
| GET | `/{org_id}/contracts/today` | `app/api/contracts.py` 311 |
| GET | `/{org_id}/contracts/{contract_id}` | `app/api/contracts.py` 323 |
| POST/DELETE | `…/dismiss` | `app/api/contracts.py` 383–411 |
| GET | `…/activity`, `…/patterns`, `…/bid-artifacts` | `app/api/contracts.py` 431–465 |
| POST/GET | `…/response-plan` | `app/api/response_engine.py` 29–68 |
| GET | `/{org_id}/users` | `app/api/users.py` 41 |
| POST | `/{org_id}/contracts/{contract_id}/drafts/generate` | `app/api/drafts.py` 67–70 |
| PATCH | `…/drafts/{draft_id}/status` | `app/api/drafts.py` 193 |
| GET | `/{org_id}/pipeline` … | `app/api/pipeline.py` 46–153 |
| GET/PATCH | Qualification | `app/api/qualification.py` 128–276 |
| POST | `/{org_id}/contracts/{contract_id}/share` | `app/api/sharing.py` 35–37 |
| POST | `/onboarding/organization` | `app/api/onboarding.py` (router prefix `onboarding` at `app/main.py` line 83) |
| GET | `/health` | `app/api/health.py` 10 |
| POST | `/internal/users/by-email` | `app/api/internal_users.py` 58 |

**Admin routes** mount under `/admin/…` (`app/main.py` lines 96–133), e.g. `/admin/scrape/…`, `/admin/orgs/{org_id}/fit-score/run` (`app/api/admin_fit_score.py` lines 28–56).

**Dev-only:** `POST /admin/dev/issue-token` (`app/api/admin_dev.py` lines 24–47).

### 4.3 Auth / tenancy middleware on request path

**Tenant reads/writes:** `Depends(get_tenant_read)` / `Depends(get_tenant_write)` from `app/lib/tenant_auth.py` (`lines 195–207`) — used across drafts, contracts, pipeline APIs (e.g. `app/api/drafts.py` lines 76–77, 200).

**Super-admin:** `require_super_admin` on admin surfaces (e.g. `app/api/admin_competitive.py` line 107).

---

## 5. Frontend audit

### 5.1 Routing strategy

**Operator UI** uses React Router; **standalone** mode prefixes routes with **`/contracts/…`** (`frontend/src/operator/paths.ts` lines 28–35). **BXI module** mode uses relative segments under basename `/contracts` (`frontend/src/operator/paths.ts` lines 21–23). **No `/contractforge` URL namespace** — navigation is `/contracts/today`, `/contracts/pipeline`, etc. (`frontend/src/operator/App.tsx` routes beginning line 77).

### 5.2 Component layering

**Domain-heavy components** live under `frontend/src/operator/components/` (e.g. `ContractDetailContent.tsx`, `SparkDecisionCard.tsx`). **Primitives** use Radix UI (`frontend/package.json` lines 21–26). Domain and UI library concerns are **folder-separated**, not a formal package split.

### 5.3 Demo data handling

**Backend:** `DEMO_ORG_IDS` (`app/config.py` lines 15–16) + `app/lib/demo_mode.py` quarantine (`lines 127–142`). **Frontend:** dev operator login path (`frontend/src/operator/App.tsx` lines 68–71 references `LoginDev`). **`demo_mode` flag** surfaced on users bootstrap (`app/api/users.py` line 68 imports `is_demo_org`). **Tests:** `tests/test_demo_mode.py`, `tests/test_demo_catalog_quarantine_unit.py`.

---

## 6. Auth and tenancy audit

### 6.1 Tenancy model

**Multi-tenant SaaS** with **shared database**: organizations keyed by UUID (`app/db/models.py` lines 32–46); users carry **`org_id`** (`app/db/models.py` lines 54–62). **No row-level security** is declared in SQLAlchemy models.

### 6.2 Org scoping

**Application-layer:** FastAPI dependencies enforce JWT `https://contractiq/org_id` matches path org (`app/lib/tenant_auth.py` lines 66–91, 129–137). **Services static guard** encourages `org_id` predicates (`scripts/check_org_id_predicates.py` lines 8–14).

### 6.3 Roles

**JWT roles** read path: `admin`, `member`, `capture_lead`, `proposal_manager`, `analyst` (`app/lib/tenant_auth.py` lines 34–41). **Writes** require `admin` (or bypass/super) (`lines 73–77`). **Bypass:** `ADMIN_BYPASS_TOKEN` maps to super access (`lines 150–158).

---

## 7. AI/LLM usage audit

| Location | Input → output | “Final” use | Human gate |
| --- | --- | --- | --- |
| `app/services/ingestion/ai/enrich_run.py` | Contract text → normalized AI fields on **`contracts`** | Persists enrichment to shared opportunities (`lines 4–7`, `22–27`) | **Not** a submission gate; ingestion pipeline |
| `app/services/response_engine/builder.py` | Bundle → validated **`response_plans.plan_json`** | Persisted org artifact (`lines 101–118`) | Plan generation — downstream “submission” not modeled as gov submission |
| `app/services/drafting/agent.py` | Org + contract context → **`generated_drafts.content_markdown`** | Stored draft (`lines 17–31`, `608`) | Status transitions via API (`app/api/drafts.py` 193–251); **any read role** may accept (`lines 203–220`) |
| `app/services/scoring/bid_confidence_service.py` | Deterministic scores + optional Anthropic explanation text | **`bid_confidence_scores.explanation_text`** | Explanation only |
| `app/services/scoring/capability_gap.py` | Gap calc + optional Anthropic **`partner_recommendation_text`** | Cached / persisted (`app/db/models.py` 826–827) | Advisory text |
| `app/services/enrichment/sc_layer1.py`, `sc_layer2.py` | SC procurement enrichment | **`llm_response_cache`**, enrichment JSON | Operational enrichment |

**Anthropic client:** `app/services/ai/anthropic_client.py` (`lines 25–28`) and ingestion variant `app/services/ingestion/ai/anthropic_client.py`.

---

## 8. Demo and seed data audit

| Mechanism | Where | Cross-org risk |
| --- | --- | --- |
| **`DEMO_ORG_IDS`** env | `app/config.py` 15–16 | Only listed UUIDs treated as demo orgs (`app/lib/demo_mode.py` 28–42). |
| **Deterministic demo org UUID** | `CONTRACTFORGE_DEMO_ORG_ID` (`app/lib/demo_mode.py` 21–25) | Documented constant for demos. |
| **Seed profiles** | `app/lib/demo_seed_profiles.py` (lines 1–24 describe 24 demo sparks) | Scripts invoke seeding (referenced in module docstring line 4 — `scripts/seed_demo_contracts.py` per repo). |
| **Quarantine SQL** | `app/lib/demo_mode.py` 95–124 | Non-demo orgs filter shared catalog (`demo_catalog_sql_filters` 127–142). |
| **Dry-run unlink script** | `scripts/dryrun_unlink_quarantined_demo_contracts_for_real_orgs.py` (import in grep results) | Operational remediation if demo rows linked to real orgs. |

**Proof demo routes exist:** demo catalog tests `tests/test_demo_mode.py` (`lines 1–3` module docstring).

---

## 9. Tests and CI audit

### 9.1 Test types

- **Unit / integration (pytest):** `tests/**/*.py` — **115 files** (glob listing).
- **Frontend:** `vitest` (`frontend/package.json` lines 15–16).
- **E2E browser tests:** **No** Playwright/Cypress **frontend test script** in `frontend/package.json` (lines 5–17 list `test`, `typecheck`, `build` — **no e2e runner**). Playwright appears **Docker/scraper-related**, not UI CI (`README.md` line 295).

**Proof (no Playwright/Cypress in operator package manifest):**  
`rg "playwright|cypress" /Users/home/Code/contract-iq/frontend/package.json` → **no matches**, exit code **1** (ripgrep “no matches” semantics).

### 9.2 CI (`/.github/workflows/ci.yml`)

| Step | Lines |
| --- | --- |
| `uv sync`, `ruff check`, `ruff format --check`, `pytest -q` | 17–21 |
| Static org_id guard synthetic failure | 22–28 |
| Frontend `npm ci`, `typecheck`, `test`, `build`, `check:operator-boundary` | 41–47 |

### 9.3 Tenant isolation tests (proof)

- **Smoke tests:** `tests/test_tenant_isolation_smoke.py` lines 108–141 (`test_contracts_list_cross_org_returns_403`, etc.).
- **Response plan API:** `tests/test_response_plan_api.py` line 331 `test_cross_org_no_access`.
- **Static guard:** `tests/test_org_id_static_guard.py` lines 13–26.

---

## 10. Battle-tested vs scaffolding inventory

### Battle-tested (evidence: automated tests + CI)

- **Tenant auth & JWT parsing:** `app/lib/tenant_auth.py` — covered indirectly by API tests (`tests/test_tenant_isolation_smoke.py` lines 44–141).
- **Contracts list / detail / today:** `tests/test_contracts_api.py`, `tests/test_contracts_today.py`.
- **Pipeline mutations:** `tests/test_pipeline.py` (`test_multi_tenant_boundary_on_all_endpoints` at line 450).
- **Drafts API:** `tests/test_drafts_api.py`.
- **Qualification OS:** `tests/test_qualification_api.py`, `tests/test_qualification_service.py`.
- **Response engine:** `tests/test_response_plan_api.py`, `tests/test_response_plan_service.py`.
- **Scoring services:** `tests/test_fit_score.py`, `tests/test_pwin.py`, `tests/test_priority.py`, etc.
- **Demo quarantine:** `tests/test_demo_mode.py`, `tests/test_demo_catalog_quarantine_unit.py`.

### Unverified / partial evidence

- **Individual admin scrape/state routes:** covered unevenly — presence of `tests/test_admin_scrape.py`, `tests/test_state_scrapers.py` shows **some** coverage; **not every admin script** has a paired test without file-by-file proof.
- **Production deployment guarantees:** not audited here (infra out of scope).

---

## 11. First migration plan (described, not written)

**Goal:** introduce a **NativeForge product discriminator** without rewriting ContractForge rows.

**Safest minimal sequence (conceptual — names deferred to `02-architecture-boundary.md`):**

1. **Add optional org-level metadata** indicating NativeForge eligibility or demo cohort — implemented as **Alembic revision** against existing **`organizations`** table family (`app/db/models.py` lines 32–46), defaulting to current ContractForge behavior for all existing rows.
2. **Mount empty FastAPI router** for NativeForge namespace (`app/main.py` pattern lines 81–95) returning **501 or feature-disabled** until Sprint 0 isolation ships — **no** ContractForge query path changes.
3. **Mirror env-driven allowlist pattern** already used for demos (`app/config.py` lines 15–16; `app/lib/demo_mode.py` lines 28–42) for **NativeForge demo org IDs** in configuration — wiring only, no seed data in this step.

This sequence avoids touching **`contracts`** / **`org_contract_scoring`** until grant-specific schemas are decided.

---

## 12. Risk list (top 10)

| # | Risk | Severity | Likelihood | Mitigation |
| --- | --- | --- | --- | --- |
| 1 | **`contracts` table semantics** mismatch grants vs contracts | High | High | Parallel grant opportunity model or strict adapter layer — decide in `02`. |
| 2 | **Profile overload** — tribal fields forced into `organization_profiles` | High | Medium | Separate grant profile table or JSON extension with validation. |
| 3 | **Draft acceptance** allowed for all read roles (`app/api/drafts.py` 203–220) vs NativeForge reviewer-only gate | High | Medium | Separate permission model for NativeForge surfaces. |
| 4 | **No Postgres RLS** — tenancy bugs are catastrophic | High | Low (mitigated by tests) | Layered filters + optional RLS later; extend `tests/test_tenant_isolation_smoke.py` patterns. |
| 5 | **Demo catalog leakage** if quarantine rules miss new seed shapes | Critical | Low | Extend `quarantined_demo_catalog_sql()` (`app/lib/demo_mode.py` 95–124) + CI fixtures. |
| 6 | **AI ingestion overwrites** shared `contracts` rows affecting all tenants | Medium | Medium | Grants should avoid unscoped writes to shared tables without review workflows. |
| 7 | **URL / namespace confusion** (`/orgs` vs `/api`) across products | Medium | Medium | Document deployment base paths; align NativeForge router naming in `02`. |
| 8 | **Scoring dimension mismatch** — reusing `org_contract_scoring` for grants | High | Medium | New scoring table/version per product. |
| 9 | **Operational coupling** — shared Alembic head blocks parallel releases | Medium | Medium | Branching discipline; optional migration splitting strategy in `02`. |
| 10 | **Qualification OS coupling** — grant lifecycle differs from contract bid/no-bid | Medium | High | Map workflows explicitly before reusing `qualification_*` tables (`app/db/models.py` 1371–1549). |

---

## 13. Open questions for the human

1. **Deployment URL:** Will NativeForge ship on the **same origin** as ContractForge (path-based) or a separate subdomain? This affects CORS (`app/main.py` lines 67–78) and frontend `basename`.
2. **Shared Auth0 tenant:** Same Auth0 application with different roles, or separate tenant for NativeForge — impacts JWT namespace `https://contractiq/org_id` (`app/lib/tenant_auth.py` line 29).
3. **Grant “Spark” identity:** Should NativeForge reuse **`contracts.id`** with a type discriminator, or **never** mix federal contract rows with grant NOFO rows?
4. **Reviewer role:** Should NativeForge introduce a **`reviewer`** role distinct from `member`/`proposal_manager` (`app/lib/tenant_auth.py` lines 34–41) given draft acceptance today?
5. **Demo org:** Will NativeForge reuse **`CONTRACTFORGE_DEMO_ORG_ID`** (`app/lib/demo_mode.py` lines 21–25) or require a **separate deterministic UUID** for tribal demo branding?

---

## Appendix: Demo isolation strategy vs target (`03-demo-isolation-spec.md`)

**Already present:** tenant JWT path binding (`app/lib/tenant_auth.py`), **org_id** query conventions + **static guard** (`scripts/check_org_id_predicates.py`), **automated tenant isolation tests**, **demo org allowlist** + **shared-catalog quarantine** (`app/lib/demo_mode.py`).

**To build for NativeForge:** product-specific **demo flag**, **middleware or dependency** rejecting cross-product writes, **CI fixtures** proving NativeForge demo org cannot read/write ContractForge demo seeds — align exactly with `execution/03-demo-isolation-spec.md` once authored scope is frozen.
