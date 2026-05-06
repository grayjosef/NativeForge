# NativeForge Research Repo

Pre-build research, discovery, and execution-planning package for **NativeForge** — a sovereignty-first tribal grant pursuit and compliance platform. **ContractForge (`contract-iq`) is read-only reference architecture only** — NativeForge application code lives **here** under `src/nativeforge/` (separate product codebase per `nativeforge-separate-repo-architecture-decision.md`).

## Application code (NF-000 scaffold)

The backend is a **FastAPI** app with **SQLAlchemy**, **Alembic**, **psycopg**, and **pydantic-settings**. ContractForge is **not** modified and **not** a runtime dependency.

### Prerequisites

- Python **3.11+**
- **PostgreSQL** (optional for `GET /health` only; required for Alembic against a real DB when you add migrations with DDL)

### M0 buyer / operator demo (checklist)

Step-by-step startup, env vars, seed orgs, `/health`, `/docs`, trust manifest, and buyer talk track: **[`docs/m0-demo-operator-checklist.md`](docs/m0-demo-operator-checklist.md)**. For the **browser demo**, use a **file-backed** `DATABASE_URL` (not the default in-memory SQLite) so Alembic, seed, and `uvicorn` share one database — see the checklist warning and bootstrap sequence.

### Local backend setup

```bash
cd /path/to/NativeForge
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env        # edit DATABASE_URL if needed
uvicorn nativeforge.main:app --reload
```

- Health check: `GET http://127.0.0.1:8000/health`

### Backend validation

```bash
ruff check src tests && ruff format --check src tests
pytest -q
python scripts/check_nf_sql_grep.py
```

**Demo isolation (NF-001):** configuration (`NF_DEMO_ORG_IDS`, `NF_DEV_ORG_HEADERS`), helpers, and `/v1/isolation/*` smoke routes are documented in [`docs/demo-isolation.md`](docs/demo-isolation.md). Quick subset:

```bash
bash scripts/validate_demo_isolation.sh
```

### Frontend (placeholder shell)

```bash
cd frontend
npm ci
npm run dev                 # http://127.0.0.1:5173
npm run build
```

### Alembic

```bash
pip install -e ".[dev]"
alembic upgrade head        # applies empty initial revision when metadata has no tables
alembic history
```

---

## Research & execution docs (original purpose)

This repository **also** holds research and execution documents that inform the build. Cursor (or any agent) consumes these before and during implementation.

## Who this is for

| Audience | Entry point |
|---|---|
| You (the human reviewer) | This README, then `execution/README.md` |
| Cursor (the build agent) | `CURSOR_BUILD_BRIEF.md` |
| A new collaborator | This README, then `context/product-thesis.md`, then `source/` |
| Tribal advisor / consultant reviewing the approach | `domain/sovereignty-trust-framework.md`, `context/guardrails-and-risks.md`, `validation/interview-plan.md` |

## Layout

```
nativeforge-research/
├── README.md                          ← you are here
├── CURSOR_BUILD_BRIEF.md              ← Cursor's entry point
│
├── source/                            ← canonical source-of-truth reports
│   ├── nativeforge-product-intelligence-report.md   ← product strategy
│   └── nativeforge-revenue-model.md                 ← pricing, unit economics, monetization
│
├── execution/                         ← the four documents Cursor executes against, in order
│   ├── README.md
│   ├── 01-audit-prompt.md             ← Cursor's first action
│   ├── 02-architecture-boundary.md    ← surface decision (A/B/C) + schema
│   ├── 03-demo-isolation-spec.md      ← Sprint 0; layered enforcement
│   └── 04-m0-implementation-plan.md   ← M0 sprint sequence
│
├── context/                           ← short executive-level synthesis
│   ├── product-thesis.md              ← one-page why
│   ├── m0-demo-narrative.md           ← the money demo
│   ├── five-pillars.md                ← what's in scope and what isn't
│   ├── guardrails-and-risks.md        ← what cannot go wrong
│   └── operating-principles.md        ← rules Cursor must not break
│
├── domain/                            ← distilled reference material for the build
│   ├── personas.md
│   ├── grant-lifecycle.md
│   ├── grant-sources.md
│   ├── federal-forms.md
│   ├── entity-profile-schema.md
│   ├── nofo-extraction-schema.md
│   ├── scoring-model.md
│   ├── drafting-guardrails.md
│   ├── sovereignty-trust-framework.md
│   ├── competitive-landscape.md
│   └── pricing-and-tiers.md
│
└── validation/                        ← gates and standards
    ├── interview-plan.md
    ├── pre-coding-checklist.md
    └── definition-of-done.md
```

## How to use this repo

### If you are reviewing the approach

Read in this order:

1. `context/product-thesis.md` (one page)
2. `context/m0-demo-narrative.md` (one minute)
3. `context/five-pillars.md`
4. `execution/02-architecture-boundary.md` (the spine)
5. `execution/03-demo-isolation-spec.md` (Sprint 0)
6. `execution/04-m0-implementation-plan.md` (sprint sequence)

The two source reports in `source/` are ground truth — the product-intelligence report for any product or feature question, and the revenue-model report for any pricing, tier, or monetization question. Where they overlap on tier definitions or deployment models, the revenue model takes precedence.

### If you are Cursor

Read `CURSOR_BUILD_BRIEF.md`. Follow it.

### If you are starting tribal interviews

Read `validation/interview-plan.md`. The interview guide is in there. Compensate interviewees. Tribal cultural advisor reviews the guide before fieldwork.

## What this repo deliberately does NOT contain

- Code. The build lives elsewhere.
- Interview transcripts. Those go in a private project folder once interviews run.
- Tribal resolution templates, NOFO PDF samples, fillable SF-424 fixtures. Those are M1 artifacts and live in the build repo.
- A `.bib` citations file. The source report has full citations inline.
- An exhaustive 18-folder research structure. The source report's Section 19 proposes one; that's the long-term shape. This is the starter shape, focused on getting Cursor to ship M0.

## Status

This repo is created **before** the audit, **before** the architecture-boundary decision, **before** Sprint 0. Several files contain explicit placeholders that Cursor or the human fills in once the audit returns. Most notably:

- `execution/02-architecture-boundary.md` Section 1 has a `RECOMMENDATION (post-audit)` block.
- `execution/02-architecture-boundary.md` Section 5 has seven sign-off questions for the human.
- `validation/pre-coding-checklist.md` has six checkboxes that gate downstream work.

## Versioning

This is the v1 starter shape. Expect revisions:

- After the audit returns, the architecture-boundary doc gets filled in and may rewrite the schema section.
- After Sprint 0 ships, the demo-isolation spec gets a "what we actually built" appendix.
- After the first 5 tribal interviews, `domain/personas.md` and `domain/scoring-model.md` likely get sharpened.
- After the first paid pilot, expect a substantial rewrite of `validation/` and the addition of M1 sprint planning to `execution/`.

## License and use

Internal product strategy material. Not for external distribution.
