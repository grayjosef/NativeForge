# 766 — Gate 147: the verified operational binding boundary, surveyed

Read-only. No binding was written, no approval was granted, and the real
organization was counted but never addressed.

## The measured state

```text
verified_operational_binding                      false
binding rows total                                1
  org                                             demo
  binding_status                                  demo_fixture
  is_demo                                         1
  names a verifier                                no
  active                                          yes
binding rows for the real organization            0
rows with binding_status = 'verified_binding'     0
rows naming a verifier                            0

organizations.org_type  demo org -> 'demo'   real org -> 'real'
```

One row exists and it asserts nothing. `demo_fixture` is not in
`VERIFIER_REQUIRED_STATUSES`, so it makes no claim that anybody verified
anything — which is exactly what a fixture should be.

## Why it is false, and it is not one reason

Five independent refusals stand between today and `verified_operational_binding`,
and **any one of them alone** is sufficient:

```text
1  AUTHORIZED_REAL_ORGANIZATION_IDS is empty
     and empty is the decision, not an oversight. Mayhem's standing
     authorization refuses "real org activation" and refuses binding to
     aaaaaaaa-… by name.

2  no approval object exists
     five fields are required - organization_id, authorized_by,
     authorization_scope, environment, recorded_at - and none is supplied

3  the demo organization is categorically refused
     demo_organization_is_never_a_verified_operational_binding, derived from
     organizations.org_type and not from a caller's label

4  the real organization is refused by name
     organization_is_the_explicitly_refused_real_org, a second refusal on top
     of not being in the authorized list

5  customer_auth_live is false
     production_verified_binding_requires_live_customer_auth, in the workflow
     service. Gate 146 measured customer_auth_live false with the second
     person never having signed in.
```

That layering matters. A survey that reported one blocker would invite somebody
to clear it and expect the lane to move.

## What exact evidence would make it true

All of the following, together:

```text
an organization that is neither demo nor the refused real org
  org_type read from the database, never from the caller

an approval object with all five fields
  authorization_scope real_org_binding_activation  for local/dev/test
  authorization_scope production_binding_activation for production

that organization's id present in AUTHORIZED_REAL_ORGANIZATION_IDS
  a reviewed code change somebody reads - not an environment variable, and
  not the injectable test set, which strips both the demo and real ids

a qualified verifier principal
  role in {platform_admin, tenant_admin}, authenticated, verified-org status

customer_auth_live true
  because a verified binding is a row asserting somebody verified something,
  and writing one while nobody can authenticate leaves that assertion with no
  verifier behind it

no duplicate or ambiguous active binding
  two active rows for one organization is a conflict a person resolves, not a
  coin toss the reader makes on their behalf

NF_REAL_ORG_BINDING_ACTIVATION_REVOKED unset
  the one environment variable in the path, and it can only revoke
```

## Can the demo organization ever satisfy a production verified binding?

**No.** Not in any environment, with any approval, with any principal. The
refusal is categorical and derived from `organizations.org_type`, which the
database says is `demo`.

This is the fifth conflation Gate 145 named — *the demo organization is not a
customer organization* — enforced here against the organization rather than
against a label somebody passed in. Gates 110–113 spent four gates on exactly
this substitution.

## Is the real organization authorized?

No, and it is refused twice over: it is absent from an empty authorized list,
and it is refused by name on top of that. Gate 137G's own test found the first
version of the injectable override reaching it — listing `aaaaaaaa-…` in the
injected set approved a real-org binding and wrote the row. An escape hatch
that reaches the one organization the module exists to refuse is not an escape
hatch; it is the hole. Both ids are now stripped from the injectable set.

## Is `customer_auth_live` a prerequisite?

For a **production** verified binding, yes — and it is false. For the demo
fixture that exists today, no, because a fixture asserts no verification.

The dependency runs one way only. `customer_auth_live` becoming true clears one
of five refusals and moves nothing else.

## What can safely be proved in this gate

```text
the refusal matrix            every refusal, reachable and exercised
the dry-run decision          blockers named, nothing written
the demo-org refusal          against the database classification
the real-org refusal          by name, without addressing the row
the approved branch           against an injected fixture organization that is
                              neither the demo org nor the real one - Gate
                              137's hermetic path, kept reachable so the
                              refusals above it stay falsifiable
the caller-label refusal      tenant_id, customer_org_id,
                              organization_profile_id, profile_id, subject and
                              email refused as authority by name
```

## What must remain blocked

```text
verified_operational_binding   false
customer_auth_live             false
controlled_customer_pilot      false
production_rollout             false
real organization              untouched, zero rows, never addressed
mutation path                  disabled; no approval object exists to enable it
```

## What Gate 147 adds that Gate 137 did not have

Gate 137 built the boundary and proved it refuses. What is missing is a single
place that answers *"how far is this from true, and who moves it"* — the
equivalent of what Gate 146 did for `customer_auth_live`.

```text
Gate 137 has      a decision function, refusals, invariants, artifacts
Gate 147 adds     a checklist that reports all five refusals at once, which
                  are code and which are decisions, the owner of each, and the
                  one next human action
```

The boundary service itself needs no weakening and will get none. The two gaps
worth closing in it are that it does not read `customer_auth_live` (that guard
lives in the workflow service, one layer away) and does not consult the
duplicate/ambiguous state (that lives in the repository, another layer away).
The checklist gathers all three layers so no reader has to know they are three.

## Exact human approval and action required later

```text
1  the second-person event               Gate 146; unlocks customer_auth_live
2  a real customer organization exists   not the demo org, not aaaaaaaa-…
3  Mayhem authorizes that organization   a reviewed code change adding its id
                                         to AUTHORIZED_REAL_ORGANIZATION_IDS
4  an approval object is recorded        five fields, correct scope
5  a qualified verifier principal acts   platform_admin or tenant_admin
```

Steps 2 and 3 do not exist yet in any form: there is no real customer
organization in this deployment other than the refused one. That is the honest
distance, and it is further than "one approval away".

## Next

`767` states the boundary, `768` states why demo proof is not production proof,
`769` states the real-org approval requirements, `770` states the delta.
