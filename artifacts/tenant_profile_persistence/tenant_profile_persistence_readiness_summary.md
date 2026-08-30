# Tenant profile persistence readiness (Gate 123)

## The sentence to refuse

> "Tenant profiles are repository-backed, so beta onboarding can start."

The repository exists and the table holds zero rows. A production
profile write needs `customer_auth_live` and a verified operational
binding, and both are false. A row asserting a tenant's recognition
status while nobody can be authenticated as that tenant is a
fabricated fact in a table, which is worse than an empty table.

## Two profiles, and this gate built the second

```text
nf_tribal_profiles       who this Tribe is when a form is submitted
                         UEI, EIN, SAM, addresses, contacts, narratives
                         table since 0003

nf_tenant_beta_profiles  how this tenant wants NativeForge to behave
                         recognition, operating states, applicant
                         classes, watchlist, digest, routing, alerts
                         table as of 0031
```

Gate 123A found the two share not one column. The Gate 103 contract
already carried every field this gate needed and had nowhere to put
them.

## What moved

```text
tenant beta profile table       none      migration 0031, 8 CHECKs
tenant beta profile repository  none      6 operations
profile validation              none      11 checks, 4 refusals
state source matching           implicit  driven by operating_states
alembic head                    0030      0031
```

## What did not move

```text
tenant_profile_operational                  false
customer_auth_live                          false
login_live                                  false
verified_operational_binding                false
customer_persistence_live                   false
beta_onboarding_ready                       false
production_rollout_ready                    false
production_tenant_profiles_created          0
real_customer_data_written                  0
rows_deleted                                0
rows_in_the_application_database            0
```

## operating_states decides; an address never does

```text
operating_states ["SC"]                      -> SC sources match
service_area "the Pee Dee region"            -> matches nothing
service_area "Columbia, South Carolina"      -> matches nothing
```

The third line is the one worth reading twice. South Carolina is
written in the text and no South Carolina source matches, because
an address is not an operating state. Gate 103 named that refusal;
this gate is the first thing to enforce it against stored data.

A tenant may operate, serve and be eligible in a state it is not
headquartered in. Deriving the second from the first would produce
a plausible answer and the wrong one.

## Unknown stays unknown

```text
unknown             nobody has established this
needs_human_review  somebody looked and could not settle it
verified            established by evidence
tenant_supplied     the tenant told us and we have not checked
demo_fixture        a fixture value, never actionable
```

`demo_fixture` is deliberately outside the actionable set. Every
profile in the fixture file is storable and none is actionable,
which is the distinction the status vocabulary exists to make.

The database enforces the sharpest case: an unknown recognition
status may only carry an unestablished fact status, so a guess
cannot be stored as an established fact.

## The fixture set

```text
cases                        10
storable                     6
production writes permitted  0
production profiles created  0
rows deleted                 0
```

## Why no API route

```text
1  a read route needs a session to scope by, and /current-user
   401s for everybody
2  the table holds zero rows, so the route's only behaviour is
   no_profile
3  four tribal-profile routes already exist behind the dev header;
   a fifth on a different dependency would leave two profile
   surfaces with two different auth stories
```

The third is specific to this gate and is the strongest.

## What the next gate needs

```text
1. customer auth activation   the 11 gates from Gate 121, none of
                              which is code
2. a verified operational     the Gate 120 workflow, once a
   binding                    verifier identity can exist
3. then the first profile     written through this repository, by
                              a tenant admin who can be
                              authenticated as one
```
