# 668 — Gate 124A: awarded grants persistence survey

Read before implementing. Every answer below was measured, not recalled.

## The thirteen questions

```text
1  awarded grant service contracts        9 services, ~3,800 lines, no storage
2  awarded grant table/model/repository   none of the three
3  award requirements table/model/repo    none of the three
4  does awarded grants persistence exist  no
5  does requirements persistence exist    no
6  does proof/audit persistence exist     no - the contract exists, the store
                                          does not
7  is organization_id available as anchor yes, on organizations, as everywhere
8  do write paths use the wrong anchor    there are no write paths; the
                                          contracts use tenant_id as a label
9  is a migration required                yes - 0032
10 same table or separate                 separate, and requirements are not
                                          built in this gate
11 does an API route exist                no
12 repository-backed without auth live    yes, the Gate 120/123 shape
13 should readiness change                yes, and one existing field is wrong
                                          for a reason worth fixing
```

## 1. Nine services, and not one of them stores anything

```text
awarded_grant_record_service            432 lines   what an award record is
awarded_grant_portfolio_service         380         the portfolio view
award_transition_service                715         pursuit -> award, and undo
award_requirement_model_service         494         what a requirement is
award_requirements_calendar_service     329         when it is due
award_requirement_proof_audit_service   329         what proves it was done
awarded_grants_demo_fixture_service     447         the fixture set
awarded_grants_requirements_artifact_*  354         the artifacts
awarded_grants_requirements_readiness_* 325         what none of it permits
```

Gate 91 built the separation, Gate 108 built the requirement tracking. Both
produce dictionaries and neither has anywhere to put one.

`awarded_grant_record_service` already carries the vocabulary this gate needs:

```text
AWARD_STATUSES                 draft_award_record, active_award,
                               closeout_pending, closed, cancelled,
                               mistaken_award, unknown
LIVE_AWARD_STATUSES            active_award, closeout_pending
REQUIREMENTS_EXTRACTION_STATUSES  not_attempted, human_entered,
                               evidence_extracted, unsupported_document_type,
                               needs_human_review, unknown
OBLIGATION_CAPABLE_EXTRACTION  human_entered, evidence_extracted
```

`mistaken_award` is the one worth noticing. An award recorded and later found
not to exist is a distinct status, not a deletion — which is the same
archive-never-delete instinct Gates 120 and 123 arrived at independently.

## 2–5. No tables, and the migrations confirm it

```text
tables in migrations                     30
matching award / grant / requirement     nf_grant_pursuits (0007)
                                         nf_grant_sparks (0004)
                                         nf_spark_requirements (0005)
```

All three are **pursuit-side**. `nf_grant_sparks` is a discovered opportunity,
`nf_grant_pursuits` is one being chased, `nf_spark_requirements` is what a NOFO
asks of an applicant *before* they apply.

None is an awarded grant, and conflating them is precisely what Gate 91 exists
to prevent.

```text
nf_awarded_grants        does not exist
nf_award_requirements    does not exist
repositories/awarded_grants.py     does not exist
repositories/award_requirements.py does not exist
```

## The defect this survey found: five lanes point at modules that do not exist

The capability service maps each lane to a contract module and detects it by
import. Five of the eight point at nothing:

```text
lane                            mapped module                          exists
awarded_grants_persistence      awarded_grant_record_contract_service   NO
award_requirements_persistence  award_requirements_model_service        NO
beta_onboarding_persistence     tenant_beta_onboarding_service          NO
document_library_persistence    award_document_store_service            NO
source_watchlist_persistence    tenant_source_watchlist_service         NO
identity_binding_persistence    ...binding_store_service                yes
tenant_digest_persistence       tenant_nofo_digest_builder_service      yes
tenant_profile_persistence      tribal_profile_service                  yes
```

**Two of the five are near-misses on real services:**

```text
mapped   awarded_grant_record_contract_service
real     awarded_grant_record_service               (no `_contract`)

mapped   award_requirements_model_service
real     award_requirement_model_service            (singular `requirement`)
```

So `awarded_grants_persistence` reports
`no_service_decides_what_may_be_written` — and a 432-line service decides
exactly that. The lane is false for the wrong reason.

The other three genuinely do not exist and their `False` is correct.

This is the same family as Gate 120's filename probe and Gate 122's provider
miscount: a detector reporting on a *name* rather than a capability. It has now
appeared three gates running, in three different services.

Gate 124E fixes the two near-misses and leaves the three real absences alone.
Fixing them does **not** make either lane operational — `customer_auth_live` is
still false and still blocks both.

## 7–8. The anchor, and what the contracts use today

```text
organization_id           appears in 1 of 9 award services
tenant_id                 appears in 7
customer_org_id           appears in 5
organization_profile_id   appears in 0
```

That distribution is correct for a contract layer with no storage.
`AWARD_RECORD_FIELDS` begins with `tenant_id`, which is the *label* the contract
reasons about; there has been no row to anchor, so no anchor was needed.

The moment a row exists, `organization_id` anchors it and `tenant_id` becomes a
label alongside — the same shape Gates 113, 120 and 123 settled on.

## 9–10. One migration, one table, and requirements deliberately excluded

`0032_nf_awarded_grants`. Requirements get their own table in a later gate, for
a reason the data makes obvious:

```text
awarded grant     one per award. Amount, period, funder, status.
requirement       many per award. Type, due date, recurrence, proof, status.
```

A requirement recurs — quarterly financial reports, annual performance reports —
so a single award produces dozens of rows with their own due dates and their own
proof audit trail. Putting them in one table would mean either repeating the
award on every requirement row or storing a JSON array nothing can query by due
date, and a calendar that cannot query by due date is not a calendar.

Gate 108 already models them separately. This gate builds the first half and
names the second.

## The rule this gate must not break

Gate 91's separation, in the form it actually takes in code:

```text
pursuit_reporting_burden_projection_service
  every field prefixed `projected_`
  every result carries `is_active_obligation: False`

awarded_grant_record_service
  OBLIGATION_CAPABLE_EXTRACTION = {human_entered, evidence_extracted}
```

A projection is what a NOFO *suggests* will be required if you win. An
obligation is what an award *does* require now. The projection service refuses
to produce the second, and this gate must not undo that by copying a projected
requirement into an award row.

`active_obligation_status` is therefore its own column, derived from the award's
own extraction status and never from anything on the pursuit side. A test asserts
a projected burden cannot reach it.

## 11. No API route

Nine route decorators in `grant_spark_routes.py`, all pursuit-side. Nothing
serves an awarded grant.

## 12–13. Repository-backed without auth, and what readiness may say

```text
customer_auth_live                     false
verified_operational_binding           false
ready_for_operational_awarded_tracking false
requirement_extraction_live            false
document_storage_live                  false
ui_available                           false
```

The Gate 120/123 shape applies unchanged: a repository can exist, be exercised
against an isolated database, and refuse every production write.

What readiness may say afterwards:

```text
awarded_grants_persistence schema_available      false -> true
awarded_grants_persistence repository_available  false -> true
awarded_grants_persistence write_path_available  false -> true
awarded_grants_persistence operational           false, unchanged
award_requirements_persistence                   every field unchanged
ready_for_operational_awarded_tracking           false, unchanged
```

## Gate 124F: the API route decision, made here

**Skip it.** The three reasons from Gates 120E, 122E and 123E hold, and one is
specific:

```text
1  a read route needs a session to scope by, and /current-user 401s for
   everybody, so the authenticated branch is unreachable and untestable
2  the table will hold zero rows, so the route's only behaviour is `no_awards`
3  an awarded grant is the most consequential object in this product - it is a
   real obligation to a real funder - and the first surface that serves one
   should be built when a real tenant can be authenticated to read it, not
   eight gates earlier against an empty table
```

## Implementation constraints carried out of this survey

```text
1  migration 0032 creates nf_awarded_grants; requirements are named, not built
2  organization_id anchors; tenant_id and customer_org_id are labels with no
   foreign key; organization_profile_id refused as an anchor
3  source_pursuit_id and source_opportunity_id are lineage text, never a
   foreign key and never a reason to create an award
4  active_obligation_status is its own column and is never derived from a
   projected burden
5  the Core sa.Table restates every CHECK constraint (Gate 119C's defect)
6  archive by setting archived_at; no DELETE path. `mistaken_award` is a status,
   not a deletion.
7  unknown stays unknown; nothing infers an award status, an amount, or an
   obligation
8  production writes require customer_auth_live AND verified operational binding
9  bridge the Gate 91/108 vocabularies - AWARD_STATUSES, LIVE_AWARD_STATUSES,
   REQUIREMENTS_EXTRACTION_STATUSES, OBLIGATION_CAPABLE_EXTRACTION - import,
   never restate
10 fix the two near-miss contract mappings; leave the three real absences false
11 every new conjunct both derived and injectable
12 no API route; document why
```
