# 758 — Gate 145: internal / demo beta — GO

## Decision

```text
internal_demo_beta   GO
scope                controlled_dev_demo
```

Every one of eight conditions is met, and every one of seven flags that would
make that a lie is false.

## The eight conditions, and where each was proved

```text
login_live                         Gate 133
customer_persistence_live          Gate 138
awarded_operational_tracking       Gate 139
tenant_digest_operational          Gate 140
document_metadata_operational      Gate 141
email_delivery_readiness           Gate 142
source_monitoring_preflight_ready  Gate 143
beta_onboarding_cockpit_route_live Gate 144
```

Each has its own verifier, and the cockpit verifier runs all of them before
reporting. A matrix built on lanes nobody proved would be the thing this gate
exists to prevent.

## The seven that must be false, and are

```text
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
customer_auth_live             false
verified_operational_binding   false
controlled_customer_pilot      false
production_rollout             false
```

This is the honesty condition, not a nicety. A demo that had quietly switched
one of them on would not be a demo — it would be a production deployment
nobody had decided to make.

## What an operator can actually do today

Sign in with Google and reach their organization. Keep a tenant profile. Record
an awarded grant, its requirements, its proof events and its document
references, and read every one back anchored on `organization_id`. Preview a
weekly digest, opt into a daily one, suppress an item into a pursuit with an
audit row behind it and lift it again. Rehearse a digest delivery end to end.
Evaluate all 177 registry sources and see exactly what blocks monitoring each.
Read a cockpit that says what all of that does and does not mean.

## The constraints, which are not caveats

```text
demo organization only (bbbbbbbb-cccc-dddd-eeee-ffffffffffff)
fixture-labelled rows only
no real customer data
digest is preview_only; nothing is sent
no source is monitored and none is cleared for collection
document references only; no bytes are stored
```

Every one is enforced somewhere that is not a convention: a CHECK constraint, a
route refusal, an absent dependency, or an invariant.

## One thing worth knowing about this GO

It drops to LIMITED_GO the moment `customer_auth_live` becomes true.

That is correct. Once a real customer has signed in, the deployment has stopped
being an internal demo, and the matrix says so rather than carrying the old
verdict forward.
