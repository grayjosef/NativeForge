# 723 — Gate 138: customer persistence survey

Measured before anything was implemented. HEAD `6011b07`.

## Modules named for survey, and what they actually are

```text
customer_persistence_capability_service        PRESENT  nine lanes
org_scoped_customer_persistence_guard_service  PRESENT  the write guard
customer_persistence_spine_decision_service    PRESENT
customer_org_context_dependency                PRESENT  session -> OrgContext
customer_auth_activation_gate_service          PRESENT

tenant_beta_profile_repository_service         ABSENT
award_requirement_proof_repository_service     ABSENT
award_documents_repository_service             ABSENT
```

The three "absent" ones exist under different names, and finding them is part
of the survey rather than a footnote:

```text
tenant_beta_profile   -> tenant_profile_repository_service   (nf_tenant_beta_profiles)
proof/audit           -> award_requirement_proof_audit_repository_service
document metadata     -> award_document_store_repository_service
```

Seventh gate running where a brief names modules by a plausible name nobody
used. Worth noting because Gate 124A found two *detectors* miss real services
for exactly this reason — a probe on a name rather than a capability — and the
capability service now carries a map of the derived answers with that history
written next to it.

## Why `customer_persistence_live` is currently false

One reason, and it is the same reason for every lane that could otherwise work.

```python
# customer_persistence_capability_service.build_capability
operational = bool(
    write_path_available
    and (customer_auth_live or not customer_auth_required)
    and not blocked_reasons
)
```

`CAPABILITY_REQUIRES_AUTH` is `True` for all nine lanes, `customer_auth_live` is
false, so `operational` is false everywhere and
`customer_persistence_live = any(operational)` is false.

Measured, the full matrix:

```text
lane                              sch rls anc repo ctr write read oper
tenant_profile_persistence         T   T   T   T    T    T     T    F
awarded_grants_persistence         T   T   T   T    T    T     T    F
award_requirements_persistence     T   T   T   T    T    T     T    F
proof_audit_persistence            T   T   T   T    T    T     T    F
document_library_persistence       T   T   T   T    T    T     T    F
identity_binding_persistence       T   T   T   T    T    T     T    F
tenant_digest_persistence          F   F   F   F    T    F     F    F
source_watchlist_persistence       F   F   F   F    F    F     F    F
beta_onboarding_persistence        F   F   F   F    F    F     F    F
```

**Six lanes have a complete write path and are blocked by exactly one thing:**

```text
no_customer_auth_so_nobody_owns_the_row
```

Three lanes are genuinely absent — no table at all — and stay false honestly.

## The blocker names a fact that is already true

`no_customer_auth_so_nobody_owns_the_row` is reaching for *somebody is
accountable for this row*. Measured against the dev database right now:

```text
Gate 132 binding evidence
  identity_rows                  1
  active_membership_rows         1
  resolvable_identities          1
  org_binding_passed             TRUE
  callback_session_validated     TRUE

Gate 133 role mapping evidence
  mapped_identities              1
  role_mapping_passed            TRUE
  role_mapping_source            nf_org_memberships
  cookie_claim_can_override_membership   False
  email_domain_can_map_a_role            False
```

An identity resolves to an organization through a membership row, a real
session was validated, and the role comes from the membership row rather than
from a cookie claim or an email domain. **Somebody is accountable.**

`customer_auth_live` is false because `invite_binding_passed` is false — which
is about how a *second* member was authorized. It says nothing about whether the
first member owns their own rows.

This is precisely the shape Gate 134F found and fixed one layer up:

> "`route_org_resolution_enforced` required `customer_auth_live` … the conjunct
> was correct when written — no principal could exist while customer auth was
> off. Gate 132 made a principal exist and Gate 133 proved it in a browser,
> both with `customer_auth_live` false throughout. So the conjunct was asking
> for the wrong fact."

Same remedy, and the same shape of remedy: ask for the fact directly, keep
`customer_auth_live` as a *sufficient* condition rather than a necessary one.
`or`, never replacement — a live customer auth certainly means somebody is
accountable.

## Which lanes have route wiring

```text
route modules referencing any lane table   0
```

That looks damning and is not the whole answer, because routes reach tables
through services rather than by naming them.

```text
tenant_profile lane (nf_tribal_profiles)
  tribal_profile_routes.py, prefixes /v1/nf/demo/orgs and /v1/nf/real/orgs
  wired to require_demo_org_session / require_real_org_session   Gate 134
  _same_org(org_id, ctx) - the path org must match the session org

the five award and beta lanes
  no routes at all
```

Measured live:

```text
GET /v1/nf/demo/orgs/{demo}/tribal-profile                     401
     … with a forged X-NF-Org-Id header                        401
```

The route fails closed, and the dev header cannot open it — Gates 134 and 135
removed the chain that would have. That is real route-level proof for one lane.

So: **one lane route-live, five repository-live and route-missing.** Not faked,
and reported that way.

## Which have repository proof only

All five brief-named lanes have complete repository APIs:

```text
tenant beta profile   tenant_profile_repository_service
                        prepare_profile_write, upsert_tenant_profile,
                        get_tenant_profile, list_tenant_profiles,
                        archive_tenant_profile
awarded grants        awarded_grants_repository_service
                        prepare_award_write, create_awarded_grant,
                        get_awarded_grant, list_awarded_grants,
                        archive_awarded_grant
award requirements    award_requirements_repository_service
                        + list_requirements_for_organization
proof / audit         award_requirement_proof_audit_repository_service
                        + supersede_proof_event, archive_proof_event
document metadata     award_document_store_repository_service
                        + list_documents_for_organization
```

Every one is `archive_*`, not `delete_*`. So cleanup is archival, which is the
"mark it as a test artifact" branch the brief allows rather than the "clean it
up" one — and it is the right shape here, because these tables are audit
surfaces where a hard delete would be the wrong primitive to add for a smoke
test's convenience.

## The gap nothing above closes

Nothing in the capability matrix has ever written a row.

```text
build_capability_matrix reads   the models file, the migrations, imports
build_capability_matrix reports rows_written: 0
                                persisted: False
                                (constants, in every branch)
```

It measures whether a lane *could* work, from schema and imports. It has never
measured whether one *does*. A lane can have all five components and a broken
INSERT, and the matrix would report `write_path_available: True`.

That is the defect this gate is actually for: **`customer_persistence_live` must
come from a round trip, not from five import checks and a boolean.**

## Whether the demo org can write and read fixture-labelled rows

Not yet proved. The repositories exist, the guard exists, and no test or script
has ever driven write → read-by-organization_id → cross-org-refusal → cleanup
through them as one sequence against a live database.

Building that sequence, and making `customer_persistence_live` read its result,
is 138B/C/D.

## Whether `invite_binding_passed` must block a persistence smoke

**No.** It gates `customer_auth_live`, which gates the claim that customer
authentication is live for real Tribes. A demo organization's owner writing a
fixture-labelled row into their own organization needs an accountable
principal, not a second member.

Blocking on it would also be circular in effect: the invite flow needs a second
person to log in, and nothing about persistence changes whether they can.

## Whether `verified_operational_binding` must block demo/dev persistence

**No, and the current contract agrees.** Gate 137 measured what consumes it:

```python
# award_requirements_repository_service
if production_write and not verified_operational_binding:
    blocked.append(
        "production_requirement_write_requires_a_verified_operational_binding"
    )
```

`production_write`, specifically. A demo/dev fixture-labelled write is not a
production write, and Gate 113's contract refuses a verified binding on a demo
organization at all — so requiring one for demo persistence would make demo
persistence permanently unreachable. That is an unsatisfiable conjunct, which
is the family of defect Gate 134F removed.

Production persistence stays false and keeps requiring it.

## What can safely become true in this gate

```text
customer_persistence_live       TRUE, labelled controlled_dev_demo, IF a real
                                round trip proves it
repository_persistence_live     per lane, from a measured round trip
route_persistence_live          one lane, measured at the route
production_persistence_ready    FALSE, unchanged
```

And what must not move:

```text
customer_auth_live              governed by its own gates. Untouched.
verified_operational_binding    false. Untouched.
object_store_configured         false. No body writes, no store contact.
awarded_operational_tracking    false until Gate 139's facts exist.
```

## Exact blockers remaining after this gate

For `customer_persistence_live` in **controlled dev/demo**: none, if the round
trip passes. That is what 138C measures rather than asserts.

For **production** persistence, three, none of them this gate's:

```text
customer_auth_live true          Gate 136's second-person invite event
verified_operational_binding     Gate 137's two-part owner decision
object_store_configured          document bodies, not touched here
```

And one engineering gap, named rather than fixed: five of six ready lanes have
no routes. Repository-live is not customer-usable, and this gate will say so
per lane rather than averaging it into one word.
