# 621 — Gate 114A: org-scoped customer persistence survey

Written before any implementation. Every claim below was reproduced by reading
`src/nativeforge/db/`, `src/nativeforge/repositories/`, `src/nativeforge/api/`,
`alembic/versions/` and the readiness services named in the brief.

## A note on one referenced path

The brief cites `docs/operations/620_GATE113_BINDING_STORE_READINESS_DELTA.md`.
Gate 113 committed that document as
`docs/operations/620_GATE113_READINESS_DELTA.md`. Same document, and it is the
one this survey read. There is no missing artifact.

## The shape of what exists

```text
src/nativeforge/db/          base.py  models.py  rls.py  session.py
src/nativeforge/repositories/  18 modules
src/nativeforge/api/           26 modules
src/nativeforge/routes/        does not exist - routes live under api/
```

`src/nativeforge/routes/` is named in the brief and is not a directory in this
repository. The route layer is `src/nativeforge/api/`, which is what was
surveyed.

## Customer persistence tables that already exist

23 tables are declared in `db/models.py`. **21 of them carry
`organization_id`.** The two that do not are `organizations` itself (it *is* the
organization) and `nf_evidence_intake_records`.

```text
nf_activation_state              nf_operator_actions
nf_active_opportunity_sources    nf_opportunity_sources
nf_audit_events                  nf_pursuit_briefs
nf_auto_publish_config           nf_pursuit_calendar_events
nf_discovery_intake_candidates   nf_pursuit_tasks
nf_discovery_intake_runs         nf_review_artifacts
nf_discovery_review_items        nf_source_check_runs
nf_form_packages                 nf_spark_requirements
nf_grant_pursuits                nf_spark_scores
nf_grant_sparks                  nf_tribal_profiles
nf_nofo_extraction_runs
```

Five further tables exist in migrations with no ORM model:

```text
nf_identities                    0023
nf_org_memberships               0024, RLS in 0027
nf_authority_proof_records       0026, RLS in 0027
nf_raw_source_payloads           0028
nf_tenant_customer_org_bindings  0029, RLS in 0029   <- Gate 113
```

## RLS coverage, and the single predicate behind it

Nineteen tables have row-level security installed by a migration, across
fifteen migrations from 0002 to 0029. **Every one of them installs the identical
predicate**, with no variation anywhere in the repository:

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

This is the most useful single fact in the survey. The boundary is uniform,
it is anchored on `organization_id`, and Gate 110's finding that
`organization_id` is *the* RLS authority is not a design intention but an
observable property of every policy in the schema.

`db/rls.py::apply_org_rls_gucs` is the only place those two GUCs are set, and it
is a PostgreSQL-only no-op elsewhere.

## Repositories that write org-scoped data

Eight of the eighteen repositories both take `organization_id` and write:

```text
activation_state.py     audit_events.py         discovery_review_items.py
pursuits.py             review_artifacts.py     source_check_runs.py
spark_scores.py         tribal_profiles.py
```

`operator_actions.py` writes without threading `organization_id` through its own
signature; it takes a model instance that already carries one. The remaining
repositories are read-only helpers.

## Is there an unsafe write path?

**No.** This was checked directly rather than assumed:

```text
occurrences of tenant_id in repositories/ or api/           0
occurrences of customer_org_id in repositories/ or api/     0
occurrences of organization_profile_id in repositories/     0
```

Nothing in the write layer knows those names exist. The only way an
organization reaches a session is `deps_db.get_org_context_with_db`, which
requires `X-NF-Org-Id`, parses it as a UUID, looks the row up in
`organizations`, and only then calls `apply_org_rls_gucs`. A label cannot reach
`app.current_org_id` because no code path carries one there.

That header is still an **unauthenticated claim**, which is Gate 112's finding
and is unchanged: `dev_org_header_containment_service.production_safe` is a
constant `False`, and the dependency refuses entirely unless
`NF_DEV_ORG_HEADERS` is on.

## The eight lanes, and what actually backs each

```text
lane                     table                            model  rls   repo
tenant_profile           nf_tribal_profiles               yes    yes   yes
identity_binding         nf_tenant_customer_org_bindings  no     yes   no
awarded_grants           none                             no     no    no
award_requirements       none                             no     no    no
tenant_digest            none                             no     no    no
document_library         none                             no     no    no
source_watchlist         none                             no     no    no
beta_onboarding          none                             no     no    no
```

Two lanes are partly built and six are empty.

`nf_tribal_profiles` is the closest thing to customer persistence that exists:
one row per organization, `organization_id` unique and NOT NULL, `is_demo`,
under RLS since migration 0003, with a repository that writes. What it lacks is
not schema — it is a person who can authenticate to own the row.

`nf_tenant_customer_org_bindings` is the inverse: RLS-backed schema with no ORM
model and no repository at all. Gate 113 built the table and the contract; there
is deliberately no write path.

## Three lanes, three different definitions of "persistence live"

This is the defect this gate should fix, and it is the same class the campaign
keeps surfacing — a value that *asserts* rather than *derives*:

```text
awarded_grants_requirements_readiness_service
    customer_persistence_live = _module_importable(
        "nativeforge.repositories.awarded_grant")

tenant_nofo_digest_readiness_service
    customer_persistence = False          # hard-coded

tenant_beta_readiness_service
    customer_persistence_live = False     # hard-coded
```

All three currently report `False`, and all three are currently correct. None of
them is measuring the same thing:

* Two are constants. They would stay `False` after persistence became real —
  the failure mode Gate 113 found in `migration_applied` and fixed.
* One is a **module-existence proxy**. Creating an empty
  `repositories/awarded_grant.py` would flip `customer_persistence_live` to
  `True` with no table, no RLS policy, no organization anchor and nobody able
  to authenticate. That is the worse of the two failures, because it moves in
  the unsafe direction.

The digest lane's `_detect_verified_operational_binding` has the same shape: it
asks whether `nativeforge.repositories.identity_binding` imports. It answers
correctly today only because that module does not exist.

## Is a migration required for the persistence spine?

**No, and this gate should not add one.**

The spine this gate builds is a *contract* over persistence: which capabilities
exist, which are schema-backed, which are RLS-backed, and which may actually be
written to. Every fact it needs is already observable — from `db/models.py`, from
`alembic/versions/`, and from the repositories directory.

Adding a table would be building the thing the contract exists to gate. The six
empty lanes each need their own migration when their own gate arrives, decided
against this spine rather than ahead of it.

## Answers to the specific questions

```text
customer persistence tables exist?      yes - 21 org-scoped, 19 under RLS
org-scoped repositories?                8 that write, of 18
persistence-facing services?            3 readiness surfaces, 1 safety guard
tenant profile persistence?             schema+repo yes, operational no
Awarded Grants persistence?             none - no table, no model, no repo
digest persistence?                     none
document library persistence?           none
source watchlist persistence?           none
beta onboarding persistence?            none
identity binding persistence?           schema+RLS yes, no model, no repo
any route writing under tenant_id?      no - zero occurrences in api/
any write path bypassing organization_id/RLS?  no
migration required?                     no - the spine is a contract
```

## What this gate must not do

```text
insert rows                     no fixture writes to any table
create the six missing tables   each belongs to its own gate
make persistence live           customer_persistence_live stays false
turn on auth                    no provider, no verifier, unchanged
add a route                     no customer UI, no new endpoint
```
