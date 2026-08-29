# 625 — Gate 114: readiness delta

What changed, what did not, and the sentence to refuse.

## The sentence to refuse

> "NativeForge has a customer persistence spine, so customer data can be
> persisted now."

The first clause is true. The second does not follow and is false. A contract
over persistence is not persistence, and none of the eight lanes is operational.

## What moved

```text
                                          before   after   why
customer persistence contract              none    true    Gate 114B/C/D
capability lanes modelled                  0       8       new
lanes with schema                          n/a     2       detected
lanes under RLS                            n/a     2       detected
lanes with a complete write path           n/a     1       detected
lanes operational                          n/a     0       auth blocks every one
persistence spine sequence                 none    8 steps derived, not listed
binding store readiness spine position     none    1 of 8  new field
```

## What did not move

Every one of these was false before Gate 114 and is false after it:

```text
customer_persistence_live                 no lane is operational
customer_auth_live                        no provider, no verifier
login_live                                unchanged
operational_awarded_tracking_ready        unchanged
operational_digest_ready                  unchanged
beta_onboarding_ready                     unchanged
document_storage_live                     unchanged
live_source_collection                    unchanged
source_monitoring_live                    unchanged
source_coverage_claimed                   unchanged
tenant_id_write_authority                 false, and structurally so
customer_org_id_write_authority           false, and structurally so
organization_profile_id_write_authority   false, and structurally so
```

## Three definitions became one

Gate 114A found `customer_persistence_live` derived three different ways:

```text
awarded lane   _module_importable("nativeforge.repositories.awarded_grant")
digest lane    False        hard-coded
beta lane      False        hard-coded
```

All three reported `False`; all three were correct; none measured the same
thing. Two were constants that would have gone on saying `False` after
persistence became real — the failure Gate 113 removed from `migration_applied`.
The third was worse, because an empty `repositories/awarded_grant.py` would have
flipped it to `True` with no table, no policy, no anchor and nobody able to
authenticate.

All three now call `build_capability`, which requires seven conjuncts. The
answer is still `False`, and now it is the same `False` for the same reason, and
it can change.

## One rule was tightened

`read_allowed` in the persistence guard now requires the operation to be one the
guard can name. The first version granted a read for an unrecognised operation,
because no capability mapped to `unknown` and none of the schema checks applied
to it. Unknown must never become permissive.

## No migration was added

Gate 114A concluded one was not required and this gate added none. The spine is
a contract over persistence; every fact it needs is already observable from
`db/models.py`, `alembic/versions/` and the repositories directory. Six lanes
need a migration each, and each belongs to its own gate, decided against this
spine rather than ahead of it.

`alembic` head remains **0029**.

## No unsafe write path exists, and this was checked

```text
occurrences of tenant_id in repositories/ or api/            0
occurrences of customer_org_id in repositories/ or api/      0
occurrences of organization_profile_id in repositories/      0
```

The only way an organization reaches a session is
`deps_db.get_org_context_with_db`, which requires `X-NF-Org-Id`, parses it as a
UUID, looks it up in `organizations`, and only then calls `apply_org_rls_gucs`.
A label cannot reach `app.current_org_id` because no code path carries one
there.

That header remains an unauthenticated claim — Gate 112's finding, unchanged.

## Claims this gate does not make

```text
no customer data was written           rows_written is 0 on every surface
no real database row was inserted      no fixture touches a session
no identity provider was called
no URL was fetched
no collector ran
no scraper was activated
no source was monitored
no email was sent
no secret was stored or printed
no live payload was committed
customer auth is not live
login is not live
customer persistence is not live
beta onboarding is not ready
production rollout is not ready
source coverage is not claimed
```

## What the next gate needs

**Customer authentication.** Every lane in the spine lists it as a prerequisite,
so no amount of schema moves any of them, and it is the only thing that unblocks
more than one lane at once.

After it, in order: identity binding persistence (the table exists; it needs a
repository), then tenant profile persistence (which needs nothing but the two
above), then the six lanes that each need a migration of their own.
