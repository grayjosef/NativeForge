# Grant Lifecycle

Distilled from source report Section 4. Twelve stages. M0 covers the pre-award path through stage 11.

## Stage 1 — Organizational onboarding and entity profile creation (M0)

Collect: legal entity name, UEI, EIN, SAM status, entity type, congressional district, address, AOR, key contacts, indirect cost rate, assurances, narratives.

Common mistakes: outdated SAM registration, mismatched entity name vs. SAM, expired indirect cost rate.

NativeForge: guided onboarding wizard. Highest-ROI feature in the entire product.

## Stage 2 — Funding priority setup (M0 minimal, M1 full)

Collect: tribal strategic plan priorities, program areas of interest, geographic service area, typical grant size range, preferred agencies, match capacity, staff availability.

NativeForge M0: manual priority selection from structured taxonomy. M1: ML-based matching against past awards.

## Stage 3 — Opportunity ingestion and deduplication (M0 seeded, M1 live)

Sources: Grants.gov (REST API), SAM.gov Assistance Listings, Federal Register, agency-specific portals (BIA, IHS, ANA, USDA RD, HUD ONAP, EPA, DOE, DOT, FEMA, CTAS).

Common mistakes: duplicate ingestion across overlapping sources, missing amendment notices, expired opportunities shown as active.

NativeForge M0: 12 hand-curated demo Sparks. M1: daily Grants.gov polling + amendment tracking + deduplication by `(source, source_id)`.

## Stage 4 — Eligibility analysis (M0)

Compare extracted NOFO eligibility section against entity profile. Flag mismatches.

Common mistakes: applying for programs where tribal organizations are not eligible; missing tribal set-aside programs that general searches don't surface.

NativeForge M0: basic eligibility tagging (tribal-eligible Y/N) plus deterministic rule-based check. M1: detailed eligibility extraction with confidence scoring.

## Stage 5 — Fit/match and capacity scoring (M0)

Six dimensions, weighted composite, recommendation tier. See `scoring-model.md`.

NativeForge M0: full scoring with templated explanation.

## Stage 6 — Requirement extraction and checklist generation (M0)

Extract: required forms, attachments, narrative sections, page limits, formatting rules, evaluation criteria, scoring weights, deadlines, match requirements, indirect cost rules, special conditions, tribal resolution requirements.

NativeForge M0: AI extraction into structured fields. Confidence scoring per field. Low-confidence flagged for human review.

## Stage 7 — Task assignment and internal workflow (M0)

Auto-assign tasks based on role: budget narrative → finance officer; project narrative → program director; forms → grant manager.

NativeForge M0: manual task assignment with deadline tracking. Auto-assignment is M1.

## Stage 8 — Tribal resolution and council approval tracking (M1)

Resolution status: drafted / submitted to council / approved / signed.

Common mistakes: starting the resolution process too late; wrong template for a specific agency.

NativeForge: resolution tracker (M1) and template library (M1).

## Stage 9 — Budget development (M1)

Categories: personnel, fringe, travel, equipment, supplies, contractual, other direct, indirect.

NativeForge: budget worksheet template (M1), AI-assisted budget narrative drafting (M1).

## Stage 10 — Narrative drafting (M1)

Sections: needs statement, project description, SMART objectives, evaluation plan, logic model, sustainability plan.

Cultural guardrails: never invent community statistics; clearly distinguish AI-drafted from cited; default to strength-based; preserve tribal voice; never use pan-Indian generalizations.

NativeForge M0: AI outline generation only. Full drafting with cultural guardrails is M1.

## Stage 11 — Review, assembly, submission tracking (M0 partial)

All required forms, attachments, narrative sections; submission portal; submission method.

Common mistakes: wrong file format; exceeding page limits; missing required certifications; submitting before tribal council resolution is signed.

NativeForge M0: document assembly checklist with completion flags. Submission tracking is M1+.

## Stage 12 — Post-award setup through closeout (M2)

Award notification → award setup → budget activation → drawdown/reimbursement tracking → milestone tracking → progress reports → SF-425 financial reports → amendment tracking → closeout → audit-ready archive.

NativeForge: M1 ships basic award setup and reporting calendar. M2 ships drawdowns, subrecipient monitoring, Single Audit prep.

## What M0 covers, in scope-bound form

Stages 1, 3 (seeded), 4, 5, 6, 7 (manual), 11 (assembly checklist + SF-424 preview).

What M0 explicitly does not cover: Stage 2 (priority matching engine), Stage 8 (resolution tracking), Stage 9 (budget development), Stage 10 (full drafting), Stage 12 (post-award).
