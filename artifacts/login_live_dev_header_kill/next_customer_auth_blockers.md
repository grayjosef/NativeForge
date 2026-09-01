# Gate 133 — what moved, and what `customer_auth_live` still waits on

## `login_live` is true

```text
issuer_jwks_validated       now measured from nf_auth_validation_events (migration 0037)
role_mapping_passed         now measured from nf_org_memberships
login activation decision   recorded, demo-scoped, cannot approve customer auth
+ the nine gates that already held
```

Measured on the deployment: `login_live: true`, `customer_auth_live: false`.

Two of those three were literals. `callback_session_validated = False` was
assigned once and never again; `org_binding_passed` and `role_mapping_passed`
were parameters of `run_auth0_live_validation` that no caller passed. Gate 132
fixed the first two the same way. A constant frozen in one gate becomes a lie in
the next, and this is the fourth time this campaign has found that exact shape.

## `customer_auth_live` is false, for three reasons

### `dev_header_disabled_for_production`

0 routes across
0 modules still read `X-NF-Org-Id`, and
every one of them is publicly routed through the preview proxy behind
Cloudflare Access.
Access gates *who reaches the app*; it does nothing about which organization a
header names once somebody is through. Anybody in the Access policy can read any
organization's rows.

Gate 133F converted `isolation_routes` and wrote the order for the rest. This is
the blocker that is engineering rather than a decision, and it is Gate 134's.

### `invite_binding_passed`

Never validated against a real flow. There is an invite/approval service
(`membership_invite_approval_service`) and no flow has run through it, so this
is unvalidated rather than failed — the same distinction the JWKS gate needed,
and the same fix: run one and record it.

### owner approval

`NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL` is unset. Gate 133D deliberately did not
touch it: the demo login decision is a different decision, and
`approves_customer_auth_live()` has no branch that returns True. Claiming
customer auth is live for real Tribal governments is Mayhem's to decide
out-of-band.

## And `verified_operational_binding` is still false

Gate 113's contract refuses a verified binding on a demo organization — a demo
binding may not carry a verifier. The binding is a `demo_fixture`. It becomes
reachable when a real organization is authorized, which is a separate decision
and was explicitly out of scope here.

## Unchanged, stated so nothing above reads as progress on them

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

## Next

Gate 134: convert the dev-header modules in the order in
`dev_header_kill_plan.md`, starting with `stage12_guided_demo_routes` and
`trust_routes`, then flip `NF_DEV_ORG_HEADERS=false`. That clears the only
`customer_auth_live` blocker nobody has to decide.
