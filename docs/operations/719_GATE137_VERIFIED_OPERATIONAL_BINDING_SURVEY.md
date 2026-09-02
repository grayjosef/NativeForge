# 719 — Gate 137: verified operational binding survey

Measured before anything was implemented. HEAD `e990722`.

## Numbering, and three modules that do not exist

The brief asked for `719`–`722`. Gate 136 committed 716–717, so 718 is free and
this uses 719–722 as asked. First gate in five with no collision.

Three modules named for survey are absent, as in Gate 135:

```text
customer_identity_repository_service   ABSENT
org_membership_repository_service      ABSENT
customer_auth_current_user_service     ABSENT
```

Their responsibilities live in `dev_org_membership_bootstrap_service`,
`identity_org_session_resolution_service` and `api/auth.py::current_user`. Sixth
gate running where a brief names modules nobody built.

## Why `verified_operational_binding` is currently false

It is not reported by `/api/auth/session` at all — it lives in
`verified_binding_workflow_service`, which no route calls. Derived there:

```python
verified_operational_binding = bool(
    auth_live
    and repository_write_performed
    and repository_result["production_verified_binding"]
    and not repository_result["demo_fixture"]
)
```

`auth_live` is false, so it is false. **That is the only reason.** The direction
matters and is worth stating because it is the opposite of what the brief
assumes: `verified_operational_binding` requires `customer_auth_live`, not the
reverse. It is not in `REQUIRED_AUTH_GATES` and does not block customer auth.

The dev database holds one binding, and it is honest:

```text
organization  bbbbbbbb-…  (demo)
tenant_id     nf-dev-demo-tenant
status        demo_fixture
source        demo_fixture
is_demo       1
verifier      none
```

## Why the demo org cannot satisfy it — and the part that is not true

The claim carried since Gate 113, repeated in Gates 132, 135 and 136, is that
the contract *refuses a verified binding on a demo organization*. Measured, it
does not. It refuses a verified binding on a row the **caller labelled** demo.

```python
# tenant_customer_org_binding_repository_service.prepare_insert
def prepare_insert(..., is_demo: bool = False, ...):
    demo_fixture = bool(is_demo or status == DEMO_STATUS)
    if demo_fixture and status in VERIFIER_REQUIRED_STATUSES:
        blocked_reasons.append("demo_fixture_cannot_be_a_verified_binding")
```

`is_demo` is a **parameter**. Nothing reads `organizations.org_type`. So:

```text
insert_binding(
    organization_id = bbbbbbbb-…   the demo organization
    binding_status  = verified_binding
    is_demo         = False        the caller's word for it
)
-> rows_written              1
-> production_verified_binding TRUE
-> demo_fixture              False
-> blocked_reasons           []
-> invariant_failures        []
-> stored row: organization_id=bbbbbbbb-…, is_demo=0, verified_binding
```

Measured, not reasoned. The demo organization now carries a production verified
binding, every invariant passes, and the row is in the **wrong RLS partition** —
`is_demo=0` against a demo organization, so the predicate

```sql
organization_id = current_setting('app.current_org_id')::uuid
AND is_demo = current_setting('app.current_org_is_demo')::boolean
```

will not match it for a demo session and will not match it for a real one
either. A row nothing can see is a row nothing can revoke.

This is the exact defect `dev_org_membership_bootstrap_service` was written to
avoid, in Gate 132, and said so:

> "`is_demo` is **derived**, and there is no parameter for it. That is the whole
> argument for this module existing rather than a caller writing the INSERT …
> a caller-supplied `is_demo` is a caller-supplied choice of which partition a
> row lands in."

Gate 120B's repository, written eight gates later, took the parameter.

And the workflow above it makes the same substitution one level up:

```python
is_demo=bool((principal or {}).get("is_demo_principal"))
```

The **principal's self-description** decides which partition an organization's
binding row lands in. A principal is not an organization.

So the honest answer to "why can the demo org not satisfy verified operational
binding" is: **today, it can.** Closing that is 137B/D.

## What facts a real-org binding must prove

```text
organization_id      the anchor, uuid-shaped, and the ONLY authority
is_demo              FALSE, derived from organizations.org_type
binding_status       verified_binding
verified_by_identity_id + verified_at   both, per migration 0029's CHECK
verifier             an authenticated principal with a verified org claim
                     holding platform_admin or tenant_admin
approval             ← does not exist. See below.
```

## Whether the existing repository can insert a verified binding

Yes, and this is the finding that makes this gate urgent rather than tidy.

With a fully-qualified verifier principal and `customer_auth_live` injected
true, against the **real** organization:

```text
authorization_allowed         True
repository_write_allowed      True
repository_write_performed    True
verified_operational_binding  TRUE
rows_written                  1
blocked_reasons               []
stored row: organization_id=aaaaaaaa-…, verified_binding, is_demo=0
```

Nothing in the chain checks which organization it is. Authorization is
role-based only:

```text
VERIFIER_ROLES            {platform_admin, tenant_admin}
OPERATIONAL_AUTH_STATUSES {authenticated_verified_org}
```

`aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee` is not refused by name, is not checked
against an authorized list, and needs no approval object of any kind.

**The only thing holding a real-org production binding shut today is
`customer_auth_live` being false** — via
`production_verified_binding_requires_live_customer_auth`. Gate 136 made
`customer_auth_live` reachable in minutes. So that guard is about to open, and
when it does there is nothing behind it.

That is why 137C exists and why it is not optional.

## Whether membership evidence can support verified binding

Partly, and less than it looks.

```text
org_claim_verified   a principal FIELD. Nothing verifies it against a row.
membership evidence  Gate 132's binding evidence and Gate 136's invite
                     evidence both read real rows, and neither is consulted
                     by the binding authorization at all.
```

So the strongest membership facts in the system — an identity resolving to an
organization through a membership row, and a membership that came through a
completed invite — are not inputs to the decision that writes a verified
binding. The decision reads a boolean the caller supplied instead.

Not fixed in this gate beyond being recorded and refused where it matters: the
preparation service requires the organization to be classified from the
database, which is the half that pairs with RLS. Wiring membership evidence into
binder authorization is a larger change and is named as the next gate's work.

## What approval is required to touch the real org

Today: **none.** That is the gap.

The precedent exists and is two gates old.
`customer_auth_owner_activation_decision_service` records a decision checked per
call against organization, provider and environment, refuses
`aaaaaaaa-…` by name, refuses production, reads one environment variable that
can only revoke, and has no branch that returns True for production rollout.
That is the shape 137C copies, for a different subject.

What Mayhem has authorized so far, verbatim scope from Gate 135:

```text
demo org only
organization_id: bbbbbbbb-cccc-dddd-eeee-ffffffffffff
environment: dev/demo
provider: Google
controlled customer-auth activation only

NOT authorized: production rollout, controlled customer pilot, real org
activation, live customer data, binding to aaaaaaaa-…
```

`real org activation` is refused explicitly. So the real-org binding path may be
**built** and must not be **activated**, which is what this gate does.

## Whether a hermetic real-org fixture can prove the path

Yes, and it is the only way to prove it without touching the real organization.

A temp database, an `organizations` row with `org_type = 'real'` and an id that
is **not** `aaaaaaaa-…`, an approval object scoped to that id, a real verifier
identity. Every branch of the real-org path becomes reachable, and the runtime
real organization is never opened.

The fixture id must differ from the real one, or the test proves the refusal is
absent rather than that the path works. Both are needed: the fixture org for the
path, `aaaaaaaa-…` for the refusal.

## How `customer_auth_live` should treat verified binding

Unchanged. `verified_operational_binding` is not in `REQUIRED_AUTH_GATES` and
must not be added, for a reason that is structural rather than convenient:

```text
verified_operational_binding  needs  customer_auth_live
customer_auth_live            needs  ...16 gates, none of them this one
```

Adding it would close the loop Gate 134F spent a gate opening —
`customer_auth_live` needing something that needs `customer_auth_live` is
unsatisfiable, and every "not ready" claim above it becomes unfalsifiable.

What *does* consume it, correctly, is production writes:

```python
# award_requirements_repository_service
if production_write and not verified_operational_binding:
    blocked.append(
        "production_requirement_write_requires_a_verified_operational_binding"
    )
```

So the demo/dev `customer_auth_live` reached in Gate 136 is not production
readiness and must not read as it. 137E reports the two separately rather than
folding either into the other.

## Exact remaining blocker after this gate

```text
verified_operational_binding   false
because                        no verified binding row exists for any
                               non-demo organization, and none may be
                               written for aaaaaaaa-… without explicit
                               owner approval that does not exist yet
```

Two things are needed, in order, and neither is code:

1. `customer_auth_live` true — Gate 136's second-person invite event.
2. An explicit owner decision authorizing real-org binding activation.

## What can be safely built now

```text
verified_operational_binding_preparation_service
    derives is_demo from organizations.org_type, refuses a verified binding
    on any demo organization by classification rather than by label

verified_operational_binding_activation_boundary_service
    real-org and production activation each require an explicit approval
    object; aaaaaaaa-… refused by name; no env var can approve

repository            derive rather than accept is_demo, refuse a
                      classification/label mismatch, refuse duplicates
gate                  report verified binding beside customer_auth_live,
                      never inside it
tests, artifacts, docs
```

Nothing here touches the real organization, and nothing here can.
