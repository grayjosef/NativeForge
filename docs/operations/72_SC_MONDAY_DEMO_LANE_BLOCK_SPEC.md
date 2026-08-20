# NF SC Monday Demo Lane — Block Spec (Sprint 001)

## Block

**NF SC Monday Demo Lane — Curated-Current Opportunities + Guided Customer Story**

## Objective

Honestly labeled SC customer demo: org profiles + curated SC/federal opportunities + eligibility explainability. No live ingest claim. No source activation. No fabricated eligibility.

## Data labels (required on every opportunity)

| Label | Meaning |
|-------|---------|
| `curated_current` | Operator-curated from known sources; capture date recorded; not automated live ingest |
| `fixture_demo` | From offline fixtures/corpus; demo/dev only |
| `rule_reference` | Derived from SC eligibility rules categories (not a live listing) |
| `live_ingest_not_claimed` | Always true for this pack — automated live ingestion is **not** claimed |

## Route

`/?view=sc_customer_demo`

## Out of scope

Live activation, migrations, scoring math changes, LLM drafting, mass ruff, push, stash, `uv.lock`.
