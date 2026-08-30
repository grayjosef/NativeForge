# 664 — Gate 123A: tenant profile persistence survey

Read before implementing. Every answer below was measured, not recalled.

## The twelve questions

```text
1  tenant profile schema/table/model        nf_tribal_profiles, 22 columns
2  tenant profile repository status         exists, 3 functions, one deletes
3  tenant profile service contracts         25 tenant_* services; one is the
                                            beta profile contract
4  does it store organization_id            yes, and it is the RLS anchor
5  tenant_id/customer_org_id/profile_id in
   write paths                              not in the table; heavily in the
                                            contract layer as labels
6  is existing profile data fixture-only    there is no data at all - 0 rows
7  does RLS apply                           yes, org + demo, both directions
8  is a migration required                  yes, and this is the finding
9  watchlist/preferences: same table?       neither - no watchlist table exists
10 does an API route exist                  yes, four, all demo-org only
11 can it become repository-backed without
   auth live                                yes, for the contract and the
                                            fixture path; production writes
                                            stay blocked
12 should readiness change                  no lane flips; one new fact is
                                            reported
```

## The finding: there are two different tenant profiles

This is the thing that decides the whole gate.

```text
nf_tribal_profiles (migration 0003, 22 columns)
  legal_name  entity_type  uei  ein
  sam_registration_status  sam_expiration_date
  physical_address  mailing_address  service_area_description
  authorized_representative  grants_manager  finance_contact
  indirect_cost_rate  certifications  standard_narratives
  attachment_index
```

That is the **grant-application identity**: who this Tribe is when a form is
submitted. UEI, EIN, SAM registration, contacts, boilerplate narratives.

```text
tenant_beta_profile_service (Gate 103, no table, no repository)
  recognition_status  operating_states  service_area
  applicant_classes  program_priorities  excluded_applicant_classes
  source_watchlist  digest_preferences  routing_rules  alert_rules
  document_library_requirements  awarded_grants_enabled
  reporting_tracking_enabled  human_review_notes  profile_fact_status
```

That is the **beta behaviour profile**: how this tenant wants NativeForge to
behave. Every field Gate 123B asks for is here, and **not one of them is a
column in `nf_tribal_profiles`.**

Verified rather than assumed — all ten of Gate 123's named fields are present in
the Gate 103 contract's output, and the contract has no `persisted` field
because nothing has ever stored it.

## Why they must not share a table

They differ in every way that matters for a schema:

```text
                    identity profile        behaviour profile
what it is          facts about a Tribe     preferences of a tenant
who supplies it     a grants administrator  a tenant admin
how it changes      rarely, on renewal      whenever priorities shift
what breaks if      a form is rejected      a digest is wrong
  it is wrong
fact status         implicitly trusted      explicitly tracked per field
```

The last row is the decisive one. Gate 103 tracks a `fact_status` per field —
`verified`, `tenant_supplied`, `unknown`, `needs_human_review` — because a
recognition status somebody guessed and a recognition status somebody confirmed
are different objects. `nf_tribal_profiles` has no such column and adding one
would mean retrofitting it onto sixteen fields that never needed it.

Merging them would produce a 38-column table where half the rows carry a fact
status and half do not.

**Conclusion: migration 0031 creates `nf_tenant_beta_profiles`.** The identity
profile keeps its table, its repository and its four demo routes untouched.

## 2. The existing repository, and what it does that this gate will not

`repositories/tribal_profiles.py`, 61 lines, three functions:

```text
get_tribal_profile_for_org     org-scoped read, via a scoping helper
append_profile_audit           an audit row per change
delete_tribal_profiles_for_org_ids   a real DELETE
```

The delete is docstringed "tests / teardown" and is used for exactly that. Gate
123's repository archives rather than deletes, and does not add a delete path —
the two tables have different lifecycles and the beta profile's history is the
thing a digest complaint gets debugged against.

The audit pattern is worth carrying: `NfAuditEvent` already carries
`tribal_profile_id`, and a beta profile write should be auditable the same way.

## 4 & 7. organization_id anchors it, and RLS is already the standard predicate

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

`nf_tribal_profiles` carries it and so will `nf_tenant_beta_profiles`. This is
the nineteenth table to use that predicate and the shape does not vary.

## 5. Labels are everywhere in the contract layer and nowhere in the schema

```text
tenant_id                appears in 21 of 25 tenant_* services
customer_org_id          appears in 12
organization_profile_id  appears in 5
```

None is a column in `nf_tribal_profiles`. That separation is correct and Gate
123 preserves it: `tenant_id_label` and `customer_org_id_label` are `text`, carry
no foreign key, and never select a row on their own. Gate 113's docstring
already records why — a label with a foreign key becomes an identity space by
accident.

## 6. There is no data

```text
rows in nf_tribal_profiles: 0
```

Not "fixture-only" — empty. So nothing needs migrating, and the question of
whether existing rows are real does not arise.

## 9. The watchlist has no table either

```text
tenant_source_watchlist_service.py   does not exist
nf_source_watchlist_entries          not in any migration
```

Gate 114 lists `source_watchlist_persistence` as its own lane, and the
capability service maps it to a table that has never been created.

So `source_watchlist_preferences` goes in the beta profile as a **preference**
— which sources this tenant wants watched — and the eventual watchlist *entries*
table stays a separate lane. A preference is small, per-tenant and changes with
priorities; entries are per-source, numerous, and change when a source does.

## 10. Four API routes, all demo-org only

`api/tribal_profile_routes.py`: POST, GET, PUT and an export, every one behind
`Depends(require_demo_org_db)`. They are part of Gate 122's fourteen dev-header
route modules and this gate does not touch them.

## 11. Repository-backed without auth is possible, and production writes are not

```text
customer_auth_live                False
operational_verified_binding      False
binding write_path_available      True
```

The same shape Gate 120 reached: a repository can exist, be exercised against an
isolated database, and refuse every production write. A beta profile row that
asserted a tenant's recognition status while nobody could be authenticated as
that tenant would be a fabricated fact in a table, which is worse than no table.

## 12. Readiness: one new fact, no lane flips

```text
tenant_profile_persistence   schema=True repo=True write_path=True
                             operational=False  demo_only=True
```

The lane already reports a write path, because `repositories/tribal_profiles.py`
exists and satisfies the file probe. Gate 123 adds a *second* profile with a
*second* repository, and the honest reporting is a new named fact rather than a
flipped lane:

```text
tenant_beta_profile_repository_available   false -> true
```

`operational` stays false for the same reason it has since Gate 114 — nobody can
own the row.

The spine currently reports `ready_to_build_next: None` and recommends
`customer_authentication`, with six lanes still needing repositories. After this
gate the beta profile has one; the six are unchanged, because the beta profile
is not one of the eight capability lanes.

## Gate 123E: the API route decision, made here

**Skip it.** Same reasoning as Gates 120E and 122E, and one addition:

```text
1  a read route needs a session to scope by, and /current-user 401s for
   everybody, so the authenticated branch is unreachable and untestable
2  the table will hold zero rows, so the route's only behaviour is `no_profile`
3  four tribal-profile routes already exist behind the dev header, and adding a
   fifth on a different dependency would leave two profile surfaces with two
   different auth stories
```

The third is specific to this gate and is the strongest of the three.

## Implementation constraints carried out of this survey

```text
1  migration 0031 creates nf_tenant_beta_profiles; 0003's table is untouched
2  organization_id anchors; tenant_id and customer_org_id are text labels with
   no foreign key
3  organization_profile_id is refused as an anchor, not ignored
4  the Core sa.Table restates every CHECK constraint (Gate 119C's defect)
5  archive by setting archived_at; no DELETE path exists
6  operating_states drives state matching; a mailing address never does -
   Gate 103's INFERENCE_PROHIBITED already names this and it must be enforced
7  unknown stays unknown; nothing infers recognition, geography, or class
8  production writes require customer_auth_live AND verified operational binding
9  bridge Gate 103's vocabularies - RECOGNITION_STATUSES, APPLICANT_CLASSES,
   DIGEST_FREQUENCIES, FACT_STATUSES - import, never restate
10 every new conjunct both derived and injectable
11 no API route; document why
```
