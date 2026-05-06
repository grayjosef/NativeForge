# NativeForge vs ContractForge — Divergence architecture audit (second pass)

**Scope:** Read-only review of `/Users/home/Code/contract-iq` against NativeForge product intent in this repo.  
**Citations:** `contract-iq/...` paths are under `/Users/home/Code/contract-iq`. NativeForge research citations use `domain/...` or `context/...` and **section headings** as requested.

---

## 1. Executive conclusion

### Decision: **D — Hybrid (primarily A, with a hard domain boundary)**

**Surface / repo:** NativeForge should ship as a **separate product surface in the same repository** (same pattern as the first audit: modular FastAPI routers, org-scoped tenancy), **not** a fork—**but** that is **not** permission to relabel ContractForge’s `contracts` / `org_contract_scoring` / RFP workflow as “grants.”

**Why not pure B (fork):** Duplicates `app/lib/tenant_auth.py`–class tenancy, Alembic, and CI—low value if mechanics stay aligned.

**Why not pure C (shared “Forge Core” + modules) *as a first move*:** Premature “core” abstractions over `Contract` and `OrgContractScoring` would **encode contract semantics** into shared tables (`app/db/models.py` lines 261–318, 597–668). That risks the exact failure mode this audit is meant to prevent.

**Reusable mechanics vs non-reusable domain**

| **Reusable mechanics (patterns and infrastructure)** | **Non-reusable domain logic (must be grant-native)** |
| --- | --- |
| HTTP + JWT org scoping, DB session, job patterns, LLM call + cache pattern, attachment bytes → text, list/detail UI patterns, pytest/CI discipline | NOFO structure, tribal eligibility, six-dimension **grant** scoring (see `domain/scoring-model.md` — *Six dimensions, weighted*), SF-424 field mapping (see `domain/federal-forms.md` — *SF-424 → entity profile field mapping*), resolution/compliance lifecycles (see `domain/grant-lifecycle.md` — *Stage 8 — Tribal resolution*), cultural guardrails (see `context/guardrails-and-risks.md` — *AI guardrails*) |

**Product thesis tension:** `context/product-thesis.md` states the existing engine “generalizes” (*Why us*). **Divergence-correct reading:** **ingestion, scoring as a *pattern*, tenancy, and review *mechanisms*** generalize; **table rows, column names, and scoring math tied to NAICS/bid/procurement** do not.

---

## 2. Reusable mechanics

For each area: **ContractForge implementation (cited)** → **how it could support NativeForge** (without adopting contract domain).

### Ingestion

- **Implementation:** Pipelines write shared `contracts` rows and related logs (`app/db/models.py` lines 261–318, 923–945 `contract_ingestion_events`).  
- **Reuse:** **Job orchestration, idempotency, and “source + external_id” deduplication *patterns*** for a **separate** `nf_grant_sparks` (or equivalent) ingest path—**not** inserting grant NOFOs into `contracts` without an explicit mapping decision.

### Source adapters

- **Implementation:** `source` / `external_id` on `Contract` (`app/db/models.py` lines 269–272).  
- **Reuse:** Adapter interface (fetch → normalize → persist) is portable; **adapter implementations** for Grants.gov / agency portals are **NativeForge-specific** (per `domain/grant-lifecycle.md` — *Stage 3 — Opportunity ingestion*).

### Attachment / document parsing

- **Implementation:** `app/services/ingestion/attachment_parser.py` (module docstring: deterministic extraction, no LLM—per prior review).  
- **Reuse:** **Byte caps, MIME handling, and “no LLM in parser”** policy transfer to NOFO PDFs; **field extraction targets** differ (NOFO sections vs SOW).

### AI enrichment

- **Implementation:** `app/services/ingestion/ai/enrich_run.py` (lines 2–7, 22–27) enriches **`contracts`**.  
- **Reuse:** **Call structure** (batch, cache keying, guardrails) can inform a **new** grant enrichment service writing to **grant** tables / JSONB—not **reusing** contract enrichment output as NOFO truth.

### Document storage

- **Implementation:** `contract_attachments` linked to `contracts.id` (`app/db/models.py` lines 404–439).  
- **Reuse:** **Binary storage + metadata columns** pattern; **FK target** for NativeForge should be **grant spark / package** rows, not `contracts.id`, unless a deliberate shared binary store is introduced.

### Organization tenancy

- **Implementation:** `organizations`, `users.org_id`, path-scoped `TenantContext` (`app/db/models.py` lines 32–70; `app/lib/tenant_auth.py` lines 58–77).  
- **Reuse:** **As-is** for “one user belongs to one org for API calls” (NativeForge same).

### Audit logging

- **Implementation:** `module_event_log` for module I/O (`app/db/models.py` lines 202–222); `pipeline_activities` / `pipeline_transitions` for workflow (`app/db/models.py` lines 505–563).  
- **Reuse:** **Event JSON + timestamp** pattern. **Not** a full substitute for `domain/sovereignty-trust-framework.md` (*Audit logs retained for configurable period*) — see **Section 10**.

### Form automation

- **Implementation:** Response plan schema includes `RequiredForm` with **Phase 1** `supported_for_autofill` forced false (`app/services/response_engine/schemas.py` lines 63–74). Prompts: government **contracting** proposal analyst (`app/services/response_engine/prompts.py` lines 7–21).  
- **Reuse:** **Checklist + “missing data”** structure; **SF-424 field-filling** is **not** implemented in codebase (see **Section 9**).

### Pipeline / status workflows

- **Implementation:** `contract_pipeline.status` (`app/db/models.py` lines 471–502); qualification `decision` includes `bid` / `no_bid` examples (`app/db/models.py` lines 1371–1375).  
- **Reuse:** **State machine + audit rows** as a *pattern*; **status enum and vocabulary** must be **grant** (e.g. pursuing / submitted / awarded), not **bid/no_bid** (see **Section 3**).

### Frontend list / detail / card patterns

- **Implementation:** Operator app under `/contracts/...` (`frontend/src/operator/paths.ts` lines 28–35; `frontend/src/operator/App.tsx` imports).  
- **Reuse:** **Component patterns** (list, card, detail) **without** binding to “contract” copy or ContractForge data hooks.

### Test / CI structure

- **Implementation:** `pytest`, `ruff`, org_id static guard in CI (see `/.github/workflows/ci.yml` in prior audit).  
- **Reuse:** **Mandatory** for NativeForge: parallel tests proving **tenant isolation** and **demo isolation** for **grant** routes.

---

## 3. Domain logic that must NOT be reused directly

The following are **actively encoded** in contract-iq today and are **misleading or harmful** if pasted into NativeForge UX or scoring without replacement.

| Concept | Evidence in contract-iq | Why it diverges from NativeForge |
| --- | --- | --- |
| **NAICS-first matching** | Fit score weights NAICS heavily (`app/services/scoring/fit_score.py` lines 19–80: `W_NAICS = 35`, `_naics_raw_5`). Org profile is NAICS-centric (`app/db/models.py` lines 107–109). | NativeForge pillar scoring centers **eligibility, mission, reporting burden**, etc. (`context/five-pillars.md` — *4. Pursuit scoring*; `domain/scoring-model.md` — *Six dimensions*). NAICS may appear as **one signal**, not the spine. |
| **Contract opportunity assumptions** | `Contract` docstring: “Shared **federal contract**” (`app/db/models.py` lines 261–262). Columns: `incumbent`, `likely_competitors`, `subcontract_flag` (lines 309–315). | Grants use NOFO/assistance listings, different competition and **no “incumbent” in the same sense** (`domain/grant-lifecycle.md` — *Stage 3*). |
| **Bid / no-bid language** | `qualification_reviews` “Decision (examples): **bid, no_bid** …” (`app/db/models.py` lines 1371–1375). `org_contract_scoring.bid_recommendation` (lines 661–662). | NativeForge needs **pursue / do not pursue / disqualified** tied to **tribal eligibility** (`domain/scoring-model.md` — *Recommendation tiers*), not procurement bid labels. |
| **RFP/RFQ parsing assumptions** | Response plan system prompt: “government **contracting** proposal analyst”, “solicitation structure” (`app/services/response_engine/prompts.py` lines 7–25). | NOFOs use different sectioning; extraction schema is grant-specific (`domain/nofo-extraction-schema.md` — *Top-level structure*). |
| **Contract proposal drafting** | `DraftType` includes `GO_NO_GO_MEMO`, `CAPABILITY_MATCH_NARRATIVE`, `RESPONSE_OUTLINE` (`app/services/drafting/agent.py` lines 35–41). | M0 grant drafting is **NOFO summary, outline, SF-424 autofill** (`context/five-pillars.md` — *5. Human-reviewed AI drafting*). |
| **Pricing / technical volume assumptions** | `BidConfidence` and “requirement coverage” for **bid** artifacts (`app/services/scoring/bid_confidence_service.py` lines 1–2, 40–49). | Grant packages emphasize **narratives, budgets (separate forms), assurances** (`domain/federal-forms.md` — *Forms to support*). |
| **Contract status fields** | `contract_pipeline` / contract-specific outcome reasons (e.g. `outcome_reason` in models—used in tests). | Grant stages differ (`domain/grant-lifecycle.md` — *Twelve stages*). |
| **“Contract” forms** | `RequiredForm.supported_for_autofill` disabled in schema (`app/services/response_engine/schemas.py` lines 71–74). | NativeForge M0 still requires **SF-424 preview** from profile (`domain/federal-forms.md` — *M0 supports SF-424 preview only*). |
| **Past performance in vendor/bid sense** | `bid_confidence` “past performance alignment” component (`app/services/scoring/bid_confidence_service.py` lines 25–28). | NativeForge *can* reuse **narrative** past performance from profile (`domain/entity-profile-schema.md` — *Organizational capacity narratives*), not **federal vendor award stats** as primary. |
| **Procurement-specific scoring** | `pwin_service` / `time_to_bid_service` / `competitor_stats` / `federal_incumbency_cache` (file names and `app/db/models.py` 1060+). | **PWin** and “time to **bid**” are contract metaphors; NativeForge **win likelihood** is defined differently (`domain/scoring-model.md` — *Win Likelihood*). |

---

## 4. Current schema risk review

**Legend:** *reuse as-is* / *reuse with abstraction* / *reference, do not modify* / *ContractForge-only* / *dangerous to reuse* / *unclear*

| Table / group | Verdict | Why |
| --- | --- | --- |
| `organizations`, `users`, `tenant_invitations` | **Reuse as-is** | Clean tenancy (`app/db/models.py` lines 32–98). Add product flags in a **separate** design step—not mutating ContractForge invariants. |
| `organization_profiles` | **Dangerous to reuse** (as tribal profile) | **NAICS, capabilities, max_contract_size** are **contract vendor** fields (`app/db/models.py` lines 101–125). `domain/entity-profile-schema.md` — *Legal identity* / *Certifications* require a **tribal grant** shape. |
| `contracts` | **ContractForge-only** (for NativeForge domain) | Explicitly **federal contract** + procurement columns (`app/db/models.py` lines 261–315). |
| `org_contract_scoring` | **Dangerous to reuse** | **PWin, draft_readiness, bid_recommendation** (`app/db/models.py` lines 624–662). Not the six grant dimensions (`domain/scoring-model.md`). |
| `contract_pipeline` / `pipeline_*` | **Unclear** | Good **pattern**, wrong **vocabulary** (see Qualification *bid*). Either **new** `nf_*_pipeline` or strict view-layer separation. |
| `generated_drafts` | **Reuse with abstraction** | Generic “markdown + review columns” **shape** (`app/db/models.py` lines 1205–1243); **draft_type** namespace is **contract** (`app/services/drafting/agent.py` 35–41). NativeForge needs **new types** or a **product discriminator**. |
| `response_plans` | **ContractForge-only** (for grant plans) | Tied to `contract_id` (`app/db/models.py` 1254–1271) and **contracting** prompts (`app/services/response_engine/prompts.py` 7–12). |
| `qualification_*` | **Unclear** | Inbox **pattern** is useful; **bid/no_bid** semantics (`app/db/models.py` 1371–1375) conflict with grant decisions. |
| `bid_artifacts` / `bid_confidence_scores` | **ContractForge-only** | Names and PRD ref to **bid** (`app/db/models.py` 719–789; `app/services/scoring/bid_confidence_service.py` 1–2). |
| `vendor_*`, `competitor_stats`, `federal_incumbency_cache` | **ContractForge-only** | Procurement intel (`app/db/models.py` 969+). |
| `llm_response_cache`, `prompt_versions` | **Reuse with abstraction** | **Cache and prompt snapshot** are portable (`app/db/models.py` 1146–1202). **Kind** and **prompt text** must be **grant**-specific. |
| `module_event_log` | **Reference, do not modify** (as BXI/bridge log) | May not meet **exportable org audit** alone (`domain/sovereignty-trust-framework.md` — *Audit logs*). |

---

## 5. Proposed shared “Forge” infrastructure layer (bounded)

**Name (proposal):** `forge_infra` (package) for **non-domain** code only: **config, DB session, Auth0/JWT dependencies, HTTP client utilities, object storage adapter, structlog helpers**.

**Include (examples from contract-iq):**

- `app/lib/tenant_auth.py` — `TenantContext` pattern (lines 58–77).  
- `app/config.py` — `Settings` pattern (lines 7–20).  
- `app/services/ai/anthropic_client.py` — single provider wrapper (imported across services).  
- `scripts/check_org_id_predicates.py` — **static** tenant query discipline.

**Exclude from “core”:**

- Anything importing **`Contract`**, **`OrgContractScoring`**, **`fit_score`**, **`bid_*`**.  
- **Response plan** and **drafting** packages until **prompts and schemas** are grant-specific forks.

**Naming conventions:** prefix new NativeForge tables/services **`nf_`** or schema **`nf`** **only** for domain tables (see Section 6)—**not** renaming ContractForge.

---

## 6. Proposed NativeForge-specific domain layer

Mapping requested concepts → **new table** vs **adapt** vs **view**.  
(*Aligned with `domain/nofo-extraction-schema.md`, `domain/entity-profile-schema.md`, `domain/federal-forms.md`, `domain/grant-lifecycle.md`.*)

| Concept | Recommendation | Rationale |
| --- | --- | --- |
| **nf_tribal_profiles** | **New table(s)** (or JSONB profile keyed by `org_id`) | `organization_profiles` is contract-shaped (`app/db/models.py` 101–125). Tribal fields live in `domain/entity-profile-schema.md` — *Legal identity* / *Authorized officials*. |
| **nf_grant_sparks** | **New table** | Must not overload `contracts` (`app/db/models.py` 261–262). |
| **nf_nofo_extractions** | **New table** (JSONB + confidence columns) | NOFO schema is grant-specific (`domain/nofo-extraction-schema.md` — *Every field has `_confidence`*). |
| **nf_spark_checklists** | **New table** or **materialized view** from extraction + overrides | Checklists are derived from NOFO + human edits (`domain/grant-lifecycle.md` — *Stage 6*). |
| **nf_sf424_previews** | **New table** or **versioned documents** | No SF-424 implementation in Python (`rg "SF-424|sf424|NOFO" …/*.py` → **no matches** in `/Users/home/Code/contract-iq`). `domain/federal-forms.md` — *SF-424 → entity profile field mapping*. |
| **nf_resolution_tracker** | **New table** | Stage 8 **M1** in lifecycle doc (`domain/grant-lifecycle.md` — *Stage 8 — Tribal resolution*); no equivalent in contract schema. |
| **nf_grant_scoring** | **New table** | Six dimensions + deterministic composite (`domain/scoring-model.md`) ≠ `org_contract_scoring` (`app/db/models.py` 614–662). |
| **nf_grant_narratives** | **New table** or **fork of `generated_drafts` with product discriminator** | Reusing rows **without** discriminator risks ContractForge UI/API coupling (`app/db/models.py` 1213–1218). Prefer **separate table** until review gates align. |
| **nf_compliance_events** | **New table** | Post-award path (`domain/grant-lifecycle.md` — *Stage 12*) absent from M0 pillars (`context/five-pillars.md` — *What this list deliberately omits*). |
| **nf_audit_events** (vs shared log) | **New table or extension** if `module_event_log` cannot satisfy export | Sovereignty framework expects auditable LLM and export (`domain/sovereignty-trust-framework.md` — *Audit logs*, *AI training policy*). **No `ai_runs` table** in contract-iq (`rg "ai_runs"` → **no matches**). |

---

## 7. Product workflow divergence

**ContractForge (code-grounded):**

1. **Ingest** federal **contract** opportunities into **`contracts`** (`app/db/models.py` 261–318).  
2. **Match** via **NAICS-weighted fit** (`app/services/scoring/fit_score.py` 19–80) + org profile NAICS list (`app/db/models.py` 107–109).  
3. **Score** PWin, priority, draft readiness, pursuit risk, **bid recommendation** on **`org_contract_scoring`** (`app/db/models.py` 624–662).  
4. **Response plan** JSON via **contracting** analyst prompt (`app/services/response_engine/prompts.py` 7–12); forms **not** autofilled (`app/services/response_engine/schemas.py` 71–74).  
5. **Draft** procurement memo types (`app/services/drafting/agent.py` 35–41).  
6. **“Form completion”** = bid artifact / bid confidence (`app/services/scoring/bid_confidence_service.py` 1–49)—not SF-424.

**NativeForge (brief-grounded):**

1. **Grant source ingestion** (`domain/grant-lifecycle.md` — *Stage 3*; `context/five-pillars.md` — *2. Grant Spark ingestion*).  
2. **Tribal eligibility** vs extracted NOFO (`domain/grant-lifecycle.md` — *Stage 4*).  
3. **NOFO extraction** (`domain/nofo-extraction-schema.md`).  
4. **Forms + checklist** (`domain/grant-lifecycle.md` — *Stage 6*; `domain/federal-forms.md`).  
5. **Resolution tracking** (lifecycle *Stage 8* — M1 in doc).  
6. **Grant narrative drafting** with guardrails (`context/guardrails-and-risks.md`).  
7. **Submission package** (lifecycle *Stage 11*).  
8. **Post-award compliance** (lifecycle *Stage 12* — later milestones).

**Overlap (true):** tenant isolation pattern; “opportunity row + org overlay + pipeline”; LLM for structured extraction *concept*; checklist UX; **deterministic** scoring *pattern* (`domain/scoring-model.md` — *The score is deterministic*).  
**Split (true):** anything keyed to **NAICS/bid/PWin/incumbent** vs **CFDA/eligibility/reporting burden/SF-424/resolution**.

---

## 8. AI pipeline divergence

| Area | Reuse from contract-iq? | Notes |
| --- | --- | --- |
| **NOFO extraction** | **Rewrite prompts + schema** | Response plan JSON is **contract** solicitation (`app/services/response_engine/prompts.py` 7–25). Target schema is **`domain/nofo-extraction-schema.md` — *Top-level structure***. |
| **Tribal eligibility** | **Rewrite** | No tribal eligibility model in codebase; profile is NAICS-first (`app/db/models.py` 107–109). |
| **Grant narrative drafting** | **Rewrite** | `DraftType` is procurement (`app/services/drafting/agent.py` 35–41). |
| **Culturally guarded drafting** | **Rewrite** | Guardrails exist in **research** (`context/guardrails-and-risks.md` — *AI guardrails*), not enforced in ContractForge prompts reviewed here (response plan explicitly avoids narrative submission — `app/services/response_engine/prompts.py` 13–14). |
| **Reporting burden scoring** | **Rewrite math + inputs** | Not a column in `org_contract_scoring` (`app/db/models.py` 614–662). Required in `domain/scoring-model.md` — *Reporting Burden*. |
| **SF-424 autofill** | **Greenfield in product** | **No** SF-424 code (`rg` no matches). Mapping from `domain/federal-forms.md` — *SF-424 → entity profile field mapping*. |
| **Human review gates** | **Partial pattern only** | Draft status uses **`get_tenant_read`** — any read role may advance to `accepted` (`app/api/drafts.py` 193–220). NativeForge needs **stricter** gates (`context/guardrails-and-risks.md` — *Never auto-submit*; `domain/sovereignty-trust-framework.md` — *Human approval required*). |

**Validators:** `app/services/response_engine/schemas.py` Pydantic models (lines 44–95) are **contract response plan** shapes—**not** NOFO extraction (`domain/nofo-extraction-schema.md`).

---

## 9. Form automation divergence

**ContractForge today:** “Forms” in the response plan are **checklist** items with **no autofill** in Phase 1 (`app/services/response_engine/schemas.py` 63–74). Prompts emphasize **contracting** (`app/services/response_engine/prompts.py` 7–12).

**NativeForge M0:** SF-424 **preview** from entity profile (`domain/federal-forms.md` — *M0 supports SF-424 preview only*; *PDF generation uses field-level mapping*).

**Conclusion:** There is **no** SF-424 engine in contract-iq (grep **no matches**). NativeForge needs a **separate form-mapping layer** (field dictionary → PDF renderer) even if it **reuses** generic “preview document” UI components from the frontend. The **response plan** path should **not** be mistaken for that layer.

---

## 10. Demo isolation and data sovereignty risk

**Existing `demo_mode`:** `DEMO_ORG_IDS` + quarantine of shared catalog rows (`app/lib/demo_mode.py` lines 28–42, 95–142). **Mechanically** strong for **ContractForge** demo rows tagged `cf_demo` / synthetic (`app/lib/demo_mode.py` lines 15–18).

**NativeForge-specific trust lens:** `domain/sovereignty-trust-framework.md` — *Full data export*, *Audit logs*, *No training on customer data*, *Human approval before submission*.

**Assessment:** **`demo_mode` is necessary but not sufficient** for NativeForge trust claims:

- **Export:** Not validated solely by `module_event_log` (`app/db/models.py` 202–222); framework expects broader export (**Section 6 / sovereignty doc**).  
- **AI training audit:** **`ai_runs` referenced in `domain/sovereignty-trust-framework.md` — *Recording every LLM call*** — **does not exist** in contract-iq (`rg "ai_runs"` → **no matches**).  
- **Submission gate:** ContractForge draft acceptance is **read-role-permissive** (`app/api/drafts.py` 193–220).

**Server-enforced before NativeForge demo data:**

1. **NativeForge demo org allowlist** distinct from or explicitly composed with `DEMO_ORG_IDS` (`app/config.py` 15–16 pattern).  
2. **No shared-table reads** of grant demo rows by non-demo orgs—mirror `quarantined_demo_catalog_sql()` **pattern** (`app/lib/demo_mode.py` 95–124).  
3. **Export + audit** endpoints scoped to **org** with tests—cannot be “marketing only” (`domain/sovereignty-trust-framework.md` — *What this means for M0*).

---

## 11. Permission and review-gate divergence

**Current roles:** `admin`, `member`, `capture_lead`, `proposal_manager`, `analyst` (`app/lib/tenant_auth.py` lines 34–41). **Write:** `admin` only (`lines 73–77`). **Draft acceptance:** `get_tenant_read` (`app/api/drafts.py` 200).

**Gaps vs NativeForge personas** (implied by `domain/entity-profile-schema.md` — *Authorized officials*; `context/guardrails-and-risks.md`):

| Persona | Sufficiency today | Change |
| --- | --- | --- |
| Tribal admin | Partial — “admin” maps, but **no** tribal-specific scopes | Explicit **role or permission matrix** for NF tables; optional **separation** of ContractForge admin vs NativeForge admin if both products active. |
| Grant manager | Roughly `proposal_manager` / `capture_lead` — **not** grant-named | **Rename in UX only** unless JWT claims extended. |
| Finance officer | **No** dedicated role | **New** role or fine-grained permission on budget/SF-424A paths (M1 per `domain/federal-forms.md`). |
| Program staff | `member` / `analyst` | May need **edit** on narratives without org admin — today **writes** need `admin` (`app/lib/tenant_auth.py` 73–77). |
| External consultant | **No** first-class “external” model | Invitations exist (`tenant_invitations`) but scope **differs** from consultant **limited** grant access. |
| Read-only council / reviewer | **Broken for strict review-only:** read roles can **accept drafts** (`app/api/drafts.py` 193–220) | **Separate** permission for `accepted` / submission-ready transitions. |
| Auditor | **No** auditor role | Add **read-all audit** within org; **no** PII expansion beyond org. |

---

## 12. What the prior audit (`audit-output.md`) underweighted

1. **Semantic collision:** Reusing **`contracts`** was flagged, but the **magnitude** of downstream coupling (**fit**, **PWin**, **bid**, **qualification bid/no_bid**) deserved explicit **“do not map grants → ContractForge vocabulary”** risk.  
2. **Scoring model substitution:** First audit listed `org_contract_scoring` as contract-specific but did not stress that **none** of the **six NativeForge dimensions** (`domain/scoring-model.md`) exist as columns today (`app/db/models.py` 614–662).  
3. **Forms:** Little emphasis that **SF-424 is absent from code** (only implied).  
4. **Review gates vs sovereignty doc:** Underplayed **`get_tenant_read`** on draft acceptance (`app/api/drafts.py` 193–220) vs `domain/sovereignty-trust-framework.md` — *Human approval required*.  
5. **Qualification OS:** “May reuse if lifecycle maps” was optimistic—**bid/no_bid** in model docstring (`app/db/models.py` 1371–1375) is **actively wrong language** for grants.  
6. **AI governance:** No mention that **`ai_runs`** from sovereignty framework **does not exist** in repo (`rg "ai_runs"` → **no matches**).

---

## 13. Recommended architecture decision

| Layer | Recommendation |
| --- | --- |
| **Share** | Tenancy (`tenant_auth`), DB session, settings, CI/static guards, attachment parsing **libraries**, Anthropic client **wrapper**, generic caching (`llm_response_cache` pattern — `app/db/models.py` 1146–1157). |
| **Fork internally (parallel tables)** | **All grant sparks, NOFO JSON, grant scoring, SF-424 previews, tribal profile**, compliance events—**do not** store in `contracts` / `org_contract_scoring` without a deliberate, reviewed mapping. |
| **Build native to NativeForge** | NOFO extraction prompts/schemas (`domain/nofo-extraction-schema.md`), six-dimension scoring (`domain/scoring-model.md`), SF-424 mapper (`domain/federal-forms.md`), sovereignty export/audit gap-fill (`domain/sovereignty-trust-framework.md`). |
| **Leave ContractForge-only** | `vendor_*`, `competitor_stats`, bid artifacts, procurement response engine **as shipped**, **unless** explicitly bridged for unrelated ops. |
| **Audit again before coding** | Exact **JWT claims** for split admin; **Alembic** strategy for parallel `nf_*` tables; **frontend** deployment (basename) if NativeForge ships same SPA host. |

---

## 14. First safe implementation boundary

**Criteria:** No reuse of ContractForge **domain** assumptions; preserve ContractForge behavior; includes tests.

**Recommended first change:**

1. **Introduce configuration + routing scaffold** for NativeForge that is **feature-flagged off by default** (same **pattern** as `demo_org_ids` — `app/config.py` lines 15–16): e.g. env allowlist `NATIVE_FORGE_ORG_IDS` / `NATIVE_FORGE_ENABLED` **without** attaching grant logic to `contracts`.  
2. **Register an empty or stub FastAPI router** for NativeForge paths (mirror `app/main.py` lines 81–95 include_router pattern) returning **404 or “not enabled”** until Sprint 0.  
3. **Tests:**  
   - Router does not alter ContractForge routes (smoke).  
   - When flag off, **no** new behavior for existing org endpoints.  
   - (Optional) mirror **`tests/test_tenant_isolation_smoke.py`** pattern for any new path prefix.

**Explicit non-goals for this boundary:** No writes to `contracts`; no scoring reuse; no SF-424 PDF.

---

## 15. Open questions for the human

1. **Single org, both products:** Can one `organizations` row use **both** ContractForge and NativeForge concurrently, or **mutually exclusive** product binding? (Affects FK choices for `nf_*` tables.)  
2. **JWT issuer:** Same Auth0 app with extra claims vs separate audience—**not** decidable from SQLAlchemy alone (`app/lib/tenant_auth.py`).  
3. **Consultant access model:** Federated identity, magic links, or seat-based **inside** org—no first-class model in codebase (`tenant_invitations` only gets partway).  
4. **Council reviewer:** Legal expectation of **read-only** vs **approve** — requires policy input beyond code (`app/api/drafts.py` 193–220 shows technical gap).  
5. **M0 vs M1 boundary:** `domain/grant-lifecycle.md` places **resolution tracker** in **M1** (*Stage 8 — M1*)—confirm engineering starts **without** resolution tables in M0.  
6. **`module_event_log` vs audit export:** Is operational module logging enough for **tribal audit**, or is a **new** `nf_audit_events` mandatory for pilots (`domain/sovereignty-trust-framework.md` — *Audit logs retained*)?

---

*End of divergence audit. No files under `/Users/home/Code/contract-iq` were modified.*
