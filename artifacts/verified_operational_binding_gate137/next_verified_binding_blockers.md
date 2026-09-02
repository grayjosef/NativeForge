# Gate 137 — what still blocks a verified operational binding

## Runtime value

```text
verified_operational_binding   FALSE
```

Not surfaced by `/api/auth/session` before this gate and reported there now,
beside `customer_auth_live` rather than inside it.

## Two blockers, in order, and neither is code

### 1. `customer_auth_live`

`verified_binding_workflow_service` refuses a production verified binding
without it:

```text
production_verified_binding_requires_live_customer_auth
```

Gate 136 made this reachable. It needs a second real Google account to complete
an invite — `docs/operations/717` has the four steps and the OAuth test-user
prerequisite.

### 2. An owner decision authorizing real-org binding activation

```text
AUTHORIZED_REAL_ORGANIZATION_IDS = frozenset()
```

Empty, deliberately. Mayhem's standing authorization refuses `real org
activation` and refuses binding to `aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee` by name.

Activating one needs **both**:

```text
a reviewed code change adding the id to that constant
an approval object naming the same organization, scope, environment and
  who authorized it
```

Either alone is refused. No environment variable can approve; one can revoke.

## What is NOT the blocker any more

```text
the write path            exists, and is proved end to end against a
                          hermetic real organization
is_demo                   derived from organizations.org_type
duplicates                refused
ambiguous reads           refused rather than resolved by row order
the demo organization     refused by classification, in the boolean and in
                          the blocker list
```

## What is still open, and named rather than fixed

Binder authorization decides by **role** — `{platform_admin, tenant_admin}` —
and reads `org_claim_verified` off the principal. Gate 132's membership
evidence and Gate 136's invite evidence both read real rows, and neither is an
input to that decision.

So the strongest membership facts in the system do not reach the decision that
writes a verified binding. Recorded in `719` and named here as the next gate's
work; the preparation service reports `membership_source: not_consulted` rather
than implying otherwise.

## Still false, and not touched by this gate

```text
production_rollout             false
controlled_customer_pilot      false
customer_auth_live             false
customer_persistence_live      false
awarded_operational_tracking   false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
```
