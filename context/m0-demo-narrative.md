# M0 Demo Narrative

This is the story M0 has to tell, end to end, in roughly one minute. If any beat breaks, M0 is not done.

## The walkthrough

### Beat 1 — Login

A tribal grant manager logs in to the demo NativeForge org. They land on the pipeline view.

### Beat 2 — Pipeline at a glance

They see 12 NativeForge-recognized Sparks across pipeline stages (New, Evaluating, Pursuing, Drafting, Submitted, Awarded, Not Pursuing). The seeded mix should show realistic distribution — most in New and Evaluating, a few in Pursuing.

### Beat 3 — A Spark catches their eye

One Spark is an IHS behavioral health opportunity. The card surfaces:

- Eligibility: likely yes
- Mission match: strong
- Reporting burden: moderate
- Tribal resolution required
- Due in 38 days

### Beat 4 — Open the Spark

Clicking opens the Spark detail page. They see:

- Plain-language NOFO summary (AI-generated, with a visible AI badge)
- Extracted requirement checklist — required forms, attachments, narrative sections, page limits, formatting rules
- Required forms list, with an SF-424 preview button
- Pursuit recommendation with a templated explanation: "Strong match. You are an eligible entity, the program directly addresses your stated priority of behavioral health, and the $X award ceiling is within your management capacity. The 38-day window is feasible. Recommend immediately assigning a grant writer."

### Beat 5 — SF-424 preview

They click the SF-424 preview button. A PDF renders, pre-filled from their tribal profile. Every autofilled field has an AI badge. A "Mark as ready for review" button is visible. The system will not allow them to mark it final until a reviewer approves.

### Beat 6 — Add to pipeline

They click "Add to Pipeline." The Spark moves to Pursuing. Tasks auto-generate from the requirements checklist. The deadline calendar updates with the application deadline and any task due dates.

### Beat 7 — Sovereignty

They click into the Data Sovereignty page. They see the Trust Framework: tribe owns its data, no AI training on customer data, full data export at any time, audit logs, role-based access, human approval required before any submission, clear AI disclosure on all AI-generated content. They click "Export my data." A ZIP downloads with profile, sparks, requirements, tasks, and form packages as JSON + CSV.

## What the demo is selling

Not features. The demo is selling **trust** — that NativeForge respects tribal sovereignty in code, not in copy. And **leverage** — that a grant manager can do an hour of NOFO triage in 90 seconds.

The demo is not selling AI. AI is incidental. AI is the thing that does the boring parts so the grant manager can do the parts that matter.

## What breaks the demo

- An AI-generated paragraph without a badge.
- A demo Spark that shows up in a real org's view (test catches this; if it ever fires in production, the product is dead).
- An SF-424 preview that lets you submit without review (fails the state machine).
- An export that includes anything not owned by the requesting org.
- A pursuit recommendation that contradicts its score breakdown.
- A score that changes between page loads (scoring must be deterministic).
- A "tribal" reference that uses pan-Indian generalization (no "Native peoples have always..." language anywhere in templates).

If any of those happen during a buyer demo, recover honestly. Do not paper over them.

## What the demo deliberately does not do

- Live Grants.gov polling. The demo is fully seeded.
- Real AI drafting of narratives. Outline + summary only.
- Post-award setup. Awarded Sparks just sit in the Awarded column.
- Multi-tenant administration. One demo org.
- Real tribal council resolution workflow. Just a flag and a date.

These are M1, not M0. Saying so out loud during the demo is a strength, not a weakness — it shows discipline.
