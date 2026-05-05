# 01 — Audit Prompt

This is the prompt Cursor runs against the existing ContractForge repository. It produces a written audit report. **No code is written in this step.**

The audit's primary purpose is to make the architecture-boundary decision in `02-architecture-boundary.md` an informed call instead of a guess.

---

## Prompt to paste into Cursor

```
You are auditing the existing ContractForge codebase to determine the safest way
to introduce NativeForge as a separate product surface while reusing shared
engine mechanics.

NativeForge is a sovereignty-first tribal grant pursuit and compliance platform.
The two canonical source reports are at:

    nativeforge-research/source/nativeforge-product-intelligence-report.md
    nativeforge-research/source/nativeforge-revenue-model.md

The product-intelligence report covers product strategy, market gap, personas,
lifecycle, grant sources, forms, scoring, sovereignty, and M0/M1/M2/M3 scope.

The revenue-model report covers pricing tiers (Core / Pro / Enterprise /
Sovereignty / Consortium), unit economics, tribal procurement mechanics, and
financial projections. Where the two reports touch the same surface, the
revenue model takes precedence.

The product context, M0 demo narrative, five pillars, guardrails, and operating
principles are in:

    nativeforge-research/context/

The distilled domain knowledge (personas, lifecycle, sources, forms, scoring,
sovereignty, etc.) is in:

    nativeforge-research/domain/

DO NOT IMPLEMENT ANYTHING IN THIS STEP. No commits. No edits. No migrations.
This is read-only audit. The deliverable is a written report.

# Operating principles

Read nativeforge-research/context/operating-principles.md before starting.
Those rules apply to every subsequent step.

# What to audit

Walk the ContractForge codebase and produce findings on:

1. Database schema
   - List every table.
   - For each table, classify it as:
     a) GENERIC — could plausibly be reused by NativeForge as-is
        (e.g., users, organizations, audit_log, ai_runs, documents, files)
     b) CONTRACT-SPECIFIC — bound to contract-pursuit semantics; should NOT
        be reused directly (e.g., solicitations, RFPs, NAICS codes, pricing)
     c) AMBIGUOUS — could be generalized but it's a judgment call
   - For each GENERIC table, note any field that is actually contract-specific
     and would need to be moved to a contract subtable.

2. Services / business logic
   - For each service module, classify the same way (GENERIC, CONTRACT-SPECIFIC,
     AMBIGUOUS).
   - Note which services are battle-tested (have tests, have been deployed,
     have run against real data) versus unverified scaffolding.

3. API routes
   - List all routes.
   - For each, note whether it's product-namespaced (/api/contractforge/...) or
     mounted at the root (/api/...).
   - Note any auth/tenancy middleware in the request path.

4. Frontend architecture
   - Routing strategy: are pages mounted under product namespaces or at root?
   - Component reuse: are domain-specific components separate from generic
     primitives, or are they intermixed?
   - Demo data handling: is there any current concept of demo orgs, demo
     records, or demo-only routes? If so, how is it enforced?

5. Auth and tenancy
   - What is the current tenancy model? Single-tenant per deploy, multi-tenant
     with org_id, multi-tenant with row-level security, something else?
   - How is the current user's org scoped on queries? Application-layer filter,
     middleware, RLS, or none?
   - Are there roles? If so, list them and where they're enforced.

6. AI / LLM usage
   - List every place where an LLM is called.
   - For each, note: what's the input, what's the output, is the output ever
     used in a "final" capacity (submitted, sent, approved), and is there a
     human review gate before that final step?

7. Demo / seed data
   - List every place demo or seed data is created or referenced.
   - For each, note whether it can be associated with a real customer org and
     how that's prevented.

8. Tests and CI
   - What test types exist (unit, integration, e2e)?
   - What does CI run today?
   - Is there any existing test that proves tenant isolation? If so, where?

# What to recommend

Based on the audit, produce explicit recommendations on:

A. Product-surface decision
   Recommend one of:
     A) Same repo, separate routes (/nativeforge/* and /api/nativeforge/*).
        Fastest. Reuses everything ContractForge has built.
     B) Forked repo. Clean break, two codebases. Slowest to share improvements.
     C) Shared "Forge Core" + product modules (cf_*, nf_*).
        Most defensible long-term, highest upfront cost, biggest premature-
        abstraction risk.
   Defend the recommendation with specifics from the audit. If the audit reveals
   that ContractForge is mostly unverified scaffolding, that pushes toward A.
   If ContractForge is battle-tested and stable, that opens the door to C.

B. Schema generalization
   For each GENERIC table identified above, recommend whether it should:
     - Stay as-is and be reused by NativeForge
     - Be lightly extended (new columns) to support NativeForge
     - Be split into a generic parent + product-specific child
     - Stay ContractForge-only and NativeForge gets its own equivalent
   Be opinionated. List the trade-offs for each non-obvious call.

C. Demo isolation enforcement strategy
   Given the current tenancy model, recommend the layered enforcement approach
   (see nativeforge-research/execution/03-demo-isolation-spec.md for the
   target standard). Note which layers already exist and which need to be built.

D. First migration plan
   What is the smallest, safest first migration that would set up the
   nf_* (or chosen-naming) namespace without disrupting ContractForge?
   Do not write the migration; describe it.

E. Risk list
   Top 10 risks to introducing NativeForge given what you saw in the audit.
   For each, note severity, likelihood, and the mitigation that would close it.

F. Battle-tested vs scaffolding inventory
   List every component, service, and table that you classified as "battle-
   tested" versus "unverified scaffolding." This is critical: we cannot
   generalize from code that hasn't survived contact with users.

# Format of the deliverable

Write the report as a single markdown document at:

    nativeforge-research/audit-output.md

Use these top-level sections in this exact order:
  1. Executive summary (one page max)
  2. Product-surface recommendation (A/B/C with reasoning)
  3. Schema audit (tables, classification, generalization recommendations)
  4. Services and API audit
  5. Frontend audit
  6. Auth and tenancy audit
  7. AI/LLM usage audit
  8. Demo and seed data audit
  9. Tests and CI audit
 10. Battle-tested vs scaffolding inventory
 11. First migration plan (described, not written)
 12. Risk list (top 10)
 13. Open questions for the human

Every claim in the report must reference a file path and line range from the
ContractForge repo. No "the codebase appears to..." — show the file.

# What NOT to do

- Do not write any code.
- Do not run any migrations.
- Do not modify any file in the ContractForge repo.
- Do not create demo data.
- Do not commit anything.
- Do not propose specific table names or column types yet — that's
  02-architecture-boundary.md's job.
- Do not estimate effort in days or weeks. Effort estimation comes after
  the architecture decision is made.

# When to stop

Stop when audit-output.md is written and saved. Then return control. The human
will review the audit and instruct you whether to proceed to
02-architecture-boundary.md.
```

---

## Why this prompt is structured this way

**Front-loaded operating principles.** Cursor reads `operating-principles.md` before doing anything. This prevents drift on commits, secrets, and refactor scope.

**The A/B/C recommendation is required, not optional.** The earlier draft of this prompt left the surface decision as something to "consider." That's wrong. The audit's primary deliverable *is* the surface decision. Everything downstream depends on it.

**Battle-tested vs scaffolding is a separate section.** This was missing from the original audit framing. You cannot generalize from unverified code, and you cannot make the C (shared Forge Core) recommendation if most of ContractForge hasn't survived contact with users.

**Every claim must cite a file and line range.** Audits produced without citations are vibes. The cited version is reviewable; the uncited version isn't.

**The output goes to `nativeforge-research/audit-output.md`, not to chat.** Audits that live in chat get lost. Audits that live in the repo get versioned, redlined, and referenced.

**Cursor stops before writing code.** This step explicitly hands control back to the human. The next step (`02`) is also human-gated.

---

## Human review gate

Do not move to `02-architecture-boundary.md` until you have personally read `audit-output.md` and either:

- agreed with the A/B/C recommendation, or
- overridden it with a documented reason in `audit-output.md` itself.

The architecture-boundary doc inherits the surface decision. If you change your mind later, you re-do the architecture-boundary doc.
