# 02 — Architecture Boundary

This document is the spine of the build. It answers the questions that determine the shape of every subsequent file:

1. Is NativeForge a fork, a module, or a separate product surface on a shared core?
2. What lives in shared/generic tables, what lives in NativeForge-only tables, what stays ContractForge-only?
3. How do the two products coexist without poisoning each other?

**This document is read after `01-audit-prompt.md` returns its report.** Do not fill in the schema sections until you have the audit in hand.

---

## Section 1 — The product-surface decision (A/B/C)

Three options. They are not equivalent, and the right answer depends on what the audit reveals about ContractForge's maturity.

### Option A — Same repo, separate routes

```
contractforge/
├── apps/
│   ├── contractforge/        ← existing surface
│   └── nativeforge/          ← new surface (new routes, new pages)
├── packages/
│   ├── ui/                   ← shared component primitives (already exists)
│   ├── auth/                 ← shared auth (already exists)
│   └── db/                   ← shared schema, both products' tables live here
└── ...
```

Routes:
- `/nativeforge/*` — frontend
- `/api/nativeforge/*` — backend

**When this is right:** ContractForge is mostly unverified scaffolding, OR there's a customer waiting and speed matters more than long-term separation. Reusing auth, tenancy, AI runs, audit log, file storage, and component primitives saves weeks. The cost is that demo isolation has to be enforced very carefully because demo data lives in the same database as real data.

**When this is wrong:** ContractForge is battle-tested and stable, and you have time to build the right shared abstraction. In that case, A leaves you wedged between two products inside one app, with no clean boundary, and you'll regret it.

### Option B — Forked repo

```
contractforge/                ← unchanged
nativeforge/                  ← copy of contractforge, then diverged
```

**When this is right:** Almost never. Two codebases means every shared improvement has to be ported manually, and they will drift. The only case for B is hard legal/data isolation requirements that cannot be met by tenant separation in a single repo — and those requirements should drive a private deployment offering (M3), not a forked codebase.

**When this is wrong:** Most of the time. Default to A or C.

### Option C — Shared Forge Core + product modules

```
forge/
├── packages/
│   ├── forge-core/           ← shared platform: auth, tenancy, audit, AI, files
│   ├── forge-ui/             ← shared component primitives
│   └── forge-db/             ← shared base tables (forge_organizations, etc.)
├── apps/
│   ├── contractforge/        ← cf_* tables, contract logic, contract UI
│   └── nativeforge/          ← nf_* tables, grant logic, grant UI
└── ...
```

**When this is right:** ContractForge is battle-tested AND you have time AND the shared abstractions are obvious from the audit. The audit must produce a clear list of GENERIC tables/services that can survive a generalization pass without churn.

**When this is wrong:** You don't yet have two stabilized products. Premature shared abstractions calcify the wrong shape. You will end up with `forge_organization.contract_specific_field_we_couldnt_remove` and a six-month migration to undo it. "Duplication is far cheaper than the wrong abstraction" applies.

### The disciplined call

Default recommendation, pending audit: **Option A** with explicit duplication where domains diverge, and a `forge_*` rename pass deferred to after M1 ships and the seams are visible.

The case for C is only made if the audit produces a clear list of GENERIC, battle-tested components that can be generalized today without breaking ContractForge. That is a high bar. Do not weaken it.

The case for B is only made if there is a hard external reason — sovereignty/data residency for a specific customer that requires its own deployment artifact. In which case, B is downstream of A or C, not a substitute for it.

**Cursor: fill in the actual recommendation here once the audit is in.**

```
RECOMMENDATION (post-audit): _______________
REASONING: _______________
```

---

## Section 2 — Naming convention

Once the surface is chosen, lock the naming convention before writing any schema.

| Layer | Pattern | Examples |
|---|---|---|
| Shared / generic tables | `forge_*` (option C) or no prefix (option A) | `forge_organizations`, `forge_users`, `forge_audit_log` |
| ContractForge-specific | `cf_*` | `cf_contract_sparks`, `cf_response_plans` |
| NativeForge-specific | `nf_*` | `nf_grant_sparks`, `nf_tribal_profiles` |
| API routes | `/api/<product>/*` | `/api/nativeforge/sparks` |
| Frontend routes | `/<product>/*` | `/nativeforge/pipeline` |
| Frontend components | `apps/<product>/components/...` | `apps/nativeforge/components/SparkCard.tsx` |
| Shared components | `packages/ui/...` (no product prefix) | `packages/ui/Button.tsx` |

Rule: a file with a product prefix imports nothing from the other product. Cross-product imports go through `forge-*` only.

---

## Section 3 — Schema proposal (NativeForge M0)

This section defines the NativeForge-specific tables needed for the M0 demo, and the shared tables NativeForge depends on. **It does not propose changes to ContractForge tables.** Generalization comes later, after stability.

### Shared / generic tables (from `forge_*` or unprefixed, depending on option A vs C)

Cursor will fill in the audit's recommendations on which of these already exist in usable form:

- `organizations` — tenant root. Must already exist.
- `users` — must already exist.
- `org_users` — membership / roles join. Must already exist.
- `audit_log` — every state-changing action. Must already exist or be built.
- `ai_runs` — record of every LLM call (input, output, model, cost, user, timestamp). May or may not exist.
- `documents` — uploaded files. May or may not exist.

Audit fills these in: ✅ already exists / ⚠ exists but contract-specific / ❌ does not exist.

### NativeForge-specific tables (M0)

These are the tables NativeForge needs to demo the wedge. Each is justified against a specific M0 feature.

#### `nf_tribal_profiles`

The core data asset. Powers eligibility, autofill, scoring, drafting, sovereignty.

```
id                          UUID PK
organization_id             UUID FK → organizations.id  (one-to-one for M0)
legal_name                  TEXT
uei                         TEXT
ein                         TEXT
sam_registration_status     TEXT  -- active | expired | unknown
sam_registration_expires    DATE
entity_type                 TEXT  -- federally_recognized_tribe | tribal_government |
                                     tribal_nonprofit | tribal_college |
                                     alaska_native_corp | native_hawaiian_org |
                                     native_nonprofit
federally_recognized        BOOLEAN
tribal_code                 TEXT NULLABLE
state                       TEXT
congressional_district_house TEXT
congressional_district_senate TEXT
physical_address            JSONB
mailing_address             JSONB
service_area_description    TEXT
authorized_representative   JSONB  -- name, title, email, phone, signature_blob_id
alternate_aor               JSONB
grants_manager              JSONB
finance_officer             JSONB
indirect_cost_rate          NUMERIC
indirect_cost_rate_type     TEXT  -- predetermined | fixed | provisional | de_minimis
indirect_cost_cognizant_agency TEXT
indirect_cost_period_start  DATE
indirect_cost_period_end    DATE
de_minimis_election         BOOLEAN
fiscal_year_start_month     INT
sf424b_assurances_certified BOOLEAN
sf_lll_certified            BOOLEAN
civil_rights_compliant      BOOLEAN
drug_free_workplace         BOOLEAN
debarment_certification     BOOLEAN
org_overview_narrative      TEXT
governance_narrative        TEXT
staffing_capacity_narrative TEXT
past_performance_narrative  TEXT
community_profile           TEXT
created_at                  TIMESTAMPTZ
updated_at                  TIMESTAMPTZ
created_by                  UUID FK → users.id
is_demo                     BOOLEAN  -- see 03-demo-isolation-spec.md
```

Indexes: `(organization_id)`, `(uei)`, `(is_demo, organization_id)`.

#### `nf_grant_sparks`

A grant opportunity ingested into NativeForge. The Spark vocabulary mirrors ContractForge's; the fields are grant-specific.

```
id                          UUID PK
organization_id             UUID FK → organizations.id  -- which org is tracking this Spark
source                      TEXT  -- grants_gov | sam_assistance | bia | ihs | ana | ctas | doe | hud | epa | usda | ntia | manual
source_id                   TEXT  -- e.g., grants.gov opportunity number
agency                      TEXT
sub_agency                  TEXT
program_name                TEXT
opportunity_title           TEXT
opportunity_number          TEXT
cfda_assistance_listing     TEXT
url                         TEXT
funding_floor               NUMERIC
funding_ceiling             NUMERIC
total_program_funding       NUMERIC
expected_awards             INT
award_type                  TEXT  -- grant | cooperative_agreement | formula | competitive
match_required              BOOLEAN
match_percent               NUMERIC
match_waiver_available      BOOLEAN
indirect_cost_allowable     BOOLEAN
posted_date                 DATE
loi_deadline                TIMESTAMPTZ
application_deadline        TIMESTAMPTZ
performance_period_start    DATE
performance_period_end      DATE
raw_nofo_text               TEXT  -- ingested
raw_nofo_url                TEXT
ingested_at                 TIMESTAMPTZ
ingested_by                 TEXT  -- system | user_id
extracted                   JSONB  -- structured extraction (see nofo-extraction-schema)
extraction_confidence       NUMERIC  -- 0.0–1.0
extraction_run_id           UUID FK → ai_runs.id NULLABLE
ai_summary                  TEXT
ai_summary_run_id           UUID FK → ai_runs.id NULLABLE
score_eligibility           NUMERIC
score_mission_alignment     NUMERIC
score_capacity_fit          NUMERIC
score_funding_value         NUMERIC
score_reporting_burden      NUMERIC
score_win_likelihood        NUMERIC
score_total                 NUMERIC
recommendation              TEXT  -- strong_pursue | pursue | pursue_with_conditions |
                                     needs_review | do_not_pursue | disqualified
recommendation_explanation  TEXT  -- TEMPLATED, not freeform LLM
pipeline_stage              TEXT  -- new | evaluating | pursuing | drafting |
                                     submitted | awarded | not_pursuing
pipeline_stage_changed_at   TIMESTAMPTZ
pipeline_stage_changed_by   UUID FK → users.id
created_at                  TIMESTAMPTZ
updated_at                  TIMESTAMPTZ
is_demo                     BOOLEAN
```

Indexes: `(organization_id, pipeline_stage)`, `(organization_id, application_deadline)`, `(source, source_id)` UNIQUE, `(is_demo, organization_id)`.

#### `nf_spark_requirements`

Extracted requirements from a NOFO. One Spark has many requirements.

```
id                          UUID PK
spark_id                    UUID FK → nf_grant_sparks.id
requirement_type            TEXT  -- form | attachment | narrative_section |
                                     eligibility | match | resolution | reporting |
                                     special_condition
label                       TEXT
description                 TEXT
required                    BOOLEAN  -- vs. optional/recommended
page_limit                  INT NULLABLE
formatting_rule             TEXT NULLABLE
extracted_from              TEXT  -- excerpt of NOFO supporting this requirement
confidence                  NUMERIC  -- 0.0–1.0
human_reviewed              BOOLEAN
human_reviewed_by           UUID FK → users.id NULLABLE
human_reviewed_at           TIMESTAMPTZ NULLABLE
created_at                  TIMESTAMPTZ
is_demo                     BOOLEAN
```

#### `nf_pursuit_tasks`

Checklist items derived from requirements, plus user-added tasks.

```
id                          UUID PK
spark_id                    UUID FK → nf_grant_sparks.id
requirement_id              UUID FK → nf_spark_requirements.id NULLABLE
title                       TEXT
description                 TEXT
assignee_user_id            UUID FK → users.id NULLABLE
status                      TEXT  -- todo | in_progress | blocked | done | skipped
due_date                    DATE NULLABLE
created_at                  TIMESTAMPTZ
updated_at                  TIMESTAMPTZ
is_demo                     BOOLEAN
```

#### `nf_form_packages` (M0 = SF-424 preview only)

Tracks generated form packages for a Spark.

```
id                          UUID PK
spark_id                    UUID FK → nf_grant_sparks.id
form_type                   TEXT  -- sf424 | sf424a | sf424b | sf_lll
generated_pdf_blob_id       UUID FK → documents.id NULLABLE
field_data                  JSONB  -- mapped from tribal profile + spark
review_status               TEXT  -- draft | review_requested | reviewed | approved
review_state_history        JSONB  -- append-only audit of state transitions
created_at                  TIMESTAMPTZ
updated_at                  TIMESTAMPTZ
is_demo                     BOOLEAN
```

The `review_status` field is enforced server-side as a state machine. See `03-demo-isolation-spec.md` Section 4.

### Tables explicitly deferred past M0

These show up in the report but are not M0:

- `nf_resolution_tracker` — M1
- `nf_tribal_resolution_templates` — M1
- `nf_partners_mou` — M1
- `nf_award_records` — M1 (post-award setup)
- `nf_reporting_calendar` — M1
- `nf_drawdowns` — M2
- `nf_subrecipients` — M2
- `nf_single_audit_packages` — M2
- `nf_community_impact_metrics` — M2

---

## Section 4 — What this document does NOT decide

- Specific column types beyond TEXT/NUMERIC/etc. — those depend on the database (Postgres / MySQL / SQLite) which the audit identifies.
- The migration ordering — that's covered in `04-m0-implementation-plan.md`.
- Foreign-key cascade behavior — defaulted to RESTRICT; override per-table where needed.
- The exact RLS policies — covered in `03-demo-isolation-spec.md`.
- The exact LLM provider choice — out of scope for this doc; the audit notes what's currently used.

---

## Section 5 — Open questions for the human (post-audit)

After Cursor returns the audit and updates this document with the recommendation, these are the calls you make:

1. Lock A, B, or C? Sign off here: ______
2. Lock the naming convention (`nf_*` / `cf_*` / `forge_*`)? Sign off here: ______
3. Approve the M0 table list? Sign off here: ______
4. Any tables to remove from M0? List: ______
5. Any tables to add to M0? List: ______
6. Database is Postgres? (RLS available, JSONB available) Confirm: ______
7. Tribal profile is one-to-one with organization for M0? Confirm: ______

Until all seven are answered, do not move to `03-demo-isolation-spec.md`.
