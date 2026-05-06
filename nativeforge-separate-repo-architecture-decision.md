# NativeForge separate-repository architecture decision

**Status:** Locks architecture unless the captain explicitly revises it.  
**ContractForge (`contract-iq`):** Read-only reference implementation at `/Users/home/Code/contract-iq`. **No NativeForge code, tables, routes, or feature flags belong there.**  
**NativeForge:** Own repository, own database, own deployment path—unless the captain later decides otherwise.

This document **supersedes** any prior recommendation to build NativeForge **inside** `contract-iq` (including `audit-output.md` and the “same repo / hybrid surface” conclusion in `nativeforge-divergence-audit.md` §1). **Shared architecture ≠ shared repository.**

---

## 1. Captain’s Intent

- **NativeForge is a separate repository and a separate product codebase.** It is not a module, microfrontend, or route prefix inside ContractForge.
- **`contract-iq` is read-only reference architecture** during NativeForge planning and implementation: study patterns, copy selected files into NativeForge with attribution and adaptation, **never** merge NativeForge domain back upstream as a requirement.
- **Shared architecture does not mean a shared repository.** Lessons from FastAPI layout, tenancy, ingestion orchestration, attachment parsing, CI discipline, and demo isolation **inform** NativeForge; they **do not** imply a monorepo or a single deployable app.

---

## 2. Corrected Executive Conclusion

### Rejection of prior “same repo / additive surface / hybrid” recommendation

Earlier audits suggested mounting NativeForge alongside ContractForge in one codebase or treating domain separation as sufficient inside `contract-iq`. **That is rejected.** It would blur ownership, risk accidental coupling to `contracts` / `org_contract_scoring` (`app/db/models.py` lines 261–318, 597–668), and violate the captain’s rule: **ContractForge stays untouched; NativeForge lives elsewhere.**

### Recommendation: **Separate NativeForge repository; ContractForge as architecture donor only**

- **Product divergence** (`nativeforge-divergence-audit.md`, §3; `context/five-pillars.md` — *Five Pillars*): grant NOFOs, tribal profiles, six-dimension grant scoring (`domain/scoring-model.md` — *Six dimensions, weighted*), SF-424 mapping (`domain/federal-forms.md` — *SF-424 → entity profile field mapping*), sovereignty obligations (`domain/sovereignty-trust-framework.md`) **cannot** be expressed by renaming ContractForge tables or routes.
- **Protection of both products:** ContractForge continues its procurement lifecycle (`qualification_reviews` decision examples include `bid`, `no_bid` — `app/db/models.py` lines 1371–1375) **without** NativeForge migrations or flags. NativeForge evolves grant-native schemas **without** inheriting NAICS-first fit (`app/services/scoring/fit_score.py` lines 19–80) or bid/PWin semantics (`app/db/models.py` lines 624–662).
- **Reuse model:** **Copy or adapt selected mechanics** into NativeForge’s repo under NativeForge naming and grant domain types—**not** import from `contract-iq` as a runtime dependency for domain code.

---

## 3. Architecture Donor Map

Reference paths are under `/Users/home/Code/contract-iq`.

| Mechanic | Representative reference | Class |
| --- | --- | --- |
| **JWT + path org tenancy** (`TenantContext`, read/write roles) | `app/lib/tenant_auth.py` lines 58–77, 141–192 | **B** — copy structure; replace `https://contractiq/…` claim namespaces and route shapes for NativeForge API. |
| **Settings / env pattern** | `app/config.py` lines 7–20 | **B** |
| **DB session / FastAPI `Depends`** | `app/db/session.py`, `app/main.py` router includes lines 81–95 | **C** — study; reimplement in NativeForge scaffold. |
| **Anthropic client wrapper** | `app/services/ai/anthropic_client.py` lines 25–28 | **B** — copy; remove ContractForge-specific logging strings if any. |
| **Ingestion enrichment orchestration** (batch, skip rules) | `app/services/ingestion/ai/enrich_run.py` lines 2–27 | **C** — study; **rewrite** persistence targets (must not write grant NOFOs into a `contracts`-shaped table). |
| **Attachment parsing (no LLM in parser)** | `app/services/ingestion/attachment_parser.py` (module boundary per divergence audit) | **B** — copy; tune limits/MIME for NOFO PDFs. |
| **LLM response cache pattern** | `app/db/models.py` `LlmResponseCache` lines 1146–1157 | **C** — study schema idea; implement `nf_*` cache table in NativeForge DB. |
| **Prompt versioning snapshot** | `app/db/models.py` `PromptVersion` lines 1181–1202 | **C** |
| **Static org-scoped query guard** | `scripts/check_org_id_predicates.py` lines 1–34 | **B** — adapt predicates to NativeForge ORM names. |
| **Demo org allowlist + SQL quarantine pattern** | `app/lib/demo_mode.py` lines 28–42, 95–142; `app/config.py` lines 15–16 (`demo_org_ids`) | **B** — copy idea; **new** tags/rules for grant demo Sparks. |
| **CI: ruff + pytest + guard script** | `.github/workflows/ci.yml` lines 16–28 | **C** — replicate discipline in NativeForge repo. |
| **Frontend list/detail/card composition** | `frontend/src/operator/` (e.g. `paths.ts` lines 28–35) | **C** — study layout; **do not** copy ContractForge routes or copy as-is branding. |
| **`contracts` table / `org_contract_scoring` / fit_score.py** | `app/db/models.py` 261–318, 597–668; `app/services/scoring/fit_score.py` | **D** |
| **Response plan prompts (contracting analyst)** | `app/services/response_engine/prompts.py` lines 7–25 | **D** |
| **Draft types (GO_NO_GO, capability memo)** | `app/services/drafting/agent.py` lines 35–41 | **D** |

**Legend:** **A** = copy nearly as-is · **B** = copy then heavily adapt · **C** = study pattern only · **D** = do not copy.

---

## 4. Domain Rejection Map

These ContractForge domain concepts **must not** cross into NativeForge as-is (evidence in `contract-iq`).

| Reject | Evidence | NativeForge stance |
| --- | --- | --- |
| **`contracts` as grant opportunity table** | `Contract`: “Shared **federal contract**” (`app/db/models.py` lines 261–262); procurement columns `incumbent`, `likely_competitors`, `subcontract_flag` (lines 309–315) | Use **`nf_grant_sparks`** (or equivalent) with NOFO/CFDA semantics (`domain/grant-lifecycle.md`). |
| **`org_contract_scoring` as grant scoring** | `pwin_*`, `draft_readiness_*`, `bid_recommendation` (`app/db/models.py` lines 624–662) | **`nf_grant_scoring`** per `domain/scoring-model.md` (*Six dimensions*). |
| **NAICS-first fit** | `W_NAICS = 35`, `_naics_raw_5` (`app/services/scoring/fit_score.py` lines 19–80) | Optional secondary signal only; not primary spine. |
| **Bid / no-bid semantics** | `qualification_reviews` examples `bid`, `no_bid` (`app/db/models.py` lines 1371–1375); `bid_recommendation` column (lines 661–662) | Pursue / do not pursue / disqualified (`domain/scoring-model.md` — *Recommendation tiers*). |
| **PWin semantics** | `pwin_score`, `pwin_band` (`app/db/models.py` lines 624–631); `pwin_service.py` | Replace with grant **win likelihood** definition (`domain/scoring-model.md` — *Win Likelihood*). |
| **Contract response / RFP prompts** | “government **contracting** proposal analyst”, “solicitation structure” (`app/services/response_engine/prompts.py` lines 7–25) | NOFO extraction schema (`domain/nofo-extraction-schema.md` — *Top-level structure*). |
| **Procurement forms / bid artifacts** | `BidArtifact`, `BidConfidenceScore` (`app/db/models.py` lines 719–789); `bid_confidence_service.py` lines 1–49 | SF-424 family and grant package (`domain/federal-forms.md`). |
| **RFP/RFQ assumptions in schemas** | `RequiredForm.supported_for_autofill` forced false for contract phase (`app/services/response_engine/schemas.py` lines 63–74) | NativeForge builds **grant** form mapping layer (see §5). |
| **Contract draft status lifecycle** | `DraftType` enum (`app/services/drafting/agent.py` lines 35–41) | Grant narrative types + review gates (`context/guardrails-and-risks.md`). |
| **Contract pipeline vocabulary** | Pipeline tied to `contract_id` (`app/db/models.py` lines 471–502) | Grant pipeline stages (`domain/grant-lifecycle.md`). |
| **Vendor / competitor / incumbency intel** | `vendor_profiles`, `competitor_stats`, `federal_incumbency_cache` (`app/db/models.py` 969–1083) | Not core to M0 tribal wedge; reject unless a future grant module needs analogous **award** intel with **new** tables. |

---

## 5. NativeForge Separate Codebase Architecture

Proposed shape for **NativeForge repo only** (illustrative names).

### Backend structure

- **`src/api/`** — FastAPI routers; **tenant prefix** chosen for NativeForge (e.g. `/orgs/{org_id}/…`) is an **implementation choice**, not a mandate to mirror ContractForge’s exact paths (`app/main.py` lines 86–95 are reference only).
- **`src/domain/`** — Grant-native entities (sparks, NOFO extraction, scoring inputs).
- **`src/services/`** — Application use cases (no `Contract` types).
- **`src/workers/`** — Async ingestion / enrichment jobs.
- **`src/lib/`** — Auth, settings, crypto, feature-less utilities.

### Frontend structure

- **`apps/web/`** or **`frontend/`** — Vite/React (ContractForge uses similar stack — `frontend/package.json` in reference repo).
- **Routes:** Grant pipeline, Spark detail, profile, sovereignty/trust page (`context/m0-demo-narrative.md` — *Beat 7 — Sovereignty*) — **not** `/contracts/…` (`frontend/src/operator/paths.ts` lines 28–35 reference **pattern only**).

### Database / schema

- **Separate PostgreSQL database** from ContractForge.
- **Alembic** (or equivalent) migrations **only** in NativeForge repo.
- Core tables align with §7 (grant-native names).

### Service layer

- Explicit **application services** per bounded context: **profile**, **sparks**, **nofo**, **scoring**, **forms**, **review**, **export/audit**.

### Ingestion layer

- **Source adapters** (Grants.gov, seeded fixtures for M0): same **adapter interface pattern** as ContractForge’s `source` + `external_id` idea (`app/db/models.py` lines 269–272) **without** reusing `contracts` inserts.

### AI pipeline layer

- **NOFO extraction** prompts/schemas per `domain/nofo-extraction-schema.md`.
- **Deterministic scoring** per `domain/scoring-model.md` — LLM does not emit final numeric score (*Critical rule* in `context/five-pillars.md` — *4. Pursuit scoring*).
- **`nf_ai_runs`** for sovereignty audit (`domain/sovereignty-trust-framework.md` — *Recording every LLM call*); ContractForge has **no** `ai_runs` table (`rg "ai_runs"` over `contract-iq` → no matches — divergence audit §10).

### Form automation layer

- **Field dictionary** for SF-424 (and later SF-424A) per `domain/federal-forms.md` — *SF-424 → entity profile field mapping*; PDF generation pinned as immutable fixture (*Implementation notes*).
- **No dependency** on ContractForge response-plan JSON (`app/services/response_engine/schemas.py`) for final form fill.

### Review-gate / audit layer

- **Server-enforced** transitions for any “submission-ready” or “approved” states (`context/guardrails-and-risks.md` — *Never auto-submit*).
- **Avoid** ContractForge’s `patch_contract_draft_status` pattern that uses **`get_tenant_read`** for acceptance (`app/api/drafts.py` lines 193–220) without redesign—NativeForge should tie **accept** to explicit reviewer/consultant permissions (see §9).

---

## 6. Migration / Copy Strategy

### Candidates to **copy** (then adapt)

| Reference module | Why |
| --- | --- |
| `app/lib/tenant_auth.py` | Org-scoped JWT pattern (lines 58–77). |
| `app/services/ai/anthropic_client.py` | Thin LLM wrapper. |
| `app/services/ingestion/attachment_parser.py` | Deterministic extraction discipline. |
| `scripts/check_org_id_predicates.py` | Tenant query static analysis idea. |
| `.github/workflows/ci.yml` | CI shape (ruff/pytest). |

### Must **rewrite** after any copy

- All **imports**, **claim namespaces**, and **ORM models** — NativeForge domain types only.
- Any string referencing **contract**, **bid**, **PWin**, **solicitation** in user-facing or prompt copy.

### **Reference only** (read, do not paste)

- `app/services/scoring/fit_score.py` — understand weighting pattern; **do not** port NAICS math.
- `app/services/response_engine/builder.py` — orchestration ideas; **new** prompts/schemas.
- `app/db/models.py` — **schema inspiration** for timestamps/JSONB columns, **not** table names.

### **Must not copy**

- `app/db/models.py` **`Contract`**, **`OrgContractScoring`**, **`BidArtifact`**, **`vendor_*`**, **`qualification_*`** decision vocabulary — **D** in donor map.
- `app/services/response_engine/prompts.py` — contracting analyst (**D**).
- `app/services/drafting/agent.py` **`DraftType`** — contract prose (**D**).

**Legal/process:** Preserve license headers; document lineage in NativeForge `NOTICE` or `THIRD_PARTY` as required.

---

## 7. NativeForge Domain Model

Grant-native tables (NativeForge DB). **No rows in ContractForge DB.**

| Concept | Purpose |
| --- | --- |
| **`nf_tribal_profiles`** | Sovereignty-first entity profile (`domain/entity-profile-schema.md` — *Sections of the profile*). |
| **`nf_grant_sparks`** | Ingested grant opportunities; NOFO metadata, raw text refs (`context/five-pillars.md` — *2. Grant Spark ingestion*). |
| **`nf_nofo_extractions`** | Structured extraction + per-field confidence (`domain/nofo-extraction-schema.md`). |
| **`nf_spark_checklists`** | Tasks/forms/narratives derived from extraction + edits (`domain/grant-lifecycle.md` — *Stage 6*). |
| **`nf_sf424_previews`** | Versioned preview payloads / PDF refs (`domain/federal-forms.md` — *M0 supports SF-424 preview only*). |
| **`nf_resolution_tracker`** | Council resolution workflow (`domain/grant-lifecycle.md` — *Stage 8*). |
| **`nf_grant_scoring`** | Six dimensions + composite + tier (`domain/scoring-model.md`). |
| **`nf_grant_narratives`** | AI-assisted narrative drafts with review status (`context/five-pillars.md` — *5. Human-reviewed AI drafting*). |
| **`nf_compliance_events`** | Post-award / reporting hooks (`domain/grant-lifecycle.md` — *Stage 12*; M0 may stub empty). |
| **`nf_ai_runs`** | Provider, model, endpoint, config for LLM calls (`domain/sovereignty-trust-framework.md` — *Recording every LLM call*). |
| **`nf_audit_events`** | Exportable org audit trail (`domain/sovereignty-trust-framework.md` — *Audit logs retained*). |

**Shared cross-cutting:** `organizations` / `users` equivalent in NativeForge **with grant-appropriate roles**—not a literal copy of ContractForge `users.role` strings (`app/db/models.py` lines 65–66).

---

## 8. NativeForge Build Order

| Step | Scope |
| --- | --- |
| **0 — Repo scaffold** | New repo; Python + TS tooling; `.env.example`; CI skeleton; **no** ContractForge submodule required (optional read-only clone elsewhere). |
| **1 — Copied architecture skeleton** | FastAPI app, settings, DB session, auth middleware **adapted** from donor patterns (`tenant_auth` **B**); **empty** health route. |
| **2 — Demo isolation and fake data rules** | Env allowlist + quarantine rules inspired by `app/lib/demo_mode.py` (lines 95–142); tests proving non-demo orgs cannot see demo Sparks (`execution/03-demo-isolation-spec.md` when active). |
| **3 — Tribal profile** | `nf_tribal_profiles` + APIs per `domain/entity-profile-schema.md`. |
| **4 — Grant spark model** | `nf_grant_sparks`; seeded data for M0 (`context/five-pillars.md` — *12 demo Sparks*). |
| **5 — NOFO extraction** | `nf_nofo_extractions`; prompts/schemas per `domain/nofo-extraction-schema.md`. |
| **6 — Scoring** | `nf_grant_scoring`; deterministic engine per `domain/scoring-model.md`. |
| **7 — SF-424 preview** | `nf_sf424_previews`; mapping per `domain/federal-forms.md`. |
| **8 — Demo UI** | Pipeline + detail + trust/export beats (`context/m0-demo-narrative.md`). |

---

## 9. Tests and Validation

### Tests before feature work

- **Tenant isolation:** Cross-org access denied (pattern: `tests/test_tenant_isolation_smoke.py` lines 108–141 — **behavioral reference**, reimplemented in NativeForge).
- **Demo isolation:** Demo Sparks invisible outside demo orgs (pattern: `tests/test_demo_mode.py` — reference).
- **Scoring determinism:** Same inputs → same outputs (`domain/scoring-model.md` — *The score is deterministic*).

### Prove ContractForge was **not** modified

- NativeForge work occurs **only** in the NativeForge repository.
- **No commits** to `contract-iq` from NativeForge automation; periodic human verification that ContractForge `main` matches upstream (out of scope of NativeForge CI unless the captain adds a compliance check).
- **ContractForge remains read-only reference** — no PRs from NativeForge team that alter `contract-iq` unless the captain explicitly opens maintenance there.

### Prove copied code was adapted away from contract logic

- **Lint/rule:** forbid imports or table names `Contract`, `contracts`, `OrgContractScoring`, `bid_recommendation` in NativeForge domain packages.
- **Code review + grep gates** in NativeForge CI (analogous spirit to `scripts/check_org_id_predicates.py`).

### Prevent fake/demo data leakage

- Layered rules as in donor `demo_mode` (`app/lib/demo_mode.py` lines 127–142): allowlist orgs + **not** co-mingle demo `nf_grant_sparks` rows with production org queries.
- CI tests on list endpoints mirroring `demo_catalog_sql_filters` **concept** (lines 127–141).

---

## 10. Open Questions for Human (blocking only)

1. **Auth0 / identity:** Single IdP with a **second API audience** for NativeForge vs entirely separate Auth0 tenant—blocks JWT middleware design (`app/lib/tenant_auth.py` reference pattern only).
2. **Deployment:** Separate domains vs shared infra—blocks CORS and cookie strategy for the NativeForge frontend.
3. **ContractForge “donor” updates:** When ContractForge improves `attachment_parser` or tenant guard, does NativeForge **periodically re-merge** copies manually, or treat donor code as **one-time** fork—blocks maintenance policy.

---

**Hard rule satisfied:** This document **does not** recommend building NativeForge inside `contract-iq`. ContractForge remains **read-only reference architecture**; NativeForge is a **separate repo and product**.

---

*Stop: `nativeforge-separate-repo-architecture-decision.md` written; `/Users/home/Code/contract-iq` was not modified.*
