# 706 — Gate 133: auth readiness delta

## The delta

```text
                                  before 133   after 133
login_live                          false        TRUE
issuer_jwks_validated               false        true    measured from rows (0037)
role_mapping_passed                 false        true    measured from rows
login activation decision           absent       recorded, demo-scoped

customer_auth_live                  false        false
dev_header_disabled_for_production  false        false
invite_binding_passed               false        false
owner approval (customer auth)      absent       absent
verified_operational_binding        false        false
```

Nine of eleven login gates already held after Gate 132. This gate moved the
other two and separated the approval.

## Why `customer_auth_live` is still false

### 1. `dev_header_disabled_for_production` — engineering, and it is Gate 134's

```text
routes reading X-NF-Org-Id     207   (was 209; isolation_routes converted)
modules                         14   (was 15)
publicly routed                207   all of them
```

Every one is under `/v1`. The tunnel routes `^/api/.*` to the backend and
everything else to the Vite preview — which **proxies `/v1`, `/docs`,
`/openapi.json` and `/redoc` straight back to the backend**. So they are all
publicly reachable, one hop further in than the ingress rule
`dev_org_header_containment_service` inspects.

That detector's answer (`backend_publicly_exposed: true`) is right today because
of the `/api/*` rule, which covers the five auth routes and no dev-header route.
Delete that ingress line and it would report the backend contained while all 207
stayed exposed. Third instance of this shape in three gates; the new
`dev_header_exposure_matrix_service` models both hops and parses both configs.

Cloudflare Access gates every one of them, and Access is an *edge* boundary. It
decides who reaches the app. It does nothing about which organization a header
names once somebody is through: anybody in the Access policy can set
`X-NF-Org-Id` to any organization id and read that organization's rows.

The plan, ordered least-risky-first, is in
`703_GATE133_DEV_HEADER_KILL_PLAN.md`. Conversion order and route counts are
derived from the app; the risk classification is a judgement recorded beside
them.

### 2. `invite_binding_passed` — unvalidated, not failed

`membership_invite_approval_service` exists and no flow has ever run through it.
Same distinction the JWKS gate needed and the same fix: run one and record it.
This is engineering plus one operational run.

### 3. Owner approval — Mayhem's, out-of-band

`NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL` is unset. Gate 133D deliberately did not
touch it. Claiming customer authentication is live for real Tribal governments
is a decision about exposing a login page to real Tribes, and no measurement
substitutes for it.

## And `verified_operational_binding`

Still false, and not because it was skipped. Gate 113's contract refuses a
verified binding on a demo organization — a demo binding may not carry a
verifier and may not be a `verified_binding`. Gate 132 attempted one and got
both refusals by name. The binding is a `demo_fixture`.

It becomes reachable when a real organization is authorized, which is a separate
decision. Note the related gap recorded in `705`: there is no write path for a
real-organization membership at all today.

## Claims this gate did not make

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

None of them moved, none of them was touched, and `login_live` becoming true
says nothing about any of them. `login_live` means one dev identity can log in
to a demo organization and be recognised. It is the narrowest true statement
available and it is the one being made.

## What each remaining blocker needs, and from whom

```text
dev_header_disabled_for_production   engineering  Gate 134: convert 14 modules
                                                  in the plan's order, then
                                                  NF_DEV_ORG_HEADERS=false
invite_binding_passed                engineering  run one invite flow and record it
owner approval                       Mayhem       out-of-band, whenever the above hold
verified_operational_binding         Mayhem       authorize a real organization
customer_persistence_live            follows      once the dev header is gone
```

## Next gate

Gate 134: dev-header conversion, starting with `stage12_guided_demo_routes` (4
routes) and `trust_routes` (8), then upward through the order. That clears the
only `customer_auth_live` blocker nobody has to decide.
