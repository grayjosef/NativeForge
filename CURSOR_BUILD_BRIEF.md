# Cursor Build Brief

You are Cursor. You are working on **NativeForge**, a sovereignty-first tribal grant pursuit and compliance platform in a **standalone product repository**.

This file is your entry point. Read it once, then follow the order it gives you.

## Binding stack (sources of truth)

These documents override older notes elsewhere in the repo when anything conflicts:

1. **`README.md`** — repo layout, how to run the app, where application code lives.
2. **`nativeforge-separate-repo-architecture-decision.md`** — separate product; no shared ContractForge database or runtime.
3. **`research/execution/*`** — audit prompt (historical), architecture boundary, demo isolation (Sprint 0), M0 sprint plan.
4. **`research/domain/*`** — personas, lifecycle, schemas, scoring, forms, sovereignty, sources, etc.
5. **`research/context/*`** — thesis, M0 narrative, pillars, guardrails, operating principles.
6. **`research/validation/*`** — definition of done, checklists, human validation planning.
7. **`nativeforge-scaffold-execution-plan.md`** — scaffold and ticket-style sequencing for this codebase.

### DB-backed org context (`nf_*` routes)

- **`organizations.org_type`** is **authoritative** for real vs demo on **product** routes that touch `nf_*` data.
- **`NF_DEMO_ORG_IDS`** is **legacy/smoke-test only** (`/v1/isolation/*`); do **not** use it for new `nf_*` features.
- New routes must use the DB-backed dependency path that applies **`apply_org_rls_gucs()`** on Postgres; access **`nf_*`** only via **repositories/services**.
- Full rules: **`docs/nativeforge-db-context-rules.md`**.

**ContractForge** (`contract-iq` or similar) may be used **only** as **architectural inspiration or prior-art** when reading patterns (auth shapes, job patterns). It is **not** a dependency, submodule, or shared database. There is **no** in-place extension of ContractForge in this repository.

### NativeForge-native domain language

Do **not** model the product on federal contracting vocabulary or ContractForge table names. Use:

| Use this (NativeForge) | Not this (contracting / ContractForge) |
|------------------------|------------------------------------------|
| Sparks (grant opportunities) | Contracts |
| Grant pursuits / pursuit pipeline | Bids |
| NOFOs / assistance listings | Solicitations |
| Entity (tribal) profiles | Vendor / capability profiles |
| Tribal eligibility and fit scoring | Contract / NAICS scoring |
| `nf_*` tables and grant-native rows | `contracts`, `org_contract_scoring`, or other ContractForge runtime tables |

Implementation uses **first-class NativeForge concepts** and the **`nf_*` namespace** (see `research/execution/02-architecture-boundary.md` and `nativeforge-separate-repo-architecture-decision.md`).

### Canonical product and business sources

- **`research/source/nativeforge-product-intelligence-report.md`** — strategy, market gap, personas, lifecycle, sources, forms, scoring, sovereignty, M0–M3 scope.
- **`research/source/nativeforge-revenue-model.md`** — tiers, unit economics, procurement, projections.

Where the product-intelligence report and the revenue model overlap (e.g., pricing, deployment), **`research/source/nativeforge-revenue-model.md` wins.**

The domain files (`research/domain/*.md`) are working references per sprint. Do not load all of them at once.

**The revenue model’s five tiers (Core / Pro / Enterprise / Sovereignty / Consortium) have build implications even when M0 bills nothing.** In particular:

- **Sovereignty** (private/dedicated cloud, M3) must remain feasible without a tenant-isolation rewrite. Follow `research/execution/03-demo-isolation-spec.md`.
- **Consortium** (one buyer, multiple member tribes) implies a future one-to-many relationship. M0 may use one org ↔ one tribal profile, but avoid schema choices that block consortium later.
- **License vs. SaaS** enforcement is **M3**, not M0. Do not build license-key or subscription metering in M0.

## Your job

Work **in this repository only**, using NativeForge tables and APIs. Produce, in order:

1. **Architecture and M0 data design** — Align implementation with `nativeforge-separate-repo-architecture-decision.md` and complete the schema-oriented sections of **`research/execution/02-architecture-boundary.md`** for **`nf_*`** grant-native storage (not shared ContractForge tables). Root-level **`audit-output.md`** is **archived prior-art** from a ContractForge audit; use it for pattern context if helpful. A fresh audit of another repo is **optional** and does not block this codebase.
2. **Human sign-off** — Pause for review where **`02-architecture-boundary.md`** requires answers (e.g., section 5 sign-off questions). Do not silently assume shared-database or monorepo options.
3. **Sprint 0 (required before feature sprints)** — **`research/execution/03-demo-isolation-spec.md`**: demo isolation plus review-gate state machine, implemented, tested, and merged. **M0 engineering starts here:** no Sprints 1–7 until Sprint 0 acceptance criteria and CI gates are satisfied.
4. **Sprints 1–7 (M0)** — **`research/execution/04-m0-implementation-plan.md`**: tribal profile, Spark ingestion, NOFO summary + extraction, scoring, pipeline + tasks, SF-424 preview, sovereignty page + export — in order, without parallelizing sprints.

Stop and hand control back to the human after architecture sign-off, after Sprint 0, and after M0 if that is your working agreement. Do not auto-advance through gates.

## Read order (before deep implementation)

Paths are under **`research/`** in this repo:

1. **`research/context/operating-principles.md`** — rules; violations block merge.
2. **`research/context/product-thesis.md`** — one-page why.
3. **`research/context/m0-demo-narrative.md`** — end-to-end demo.
4. **`research/context/five-pillars.md`** — in scope / out of scope.
5. **`research/context/guardrails-and-risks.md`** — non-negotiables.
6. **`research/execution/README.md`** — execution document sequence.
7. **`research/execution/01-audit-prompt.md`** — **optional**; describes a historical ContractForge audit workflow. This repo does **not** implement NativeForge inside ContractForge.

## Step 1 — Architecture boundary (not a ContractForge code audit)

Fill in **`research/execution/02-architecture-boundary.md`** for the **standalone NativeForge product**: `nf_*` schema, isolation, and coexistence rules **without** relying on ContractForge runtime tables. If the document still lists monorepo options (A/B/C), the **effective decision for this repository** is documented in **`nativeforge-separate-repo-architecture-decision.md`** — a **separate repo**, separate database, grant-native model.

When the architecture sections are updated, **stop** for human sign-off on open questions before Sprint 0 unless your team agrees otherwise.

## Step 2 — Sprint 0 (demo isolation + review gate)

After architecture is acceptable, implement Sprint 0 per **`research/execution/03-demo-isolation-spec.md`**.

All acceptance criteria at the bottom of that document must pass. CI must show demo-isolation tests passing on the main branch before **Sprints 1–7**.

When Sprint 0 is done, **stop** until the human confirms merge.

## Step 3 — Sprints 1–7 (M0 build)

Open **`research/execution/04-m0-implementation-plan.md`**. Execute the sprint sequence in order.

For every PR, run **`research/validation/definition-of-done.md`**.

When the M0 validation gate at the bottom of `04-m0-implementation-plan.md` is satisfied, declare M0 done and hand off for the buyer demo.

## What you do not do

- Do **not** depend on ContractForge at runtime (no shared DB, no imported ContractForge services).
- Do **not** implement NativeForge as rows in `contracts`, `org_contract_scoring`, or other ContractForge tables.
- Do **not** write application code in the architecture-doc phase beyond what the team explicitly allows.
- Do **not** commit secrets or touch production secrets.
- Do **not** create demo data in real orgs.
- Do **not** skip review gates or auto-submit to Grants.gov.
- Do **not** edit **`research/context/operating-principles.md`** without explicit owner approval.
- Do **not** silently violate an operating principle; surface conflicts and ask.

## How to report

After each milestone, record a short status update (PR description or updates to the relevant execution doc): what changed, tests, principles touched, open questions. Prefer the durable record over chat alone.

## When you are stuck

- If **`research/execution/*`** still mentions shared ContractForge tables, resolve implementation using **`nativeforge-separate-repo-architecture-decision.md`** and ask the human whether to refresh those execution docs.
- If a guardrail in **`research/context/guardrails-and-risks.md`** blocks a demo feature, raise it; do not bypass it.
- If a **`research/validation/definition-of-done`** item cannot be met, call it out, propose a follow-up, and get explicit approval for the gap.

## The mission, restated

NativeForge is viable; the wedge is real. In this repo, speed and trust come from a **clean grant-native model**, **tenant and demo isolation first**, and **sovereignty-respecting defaults** — not from wiring into ContractForge’s production schema.

Build the walls around the launchpad first. Then build the rocket.

## HITP Commit Gate

All future NativeForge work requires the hard Human-in-the-Pipeline commit gate defined in `docs/HITP_COMMIT_GATE.md`.

No agent may commit automatically. Backend validation, frontend validation, migration status, diff stat, known risks, and intentionally untested items must be shown before commit approval. The agent must stop and wait for one of the valid approval phrases before running `git commit`.

No commit may be made based only on backend tests.

Before requesting commit approval, run **`bash scripts/nativeforge_full_validation.sh`** (see **`docs/HITP_COMMIT_GATE.md`**).
