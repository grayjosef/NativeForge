# 620 — Gate 113: readiness delta

What changed, what did not, and the one sentence somebody will be tempted to
write after reading that a binding store now exists.

## The sentence to refuse

> "The binding store exists, so customer bindings can be stored now."

The first clause is true. The second does not follow from it and is false. A
table under RLS holding zero rows is a container, not a capability.

## What moved

```text
                                   before  after   why
migration_defined                    n/a    true   revision 0029 is in the repo
migration_revision                   n/a    0029   detected from the directory
migration_applied                   false   false  no database has run it
store_schema_available               n/a    true   new readiness surface
store_contract_available             n/a    true   new readiness surface
store_writable                       n/a    false  nothing has created the table
operational_binding_storage_ready    n/a    false  Gate 110's three refusals hold
demo_binding_storage_ready           n/a    false  refused unconditionally
```

## What did not move

Every one of these was false before Gate 113 and is false after it:

```text
customer_auth_live                       nobody can authenticate
customer_persistence_live                no provisioned database
verified_operational_identity_binding    none exists
operational_binding_storage_allowed      the decision still refuses
beta_onboarding_ready                    unchanged
production_rollout_ready                 unchanged
tenant_id_is_rls_authority               false, and structurally so
customer_org_id_is_rls_authority         false, and structurally so
organization_profile_id_is_rls_authority false, and structurally so
```

## The constant that became a measurement

Gate 110's decision service reported `"migration_applied": False` as a
hard-coded literal. That was **accidentally correct**: no migration existed and
no database existed, so the only honest answer happened to be the one asserted.

It would have become a lie the moment revision 0029 landed. Gate 113 split it
into two facts that are measured separately:

```text
migration_defined   read off alembic/versions - is the revision file here?
migration_applied   derived from a reported database revision - has anything
                    actually run it?
```

The versions directory is injectable so a test can point at an empty one and
observe the negative branch; without that, `migration_defined: False` would be
unreachable in a repository that contains the migration, and an unreachable
branch is an untested one.

`migration_applied` was also in the decision service's list of values asserted
to be constantly `False`. That check would have fired on a correctly-applied
migration — the invariant enforcing the very defect it was meant to catch. It
was removed and replaced with relationships between the measurements:

```text
migration_applied_without_a_defined_migration
migration_defined_without_a_revision
migration_revision_without_a_defined_migration
operational_storage_permitted_before_the_migration_is_applied
storage_allowed_from_a_table_existing_without_a_verifier
```

## One rule was tightened

`operational_binding_storage_allowed` was `migration_safe_now`. It is now
`migration_safe_now and migration_applied`.

These were the same value only while no binding table could exist. "The
preconditions for acting are met" and "there is somewhere to write" are
different facts, and storing into a table no database has created is not
permitted by the first being true.

Gate 110's reachability test — which exists so a refusal that can never lift is
not mistaken for a decision — now supplies `database_revision="0029"` and still
asserts the permitted branch is reachable. A second test asserts the same inputs
*without* a database revision are refused.

## The persistence guard learned where a binding came from

Before this gate the only binding the guard could see was one a caller handed
it, so a dict saying `verified_binding` was indistinguishable from a fact. Three
provenances are now named:

```text
binding_store_record     Gate 113's store accepted it
binding_contract_object  Gate 109's service derived it
caller_asserted          an unrecognised shape - somebody typed it
absent                   no binding at all
```

This loosens nothing, and cannot: `write_allowed` already required
`not binding_required`, so no binding of any provenance has ever granted a write
at that surface. What it fixes is the reporting — and a caller-asserted binding
now produces a named blocked reason instead of quietly satisfying a requirement.

## Claims this gate does not make

```text
no customer data was written           rows_written is 0 on every surface
no rows exist                          the table is empty and stays empty
no source was contacted                no collector, scraper or monitor ran
no secret was stored or printed
no live payload was committed
customer auth is not live
customer persistence is not live
beta onboarding is not ready
production rollout is not ready
```

## What the next gate needs

In order, and none of them is unblocked by anything Gate 113 did:

```text
1. customer auth        so that somebody can be a verifier
2. customer persistence so that there is a provisioned database to apply 0029 to
3. a verified binding   produced by 1 and 2, stored under 3's own guard
```

Until then the store is a specified, tested, reversible, empty table, and the
readiness surface says so in those words.
