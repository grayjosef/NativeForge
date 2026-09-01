# 710 — Gate 134: customer auth readiness delta

## The delta

```text
                                     before 134   after 134
dev_header_disabled_for_production     false        TRUE (measured)
dev-header route consumers               207          0
dev-header modules                        14          0

login_live                              true        true
customer_auth_live                     false        false
invite_binding_passed                  false        false
owner approval                        absent       absent
verified_operational_binding           false        false
```

One of the three `customer_auth_live` blockers cleared. Two remain, and one of
them is not an engineering task.

## `dev_header_disabled_for_production` is true, and how

Two ways, either sufficient:

```text
the setting    NF_DEV_ORG_HEADERS=false, set on the deployment
a measured 0   no registered route depends on the header, walked per call
```

The second is the one worth having. The fact the gate reaches for is that *an
unauthenticated header cannot set the RLS context* — and a header no route reads
cannot set anything, whatever a setting says. A deployment that forgets the
setting is now still safe, and the gate can say so with a measurement instead of
a promise.

Without exposure evidence only the setting decides, which keeps the gate
deterministic for the artifacts it feeds. A supplied count above zero holds the
blocker shut; there is a test for that branch too, so the permitted one is not
the only reachable one.

## A cycle that made `customer_auth_live` unreachable

Found while wiring the above:

```text
customer_auth_live
  needs dev_header_disabled_for_production
    which the shutdown readiness gates on auth_replacement_available
      which needs ready_for_live_login
        which needs route_org_resolution_enforced
          which needed customer_auth_live
```

Every link read as a reasonable precondition on its own, which is why five gates
passed over it. The last conjunct was correct when written — no principal could
exist while customer auth was off, so no route could resolve an organization.

Gate 132 made a principal exist and Gate 133 proved it in a browser, both with
`customer_auth_live` false throughout. So the conjunct was asking for the wrong
fact. It asks whether **a principal can exist** now, injectable, and the
activation gate supplies Gate 132's binding evidence — a verified identity
resolving to an organization through a membership row, which is that fact
exactly.

`customer_auth_live` still satisfies it, because live customer auth certainly
means a principal can exist. It is no longer the only way, which is what removes
the cycle.

## `customer_auth_live` is still false

### `invite_binding_passed` — engineering, plus one run

`membership_invite_approval_service` exists and no flow has ever run through it.
Unvalidated rather than failed — the same distinction the JWKS gate needed in
Gate 133, and the same fix: run one and record it.

### owner approval — Mayhem's, out-of-band

`NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL` is unset. Gate 133D deliberately kept the
demo-login decision separate from this one, and
`approves_customer_auth_live()` has no branch that returns True. Claiming
customer authentication is live for real Tribal governments is a decision about
exposing a login page to real Tribes.

### And `verified_operational_binding`

Still false. Gate 113's contract refuses a verified binding on a demo
organization — a demo binding may not carry a verifier. Reachable when a real
organization is authorized, which is a separate decision. Related gap recorded
in `705`: there is no write path for a real-organization membership at all.

## `login_live` is unaffected

The conversion touched no auth route. `/api/auth/*` never consumed the header —
Gate 116 built those routes as the replacement for it and said so — and the
activation gate's login path is unchanged. A test asserts `login_live: true` on
the same injected facts Gate 133 used, alongside `customer_auth_live: false`.

## What this gate did not claim

```text
controlled_customer_pilot      false
production_rollout             false
customer_persistence_live      false
awarded_operational_tracking   false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
```

Converting 207 routes off a header says nothing about any of them.

## Next

Gate 135:

```text
1  delete deps_db.get_org_context_with_db, isolation_deps, and
   get_dev_org_context_explicit_only, with their tests. Zero route consumers
   makes it a deletion rather than a rewrite.
2  run one invite flow through membership_invite_approval_service and record it
3  then customer_auth_live waits on one decision, which is Mayhem's
```
