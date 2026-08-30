# 655 — Gate 120: readiness delta

What changed, what did not, and the sentence to refuse.

## The sentence to refuse

> "The binding repository exists, so tenants can be bound."

A repository is somewhere to put a verified binding. A verified binding names
the identity that verified it, and `verified_by_identity_id` references
`nf_identities` — a verified OIDC subject. **Eleven of sixteen** activation
gates are unsatisfied, so no OIDC subject can be verified, so no verifier
identity exists to name.

A production verified binding is not merely unauthorized today. It is
unconstructible.

## What moved

```text
                                     before          after
binding repository                   none            six operations, DB-backed
verified binding workflow            none            authorization -> contract
                                                     -> repository, in order
write_allowed                        unconsumed      acted on
identity_binding repository_available false           true
identity_binding write_path_available false           true
revocation                           a modified dict an UPDATE that keeps the row
binding store readiness fields       3               6
```

## What did not move

```text
verified_operational_binding           false
customer_auth_live                     false
login_live                             false
provider_configured                    false
secret_present                         false
customer_persistence_live              false
operational_binding_storage_ready      false
store_writable                         false
beta_onboarding_ready                  false
production_rollout_ready               false
operational_awarded_tracking_ready     false
operational_digest_ready               false
source_monitoring_live                 false
source_coverage_claimed                false
production verified bindings created   0
real customer rows written             0
rows in the application database       0
alembic head                           0030, unchanged
```

## organization_id is still the only authority

```text
organization_id          UUID, foreign key, the RLS predicate's anchor
tenant_id                text label, no foreign key, never selects alone
customer_org_id          text label, same
organization_profile_id  refused, not ignored
```

A test passes only a `tenant_id` to a read and asserts nothing comes back. A
second offers an `organization_profile_id` as the anchor and asserts the named
refusal. The artifact writer scans every payload for a fixture label appearing
in an `organization_id` field and refuses to write if one does.

## The refusal moved rather than disappearing

The interesting change is in `identity_binding_persistence`'s blocked reasons:

```text
before  no_repository_can_address_this_capability
after   no_customer_auth_so_nobody_owns_the_row
```

Same `operational: False`, different reason. Before this gate the lane was
blocked by something engineering had not built; now it is blocked by something
an owner has to supply. That is the whole delta, and it is worth exactly as much
as that sentence and no more.

## A declared-versus-derived defect, caught before it landed

`repository_available` was measured by probing for a **filename**:

```python
repository_available = (repos / f"{CAPABILITY_REPOSITORIES[name]}.py").is_file()
```

A repository built as a service would have been invisible to it — the detector
measured a naming convention rather than whether anything could address the
table. Patched carelessly it would have flipped all eight lanes at once.

The fix detects by import, per capability, with only
`identity_binding_persistence` pointed at the new module. A test asserts the
other six repository-less lanes stay false.

## The spine reports the repository without recommending past auth

```text
identity_binding_repository_available   true
verified_binding_workflow_available     true
verified_operational_binding            false
next_gate_recommendation                customer_authentication
```

Auth still blocks every lane at once, so it is still the recommendation.
Reporting the repository without changing the recommendation is the honest
version: the next gate will find one thing already built.

One consequence worth naming: with auth forged, `tenant_profile_persistence` is
no longer *operational out of sequence*, because the prerequisite it was ahead
of is now built. Gate 114's test for that reporting path now forges the
disagreement rather than relying on it occurring naturally — a path that only
ever fired by accident is one nobody has tested.

## Gate 120E: no API route, and why

```text
1  a read route needs a session to scope by. /current-user is the only route
   that enforces and it 401s for everybody, so an authenticated binding read
   is unreachable and its permitted branch untestable.

2  the table is empty. A route returning `no_binding` for every caller forever
   is a route whose only behaviour is its refusal.

3  a route is a surface. Adding one before a session can reach it means the
   first thing to exercise it will be a real browser with a real cookie -
   the worst place to discover a scoping mistake.
```

The repository and workflow are the safer boundary and are testable today.
Recorded as a decision, not left as an omission.

## Nothing was written, called, or claimed

```text
production verified bindings created   0
real customer rows written             0
real users created                     0
production sessions created            0
rows in the application database       0
live provider called                   no
live source called                     no
URL fetched                            no
collector executed                     no
scraper activated                      no
email sent                             no
secret printed or committed            no
```

Four of eight fixture cases write a row. Every one is a demo fixture in an
in-memory database created inside the case and discarded when it ends.

## What the next gate needs

```text
1. customer auth activation   11 of 16 gates. Everything below waits on this
                              and nothing else does.

2. a verifier identity        an nf_identities row from a verified OIDC
                              subject. The repository is ready for one.

3. a database with 0029       store_writable is false: the migration is
                              defined and no runtime database has applied it

4. the remaining six lanes    each needs a repository of its own; this gate
                              built the pattern for them
```

Item 1 is the only one that unblocks more than one thing, and it has been the
answer since Gate 114. What changed is that the thing waiting behind it is now
built.
