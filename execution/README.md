# execution/

This folder contains the four documents Cursor executes against, in order. Nothing else in this repo is "what to do." Everything else is reference material.

## Read order

1. **`01-audit-prompt.md`** — Cursor's first action. Audit the existing ContractForge codebase. Produce a written report. **Do not implement anything.**
2. **`02-architecture-boundary.md`** — After the audit returns, decide between fork / module / shared-core / product-surface. Includes the schema proposal as one section. **Do not implement anything.**
3. **`03-demo-isolation-spec.md`** — Sprint 0. Build the walls around the launchpad. Layered enforcement: tenant + flag + middleware + query filters + DB constraints + CI tests. **This is the first code that gets written.**
4. **`04-m0-implementation-plan.md`** — Everything after Sprint 0. Tribal profile, grant Spark, scoring, autofill, pipeline, sovereignty page. Sequenced, with risks.

## The rule

You cannot skip `01` and `02`. The schema and M0 plan are guesses without the audit. The architecture-boundary decision determines the shape of every subsequent file you write.

## What "done" means

See `../validation/definition-of-done.md`. Every unit of work in `04` must satisfy that checklist before it counts as done.

## What this folder is not

- It is not the build. The build lives in the ContractForge repo (or a derived repo, depending on the `02` decision).
- It is not exhaustive. It contains only the four documents needed to get from "report in hand" to "M0 demo working."
- It is not stable. Once `02` is decided, this folder gets revised. Treat the architecture-boundary doc as the spine that everything else will be re-examined against.
