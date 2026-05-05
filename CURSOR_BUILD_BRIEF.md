# Cursor Build Brief

You are Cursor. You are working on NativeForge, a sovereignty-first tribal grant pursuit and compliance platform that extends the existing ContractForge engine.

This file is your entry point. Read it once, then follow the order it gives you.

## Your job

Take this research repo and the existing ContractForge codebase, and produce, in this order:

1. An **audit report** of the existing ContractForge codebase.
2. An **architecture-boundary decision** (A, B, or C) with a defended recommendation and the M0 schema proposal filled in.
3. **Sprint 0** — demo isolation + review-gate state machine — implemented, tested, and merged.
4. **Sprints 1–7** of M0 — tribal profile, Spark ingestion, NOFO summary + extraction, scoring, pipeline + tasks, SF-424 preview, sovereignty page + export — implemented, tested, and merged.

You stop and hand control back to the human after step 1, after step 2, and after Sprint 0. You do not auto-advance through gates.

## Read order (right now, before anything else)

1. **`context/operating-principles.md`** — the rules. Read these first. Every PR is reviewed against them. Violations block merge.
2. **`context/product-thesis.md`** — one-page why.
3. **`context/m0-demo-narrative.md`** — what the demo has to do, end to end.
4. **`context/five-pillars.md`** — what's in scope and what isn't.
5. **`context/guardrails-and-risks.md`** — what cannot go wrong.
6. **`execution/README.md`** — the four-document sequence.
7. **`execution/01-audit-prompt.md`** — your first action.

The two source reports are canonical:

- **`source/nativeforge-product-intelligence-report.md`** — product strategy, market gap, personas, lifecycle, sources, forms, scoring, sovereignty, M0/M1/M2/M3 scope. Reference for any product or feature question.
- **`source/nativeforge-revenue-model.md`** — pricing tiers (Core / Pro / Enterprise / Sovereignty / Consortium), unit economics, tribal procurement mechanics, monetization models, financial projections. Reference for any business-model, tier-gating, or licensing-architecture question.

Both are sources of truth. Where the product-intelligence report and the revenue-model report touch the same surface (e.g., pricing tiers, deployment models), the revenue model takes precedence — it is the more recent and more rigorous treatment.

The domain files (`domain/*.md`) are working references for the build. Read each one as the relevant sprint comes up. Do not try to load them all at once.

**The revenue model defines five tiers (Core / Pro / Enterprise / Sovereignty / Consortium) that have build implications even though M0 ships none of them as billable products.** Specifically:

- The **Sovereignty** tier (private/dedicated cloud deployment) is a hard architectural commitment that the M3 product must support without a rewrite. Decisions made in Sprint 0 about tenant isolation must not preclude private deployment later. This is already reflected in `execution/03-demo-isolation-spec.md`; do not regress on it.
- The **Consortium** tier (one paying customer org with up to 8 member tribes) implies a one-to-many relationship between the buying organization and the operating tribal entities. M0 ships a one-to-one (org → tribal profile) for simplicity, but the data model should not preclude future consortium support. Flag any M0 decision that hard-binds the relationship in a way that would force a costly migration later.
- The **license vs. SaaS** distinction is M3 enforcement, not M0 enforcement. Do not build license-key infrastructure or subscription metering in M0.

## Step 1 — Run the audit

Open `execution/01-audit-prompt.md`. Execute the prompt block exactly as written. Do not modify it; if you have suggestions, surface them in the audit's open-questions section, not by editing the prompt.

The audit produces a single markdown file at:

```
nativeforge-research/audit-output.md
```

Every claim in the audit cites a file path and line range from the ContractForge repo. No "appears to" without a citation.

When the audit is written, **stop**. Do not proceed to step 2 until the human has read it and signed off.

## Step 2 — Architecture-boundary decision

After the human signs off on the audit, open `execution/02-architecture-boundary.md`.

Fill in:

- Section 1: the A/B/C recommendation, with reasoning anchored in audit findings.
- Section 3: the M0 schema, finalized against the audit's findings about which generic tables already exist.
- Section 5: the seven sign-off questions for the human.

When the document is updated, **stop**. Do not proceed to step 3 until the human has answered all seven sign-off questions.

## Step 3 — Sprint 0 (demo isolation + review gate)

After the human signs off on the architecture-boundary decision, open `execution/03-demo-isolation-spec.md` and implement Sprint 0 exactly as specified.

The acceptance criteria are at the bottom of that document. All checkboxes must be checked before Sprint 0 is done. CI must show all 7 demo-isolation tests passing on the main branch before any feature work begins.

When Sprint 0 is done, **stop**. Do not proceed to step 4 until the human confirms Sprint 0 is merged.

## Step 4 — Sprints 1–7 (M0 build)

Open `execution/04-m0-implementation-plan.md`. Execute the sprint sequence in order. Do not parallelize.

For every PR, run the checklist in `validation/definition-of-done.md`. Every box must be checked. The PR description references the relevant operating principles and any near-violations avoided.

When all seven sprints are merged and the M0 validation gate at the bottom of `04-m0-implementation-plan.md` is satisfied, declare M0 done and hand off to the human for the buyer demo.

## What you do not do

- Do not write code in steps 1 or 2.
- Do not commit secrets, ever.
- Do not touch production secrets.
- Do not create demo data in real orgs.
- Do not broadly refactor ContractForge.
- Do not skip review gates.
- Do not auto-submit anything.
- Do not edit the operating principles.
- Do not silently violate any operating principle. If something seems to require violating one, surface the contradiction and ask.

## How to report

After each step, write a short status update in the PR description (or, for steps 1 and 2, at the bottom of `audit-output.md` or `02-architecture-boundary.md` respectively). The update lists:

- What changed (file paths, line ranges, test names).
- What tests pass.
- Which operating principles were relevant to the decisions made.
- Any open questions for the human.

Chat is for synchronous coordination. PR descriptions and execution-doc updates are the durable record. Default to the durable record.

## When you are stuck

- If the audit reveals something that contradicts what's in this repo (e.g., ContractForge's tenancy model is fundamentally different from what we assumed), surface it in the audit's open-questions section. Do not silently work around it.
- If a guardrail in `context/guardrails-and-risks.md` would force you to skip a feature in the demo, raise that. Do not work around the guardrail.
- If you cannot satisfy a `definition-of-done` checkbox for a legitimate reason, explicitly call it out in the PR description, propose a follow-up ticket, and let the human approve the gap. Do not quietly skip it.

## The mission, restated

NativeForge is viable. The wedge is real. ContractForge gives you a head start. But the first engineering priority is not features — it is product separation and demo/tenant isolation, so we do not poison customer trust on day one.

Build the walls around the launchpad first. Then build the rocket.
