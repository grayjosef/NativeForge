# 665 — Gate 123B: the tenant beta profile repository

```text
alembic/versions/0031_nf_tenant_beta_profiles.py
src/nativeforge/services/tenant_profile_repository_service.py
```

## Two tenant profiles, and this is the second

```text
nf_tribal_profiles       who this Tribe is when a form is submitted
                         legal_name, entity_type, uei, ein,
                         sam_registration_status, addresses, contacts,
                         certifications, standard_narratives
                         table since 0003, repository since Sprint 0

nf_tenant_beta_profiles  how this tenant wants NativeForge to behave
                         recognition_status, operating_states, service_area,
                         applicant_classes, programs, departments,
                         priority_topics, excluded_topics,
                         source_watchlist_preferences, digest_frequency,
                         routing_rules, custom_alerts
                         table as of 0031
```

Gate 123A found the two share **not one column**. Gate 103's contract already
carried every field this gate needed, and had nowhere to put them.

They differ in the way that decides a schema. Gate 103 tracks a `fact_status`
per field, because a recognition status somebody guessed and one somebody
confirmed are different objects. `nf_tribal_profiles` has no such column, and
merging would produce a 38-column table where half the rows carry a fact status
and half do not.

Alembic head moves **0030 → 0031**.

## organization_id anchors; labels never select

```text
organization_id          UUID, foreign key, the RLS predicate's left side
tenant_id_label          text, no foreign key. Travels with the row.
customer_org_id_label    text, optional. Same.
organization_profile_id  refused outright
```

The label columns are named `*_label` on purpose. Gate 113's docstring records
why: a label with a foreign key becomes an identity space by accident, and the
name is the cheapest reminder that this one is not an identity.

`organization_profile_id` is **refused rather than ignored**. Silently dropping
it would let a caller believe it had been honoured.

## operating_states decides; an address never does

The most consequential rule in the gate.

```text
operating_states ["SC"]                    -> SC sources match
service_area "the Pee Dee region"          -> matches nothing
service_area "Columbia, South Carolina"    -> matches nothing
```

The third line is the one worth reading twice. Gate 103's
`INFERENCE_PROHIBITED` names `operating_state_from_mailing_address` as a
refusal; this is the first thing to enforce it against stored data.

Three enforcements, at three layers:

```text
schema        operating_states is JSON, not text - a state cannot be produced
              by splitting an address on a comma
repository    a service area with no operating states is refused, with the
              reason named rather than the state derived
repository    a delimited string in operating_states is refused outright
```

A tenant may operate, serve and be eligible in a state it is not headquartered
in. Deriving the second from the first produces a plausible answer and the
wrong one, and the wrong one reaches a real government's eligibility.

## Unknown stays unknown, and the database agrees

```text
ck_nf_tenant_beta_unknown_recognition_is_unestablished
  recognition_status <> 'unknown'
  OR recognition_status_fact_status IN ('unknown', 'needs_human_review')
```

A guess cannot be stored as an established fact. The repository refuses it
first, with a named reason; the constraint catches the case the repository gets
wrong. A test inserts around the module and asserts the constraint fires.

Eight CHECK constraints in total, and the Core `sa.Table` restates every one —
Gate 119C shipped a Core table with columns and no constraints, so a test built
a weaker schema than production. Two tests compare the definitions by name.

## Archive, never delete

`archive_tenant_profile` sets `archived_at` and leaves the row. `rows_deleted`
is a constant `0`, and a test **parses** the module rather than grepping it: a
substring search finds `sa.delete` in the docstring that explains there is no
delete path.

`upsert_tenant_profile` archives the previous profile before inserting the new
one. The partial unique index (`WHERE archived_at IS NULL`) makes that the only
safe shape, and it keeps the superseded profile as the thing a digest complaint
gets debugged against.

`list_tenant_profiles` returns archived rows by default, because a listing that
hid them would make an archive indistinguishable from a row that never existed.

## Production writes need two things that are both false

```text
customer_auth_live              false
verified_operational_binding    false
```

Both are required, both are injectable so the permitted branch is reachable in a
test, and both are false in the real environment.

A profile row asserting a tenant's recognition status while nobody can be
authenticated as that tenant is a fabricated fact in a table — worse than an
empty table, because a table nobody trusts gets read by somebody eventually.

Demo fixture writes are permitted and are never production writes. An invariant
refuses any result where `demo_fixture` and `production_write_allowed` are both
true.

```text
rows in the application database        0
production tenant profiles created      0
```
