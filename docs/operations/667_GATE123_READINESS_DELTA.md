# 667 — Gate 123: readiness delta

What changed, what did not, and the sentence to refuse.

## The sentence to refuse

> "Tenant profiles are repository-backed, so beta onboarding can start."

The repository exists and the table holds zero rows. A production profile write
needs `customer_auth_live` **and** a verified operational binding, and both are
false — the same two facts Gates 115–122 have measured false throughout.

A row asserting a tenant's recognition status while nobody can be authenticated
as that tenant is a fabricated fact in a table. That is worse than an empty
table, because a table nobody trusts still gets read by somebody eventually.

## The finding: there were two tenant profiles all along

```text
nf_tribal_profiles       who this Tribe is when a form is submitted
                         22 columns, table since 0003, repository since Sprint 0
                         UEI, EIN, SAM, addresses, contacts, narratives

nf_tenant_beta_profiles  how this tenant wants NativeForge to behave
                         28 columns, table as of 0031
                         recognition, operating states, applicant classes,
                         watchlist, digest, routing, alerts
```

They share **not one column**. Gate 103 built the behaviour contract and it has
had nowhere to be stored since; Gate 114 listed `tenant_profile` as a
schema-backed lane, and the schema it was backed by is the other profile.

Merging them would have produced a 38-column table where half the rows carry a
`fact_status` and half do not — because the identity profile has no such column
and never needed one.

## What moved

```text
                                  before    after
tenant beta profile table         none      0031, 28 columns, 8 CHECKs
tenant beta profile repository    none      6 operations
profile validation                none      11 checks, 4 bridged refusals
state source matching             implicit  driven by operating_states, and a
                                            reported `decided_by`
alembic head                      0030      0031
```

## What did not move

```text
tenant_profile lane operational        false
customer_auth_live                     false
login_live                             false
verified_operational_binding           false
customer_persistence_live              false
beta_onboarding_ready                  false
production_rollout_ready               false
production tenant profiles created     0
real customer data written             0
rows deleted                           0
rows in the application database       0
```

## operating_states decides; an address never does

```text
operating_states ["SC"]                    -> SC sources match
service_area "the Pee Dee region"          -> matches nothing
service_area "Columbia, South Carolina"    -> matches nothing
```

The third line is the case this gate turns on. South Carolina is written in the
text and no South Carolina source matches, because an address is not an
operating state. A tenant may operate, serve and be eligible in a state it is
not headquartered in.

Gate 103 named that refusal; this gate is the first thing to enforce it against
stored data, at three layers — the column is JSON so a comma cannot make a
state, the repository refuses a delimited string, and the repository refuses a
service area with no operating states rather than parsing one out of it.

## Unknown stays unknown

```text
unknown             nobody has established this
needs_human_review  somebody looked and could not settle it
verified            established by evidence
tenant_supplied     the tenant told us and we have not checked
demo_fixture        a fixture value, never actionable
```

`demo_fixture` is deliberately outside `ACTIONABLE_FACT_STATUSES`. Every profile
in this gate's fixture file is storable and **none** is actionable — a fixture
that reached `profile_ready_for_matching` would have proved the fixture path and
quietly broken Gate 103's rule.

The database enforces the sharpest case: an unknown recognition status may only
carry an unestablished fact status, so a guess cannot be stored as an
established fact.

## Readiness: a new fact, no lane flip

`tenant_profile_persistence` already reported `write_path_available: True`,
because `repositories/tribal_profiles.py` satisfies the capability service's file
probe. Gate 123 adds a *second* profile with a *second* repository, and the
honest reporting is a new named fact rather than a flipped lane:

```text
tenant_beta_profile_repository_available   false -> true
tenant_beta_profile_table                  nf_tenant_beta_profiles
tenant_beta_profiles_stored                0
```

Folding the two into one `repository_available` would have reported a write path
for a table that had none — the Gate 120 defect, in the other direction.

`operational` stays false for the reason it has since Gate 114: nobody can own
the row.

## A sixth substring-versus-meaning false positive

The test asserting the repository never deletes grepped for `sa.delete` and
found it — in the docstring explaining that there is no delete path.

It now parses the module with `ast` and looks for a `Call` whose attribute is
`delete`. It also asserts the prose is still present, so the test would catch a
real delete rather than the explanation of one.

Sixth instance in this campaign, second inside a test of mine.

## Gate 123E: no API route, and why

```text
1  a read route needs a session to scope by, and /current-user 401s for
   everybody
2  the table holds zero rows, so the route's only behaviour is `no_profile`
3  four tribal-profile routes already exist behind the dev header; a fifth on
   a different dependency would leave two profile surfaces with two different
   auth stories
```

The third is specific to this gate and is the strongest of the three. Recorded
as a decision, not an omission.

## Nothing was written, called, or claimed

```text
production tenant profiles created  0
real customer data written          0
rows deleted                        0
rows in the application database    0
live provider called                no
live source called                  no
URL fetched                         no
collector executed                  no
scraper activated                   no
email sent                          no
secret or env value printed         none
```

The artifact writer refuses on three checks: forbidden field names, configured
`OIDC_*` values, and — new in this gate — any payload claiming an inference the
campaign prohibits. A tenant profile artifact is made of claims about a real
government, so the danger is not a leaked credential but a fabricated fact.

## What the next gate needs

```text
1. customer auth activation   the 11 gates from Gate 121, none of which is code
2. a verified operational     the Gate 120 workflow, once a verifier identity
   binding                    can exist
3. then the first profile     written through this repository, by a tenant
                              admin who can be authenticated as one
```

Steps 1 and 2 are unchanged and are not code. What changed is that the thing
waiting behind them is built: a table, a repository, a validation, and a fixture
set that proves the address rule holds.
