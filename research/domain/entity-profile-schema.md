# Entity Profile Schema

The entity (tribal) profile is the most important data structure in NativeForge. Distilled from source report Section 6. The full SQL is in `execution/02-architecture-boundary.md`.

## Why the profile is the core data asset

It powers:

- Eligibility checks (entity type, federally recognized status, registration validity)
- Form autofill (SF-424 fields 8a–8f, 16, 21; SF-424A budget basics; SF-LLL)
- Grant matching and scoring (mission alignment, capacity fit)
- AI narrative drafting (community profile, governance narrative, past performance)
- Resolution tracking (authorized representative, governance structure)
- Compliance tracking (indirect cost rate, certifications, audit history)
- Sovereignty controls (data export, audit log scoped to org)

A tribe fills it out once. Every subsequent grant pursuit reuses it. The most direct ROI demonstration in the entire product.

## Sections of the profile

### Legal identity

- `legal_name` — must match SAM.gov exactly
- `uei` — Unique Entity Identifier
- `ein` — Federal Tax ID
- `sam_registration_status` — active | expired | unknown
- `sam_registration_expires` — date
- `entity_type` — federally_recognized_tribe | tribal_government | tribal_nonprofit | tribal_college | alaska_native_corp | native_hawaiian_org | native_nonprofit
- `federally_recognized` — Y/N
- `tribal_code` — if applicable
- `state` — state of incorporation/operation
- `congressional_district_house`, `congressional_district_senate`

### Location and address

- `physical_address` — JSON with street, city, county, state, zip
- `mailing_address` — JSON, if different
- `service_area_description` — county, tribal land, reservation, village

### Authorized officials

- `authorized_representative` — JSON: name, title, email, phone, signature blob ID
- `alternate_aor` — same shape
- `grants_manager` — name, title, email
- `finance_officer` — name, title, email
- Project Director templates (M1; reusable per application)

### Financial

- `indirect_cost_rate` — numeric (e.g., 18.5)
- `indirect_cost_rate_type` — predetermined | fixed | provisional | de_minimis
- `indirect_cost_cognizant_agency`
- `indirect_cost_period_start`, `indirect_cost_period_end`
- `de_minimis_election` — Y/N (15% MTDC if no negotiated rate)
- `fiscal_year_start_month` — int (1–12)
- annual audit status and findings (M1)

### Certifications and assurances

- `sf424b_assurances_certified` — Y/N + date
- `sf_lll_certified` — Y/N + date
- `civil_rights_compliant` — Y/N
- `drug_free_workplace` — Y/N
- `debarment_certification` — Y/N
- SAM.gov active registration auto-verified via API (M1)

### Organizational capacity narratives

- `org_overview_narrative` — 2-paragraph editable
- `governance_narrative` — governance structure description
- `staffing_capacity_narrative` — capacity story
- `past_performance_narrative` — reusable paragraphs
- `community_profile` — tribe-specific community description

These narratives are the raw material for AI drafting in M1. M0 stores them; the AI uses them in M1.

### Standard attachment library (M1)

- Organizational chart (upload)
- Most recent audit report
- Indirect cost rate agreement
- Tribal resolution templates
- Past grant awards list
- Financial statements (high sensitivity; admin-only access)

## Data sovereignty considerations

- Profile data is org-scoped. Every read filtered by `organization_id`.
- Export endpoint returns the full profile as JSON (M0).
- Audit log records every change with timestamp and actor.
- Authorized representative signature blob is stored as a document (sensitive).
- High-sensitivity fields (financial statements, indirect cost rate agreement docs) require role-based access in M1.
- No profile field is ever sent to a model training pipeline. AI usage of profile data is for the user's own drafts, scoped to the user's session, and logged.

## Profile completeness gating

The product warns (does not block) when a Spark autofill would leave required fields blank because the profile is incomplete. Examples:

- SF-424 8c (UEI) blank → warning before preview is generated.
- SF-424 21 (Authorized Representative) blank → warning + cannot transition package to `approved` until populated.

Blocking would frustrate users who want to look at a Spark before completing onboarding. Warning preserves the look-around path while making the gap visible.

## M0 acceptance for the profile

- All fields above present in the database schema.
- Onboarding wizard guides through Legal Identity → Location → Authorized Officials → Financial → Certifications → Narratives.
- Profile page allows editing any section after onboarding.
- Edits write to audit log.
- Export endpoint returns the full profile JSON for the requesting org only.
- Demo isolation tests prove the profile is org-scoped.
