# NativeForge scaffold execution plan

**Purpose:** Define the **first implementation sequence** for NativeForge as a **separate repository and product**, using ContractForge (`/Users/home/Code/contract-iq`) **only** as a read-only architecture donor (`nativeforge-separate-repo-architecture-decision.md`).

**Hard rule:** **Do not** add NativeForge into `contract-iq`. **Do not** mount NativeForge routes, `nf_*` tables, or feature flags inside ContractForge. ContractForge stays untouched.

**Inputs:** `context/operating-principles.md`, `validation/definition-of-done.md`, `domain/entity-profile-schema.md`, `domain/nofo-extraction-schema.md`, `domain/scoring-model.md`.

---

## 1. Repo scaffold recommendation

- **New Git repository** (name per captain; e.g. `nativeforge` / `native-forge-app`) — **not** a subdirectory of `contract-iq`.
- **Root layout:** single backend package + optional `frontend/` (or `apps/web/`) in the same repo for M0; monorepo acceptable; **polyrepo** acceptable if the captain prefers separate UI repo later.
- **Tooling:** Python **uv** or **pip** + lockfile (mirror ContractForge discipline); Node **npm** + lockfile for frontend (ContractForge uses Vite + React — `contract-iq/frontend/package.json` as donor pattern).
- **Environment:** `.env.example` only — **no secrets** (`context/operating-principles.md` — *Do not commit secrets*).
- **License / attribution:** `NOTICE` or `THIRD_PARTY` listing adapted donor files from ContractForge when copied (`nativeforge-separate-repo-architecture-decision.md` — §6).
- **CI skeleton:** GitHub Actions (or equivalent) with placeholder jobs to be filled in Step 0 — pattern from `contract-iq/.github/workflows/ci.yml` (*study only*).

---

## 2. Backend stack recommendation (ContractForge donor patterns)

| Layer | Recommendation | Donor reference |
| --- | --- | --- |
| **Framework** | **FastAPI** | `contract-iq/app/main.py` |
| **ASGI** | uvicorn (dev) / gunicorn+uvicorn workers (prod) — standard FastAPI deployment | industry default matching donor |
| **ORM** | **SQLAlchemy 2.x** + Alembic migrations | `contract-iq/app/db/` |
| **DB driver** | **psycopg** (PostgreSQL) | `contract-iq/app/config.py` `DATABASE_URL` pattern |
| **Settings** | **pydantic-settings** env loading | `contract-iq/app/config.py` lines 7–20 |
| **Auth** | JWT bearer validation + org path param; NativeForge claim namespace (**not** `https://contractiq/…`) | `contract-iq/app/lib/tenant_auth.py` — **copy structure, adapt** |
| **Lint / format** | **ruff** | `contract-iq` CI |
| **HTTP client** | httpx (for future Grants.gov / SAM) | align when ingestion ships |

---

## 3. Frontend stack recommendation (ContractForge UI donor patterns)

| Choice | Recommendation | Donor reference |
| --- | --- | --- |
| **Bundler** | **Vite** | `contract-iq/frontend/vite.config.ts` |
| **UI library** | **React** (version aligned to team standard; donor uses React 19) | `contract-iq/frontend/package.json` |
| **Routing** | **React Router** | `contract-iq/frontend/src/operator/App.tsx` patterns |
| **Data** | TanStack Query (optional M0; donor uses it) | `contract-iq/frontend/package.json` |
| **Styling** | Team choice (donor uses Radix + Tailwind-style utilities — follow NativeForge design system) | study `contract-iq/frontend/src/operator/` |

**Routes:** Grant-native paths (e.g. `/sparks`, `/pipeline`) — **not** `/contracts/…` (`nativeforge-separate-repo-architecture-decision.md` §5).

---

## 4. Database / schema setup recommendation

- **Separate PostgreSQL instance/database** from ContractForge — **never** shared DB for M0.
- **Alembic** revision chain **only** in NativeForge repo.
- **Naming:** grant-native tables (`nf_tribal_profiles`, `nf_grant_sparks`, …) per `nativeforge-separate-repo-architecture-decision.md` §7.
- **`validation/definition-of-done.md` expectations** (adapt when implementing):
  - New `nf_*` tables: **`is_demo`**, **FK to `organizations`**, trigger alignment where spec requires (*Demo isolation* section).
  - **RLS** enabled with org-scope and demo-scope policies when Postgres is the target (*Postgres only* in definition-of-done).
- **`nf_ai_runs`** (or `ai_runs` per repo naming): record LLM calls per `domain/nofo-extraction-schema.md` — *Implementation notes for M0* (*recorded in `ai_runs`*) and `validation/definition-of-done.md` — *Any new AI call is recorded in `ai_runs`*.
- **No** tables named `contracts`, `org_contract_scoring`, `bid_*` in NativeForge.

---

## 5. Initial folder structure (proposal)

NativeForge repository (illustrative):

```
nativeforge/
  README.md
  LICENSE
  NOTICE                    # third-party / donor lineage
  .env.example
  pyproject.toml             # or requirements + uv.lock
  alembic.ini
  alembic/versions/
  src/
    nativeforge/             # or app/ — pick one convention early
      __init__.py
      main.py                # FastAPI factory
      api/
        health.py
        deps.py              # get_db, auth dependencies
      lib/
        auth.py              # adapted from donor tenant_auth pattern
        settings.py
      db/
        base.py
        session.py
        models/              # nf_* SQLAlchemy models
      services/              # use cases (thin in early steps)
  scripts/
    check_org_scope.py       # adapted from donor check_org_id_predicates idea
  tests/
    conftest.py
  frontend/                  # if monorepo
    package.json
    src/
  .github/workflows/ci.yml
```

Adjust names to match the captain’s Python package naming (`nativeforge` vs `app`).

---

## 6. Copy / adapt candidates from contract-iq

Per `nativeforge-separate-repo-architecture-decision.md` §3 (Architecture Donor Map) and §6:

| Source (contract-iq) | Action |
| --- | --- |
| `app/lib/tenant_auth.py` | **Copy → heavily adapt** (claims, namespaces, tests) |
| `app/config.py` | **Copy → adapt** (`Settings` fields for NativeForge) |
| `app/services/ai/anthropic_client.py` | **Copy → adapt** |
| `app/services/ingestion/attachment_parser.py` | **Copy → adapt** (NOFO PDF limits) |
| `scripts/check_org_id_predicates.py` | **Copy → adapt** → `scripts/check_org_scope.py` targeting `nf_*` ORM |
| `.github/workflows/ci.yml` | **Study → replicate** ruff + pytest + guards |

---

## 7. Reference-only modules from contract-iq

**Read for ideas; do not paste domain logic:**

| Source | Why reference-only |
| --- | --- |
| `app/services/scoring/fit_score.py` | NAICS-weighted — **reject math** for NativeForge (`nativeforge-separate-repo-architecture-decision.md` §4) |
| `app/services/response_engine/builder.py` | Orchestration-only ideas; NOFO prompts differ (`domain/nofo-extraction-schema.md`) |
| `app/db/models.py` | Timestamp/JSONB idioms; **never** copy `Contract` / `OrgContractScoring` |
| `app/lib/demo_mode.py` | Quarantine **pattern** for demo Sparks (`nativeforge-separate-repo-architecture-decision.md` §3) |
| `frontend/src/operator/` | Layout/list/detail **patterns**, not routes or strings |

---

## 8. Blocked ContractForge concepts (must not copy)

Explicit ban list (`nativeforge-separate-repo-architecture-decision.md` §4):

- `contracts` table semantics; `incumbent`, `likely_competitors`, procurement columns (`contract-iq/app/db/models.py` lines 261–315).
- `org_contract_scoring`; `pwin_*`, `bid_recommendation`, `draft_readiness` as grant scoring (`app/db/models.py` lines 624–662).
- `fit_score.py` NAICS-first weighting (`app/services/scoring/fit_score.py` lines 19–80).
- Qualification **bid / no_bid** vocabulary (`app/db/models.py` lines 1371–1375).
- Response plan **contracting** prompts (`app/services/response_engine/prompts.py` lines 7–25).
- `DraftType` procurement memos (`app/services/drafting/agent.py` lines 35–41).
- `BidArtifact` / `BidConfidence` paths (`app/db/models.py` lines 719–789).

---

## 9. Step 0 implementation ticket: create scaffold

**Title:** `NF-000 — Repository scaffold (backend + CI + frontend shell)`

**Goal:** Runnable empty product in the **NativeForge repo** only.

**Tasks:**

1. Initialize repo structure (§5); Python package; FastAPI `GET /health`.
2. Wire **settings** from env; document in `.env.example`.
3. Add **database session** module stub (can point at local Postgres or skip connect in CI with SQLite **only** if team accepts divergence — default **Postgres** to match DoD RLS path).
4. Add **Alembic** with empty baseline or first revision placeholder (no domain migrations yet if captain wants Step 2+ for first migration — acceptable either way if **no `nf_*` schema** until Step 1–2).
5. Copy-adapt **Anthropic client** stub **or** defer client to Step 5 — **no production secrets**.
6. Add **ruff** + **pytest** + CI workflow mirroring donor CI **shape**.
7. Scaffold **frontend** with Vite + React; single page “NativeForge” placeholder.
8. **README:** explicit statement that ContractForge is **not** a dependency and **not** modified.

**Acceptance criteria:**

- `pytest` passes (health test).
- CI green on PR.
- No secrets in repo.
- **Zero files changed** under `/Users/home/Code/contract-iq`.

**Operating principles:** *Validate after each small change*; *Do not commit secrets* (`context/operating-principles.md`).

---

## 10. Step 1 implementation ticket: demo isolation and fake-data rules

**Title:** `NF-001 — Demo org allowlist + quarantine + CI guards`

**Goal:** Meet **demo isolation** spine before real domain data (`context/operating-principles.md` — *Do not create demo data in real orgs*; `validation/definition-of-done.md` — *Demo isolation* section).

**Tasks:**

1. **Env:** `DEMO_ORG_IDS` (or NativeForge-specific name) — comma-separated UUIDs — pattern from donor `app/config.py` / `app/lib/demo_mode.py` (**adapt**, do not import).
2. **Rules:** Define **demo Spark** tagging (e.g. `nf_demo` tag + external id prefixes) and **SQL predicates** excluding demo rows for non-demo orgs — **conceptual copy** of `quarantined_demo_catalog_sql()` (`contract-iq/app/lib/demo_mode.py` lines 95–142).
3. **Middleware / dependency:** Reject or filter demo data for non-demo orgs on list endpoints (stub routes OK).
4. **Tests:** At least one test proving **non-demo org cannot list demo Sparks** (when Spark table exists, extend; until then test predicate helpers).
5. **Adapt** `scripts/check_org_id_predicates.py` → NativeForge `nf_*` query guard (`nativeforge-separate-repo-architecture-decision.md` §3).
6. Align with **`execution/03-demo-isolation-spec.md`** when that document is the sprint source of truth for **7 CI tests** referenced in `validation/definition-of-done.md`.

**Acceptance criteria:**

- Demo isolation checklist items **progress** toward DoD (full **7 tests** may land when spec is wired).
- No demo fixtures loaded into “real” org paths in tests.

---

## 11. Step 2 implementation ticket: tribal profile

**Title:** `NF-002 — nf_tribal_profiles + CRUD + audit + export stub`

**Goal:** Persist **sovereignty-first profile** per `domain/entity-profile-schema.md`.

**Tasks:**

1. **Schema:** All **sections** listed: Legal identity, Location, Authorized officials, Financial, Certifications, Narratives (*Sections of the profile*).
2. **API:** Org-scoped read/write (path or header org id per NativeForge auth design).
3. **Audit:** Profile edits append **`nf_audit_events`** (or equivalent) — *Audit log records every change* (`domain/entity-profile-schema.md` — *Data sovereignty considerations*).
4. **Export:** `GET` JSON export **requesting org only** — *Export endpoint returns the full profile as JSON* (*M0 acceptance for the profile*).
5. **Warnings not blocks** for incomplete profile where schema calls for it — *Profile completeness gating* (`domain/entity-profile-schema.md`).
6. **Tests:** Org isolation; export excludes other orgs; audit entries on update.

**Acceptance criteria:**

- Matches **M0 acceptance** bullets in `domain/entity-profile-schema.md` — *M0 acceptance for the profile* (database fields, wizard can follow in UI later).
- `validation/definition-of-done.md` — *Any new data export endpoint returns only the requesting org's data. Tested.*

---

## 12. Step 3 implementation ticket: grant spark model

**Title:** `NF-003 — nf_grant_sparks + seeded demo data + list/detail API`

**Goal:** Grant-native opportunity rows; seed **M0 demo Sparks** (`context/five-pillars.md` — *12 demo Sparks*; hand-verified extraction per `domain/nofo-extraction-schema.md` — *Implementation notes for M0*).

**Tasks:**

1. **Table(s):** `nf_grant_sparks` with source, external id, title, agency, deadlines, raw refs; **JSONB** `extracted` per *Top-level structure* (`domain/nofo-extraction-schema.md`) for seeded content.
2. **Seed path:** Loader runs **only** in demo org context or via explicit test fixtures — *fake data must be demo-scoped* (`context/operating-principles.md`).
3. **API:** List + detail filtered by **demo isolation** rules from Step 1.
4. **Optional projection:** stub `nf_spark_requirements` or checklist table per *denormalized projection* (*Implementation notes for M0* in `domain/nofo-extraction-schema.md`) — can be **NF-003 stretch** or follow-on ticket.

**Acceptance criteria:**

- Demo Sparks **never** returned for non-demo orgs in tests.
- No ContractForge `contracts` table or naming in NativeForge schema.

---

## 13. Test / validation commands

**Local (backend):**

```bash
ruff check src tests
ruff format --check src tests
pytest -q
```

**Org-scope guard (when script exists):**

```bash
python scripts/check_org_scope.py
```

**Frontend (when present):**

```bash
cd frontend && npm ci && npm run typecheck && npm test && npm run build
```

**CI:** Mirror commands in pipeline; fail on secrets (pre-commit or `grep` for keys per `validation/definition-of-done.md`).

---

## 14. Definition of done (for scaffold through Step 3)

Use **`validation/definition-of-done.md`** with these **NativeForge repo interpretations:**

| DoD item | Application |
| --- | --- |
| **ContractForge regression** | **N/A** — NativeForge repo contains **no** ContractForge code. **Done** means: **no PR touches `contract-iq`**; ContractForge CI unchanged because untouched. |
| **Tests / lint / frontend** | Apply fully. |
| **Demo isolation** | Apply — align with `execution/03-demo-isolation-spec.md` as it lands. |
| **`ai_runs`** | Required once LLM calls exist (Step 5+); Step 0–3 may have **no** AI calls yet — **document exception** in PR if true (`validation/definition-of-done.md` — *Escalation*). |
| **RLS** | Apply when `nf_*` tables exist on Postgres per DoD. |

**Operating principles:** *Scoped imports* — NativeForge never imports ContractForge (`context/operating-principles.md` — *Scoped imports* applies to **runtime**; donor copy is **forked code**, not a package dependency).

---

## 15. Risks and open questions

**Risks**

| Risk | Mitigation |
| --- | --- |
| Accidental copy-paste of ContractForge **domain** types | PR checklist + grep ban (`Contract`, `OrgContractScoring`, `bid_recommendation`) per §8. |
| Demo data leaks before isolation is solid | Step **1** before bulk Step **3** seeds (`context/operating-principles.md`). |
| `definition-of-done.md` references shared components with ContractForge | Treat as **historical monorepo** wording; **separate repo** satisfies spirit by **non-modification**. |
| RLS complexity slows scaffold | Timebox Step 1; escalate per DoD *Escalation* if RLS slips one PR with signed follow-up. |

**Open questions (blocking)**

1. **Auth0 / JWT:** Final claim namespace and audiences for NativeForge-only deployment (`nativeforge-separate-repo-architecture-decision.md` §10).
2. **Single repo vs UI repo:** Confirm monorepo for M0 or split frontend repository.
3. **`execution/02-architecture-boundary.md` / `03-demo-isolation-spec.md`:** Some checklist items (e.g. **7 CI tests**, triggers) — confirm these docs are finalized before implementing Step 1 to avoid rework.

---

**Stop:** This plan is documentation only. **No code**, **no migrations**, **no commits**, **no changes** to `/Users/home/Code/contract-iq`.
