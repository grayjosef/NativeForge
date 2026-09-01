# 701 — Gate 132: the first identity, the first membership, the first session

A real Google login now mints a session and `/api/auth/current-user` answers
with an organization and a role. Three tables that had never held a row hold
one each.

## The two logins, and why there were two

The order matters more than the outcome.

### Login one — identity persisted, session refused

```text
state_validated              true
pkce_verified                true
token_exchange_succeeded     true   (HTTP 200)
identity_validated           true   (JWKS, domain gmail.com)
identity_rows_written        1
organization_id_resolved     false
membership_verified          false
session_created              false
reason                       identity_has_no_active_membership
```

The callback persists the verified identity and **creates no membership**. That
is the whole design: auto-creating one would mean anybody with a Google account
joins the demo organization by signing in. A Google account proves who somebody
is; it says nothing about which Tribal government they act for.

### Then the membership, deliberately, under Mayhem's authorization

### Login two — session minted

```text
identity_rows_written        0      (already existed; one person, seen twice)
organization_id_resolved     true
membership_verified          true
session_created              true
status                       session_created
```

## `/api/auth/current-user`

```text
no cookie                    401   (loopback; publicly 302 from Cloudflare Access
                                    before the request reaches the application)
forged cookie                401
cookie signed by another key 401
valid session                200
```

```json
{
  "authenticated": true,
  "organization_id": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
  "organization_id_resolved": true,
  "membership_verified": true,
  "roles": ["org_owner"],
  "least_privilege_role": "org_owner",
  "email": null,
  "subject": "<internal identity id, not the provider subject>"
}
```

No token, cookie value, provider subject or email address appears in any
response body.

## Rows created

```text
nf_identities                    1   from a verified claim, by the callback
nf_org_memberships               1   demo org, is_demo derived, role org_owner
nf_tenant_customer_org_bindings  1   demo_fixture, no verifier

on the organization typed `real`   0 memberships, 0 bindings
```

The identity row was written by `/api/auth/callback`. The membership and the
binding were written by a one-off script calling the committed services —
`insert_membership` and `insert_binding` — and that script is deliberately not
committed. Nothing in `src/` creates a membership on its own, which is the
property that keeps a Google account from being a way in. Creating the next one
is a decision somebody takes, the way this one was.

## The verified binding that a demo organization cannot have

`verified_operational_binding` is **false**, and not because it was skipped. A
`verified_binding` was attempted and Gate 113's own contract refused it:

```text
demo_fixture_binding_cannot_carry_a_verifier
demo_fixture_cannot_be_a_verified_binding
```

The authorization was demo-only. A demo binding may not carry a verifier and may
not be a verified binding, so the only storable status on this organization is
`demo_fixture` — which is, correctly, not a verified operational binding. A
verified one becomes reachable when a real organization is authorized, which is
a separate decision and not this gate's to take.

## Two defects found in my own work

**A cookie's organization was believed.** The first version of `_session_decision`
read `organization_id` out of the verified cookie payload. A session naming an
organization the holder is not a member of — a stale cookie outliving a revoked
membership — came back reported as that organization, with the membership check
passing on the existence of *some* membership. Declared, not derived, and the
exact substitution Gates 110–113 exist to prevent. The organization and the roles
now come from the membership row; a cookie whose claim does not match it yields
`organization_id: null` and `membership_verified: false`. Caught by the
cross-organization case in this gate's own probe, and now a test.

**An absent table blocked an unrelated gate.** `build_binding_evidence` folded
every read failure into one `blocked_reasons` list, so a database without
`nf_auth_redirect_states` could not satisfy `org_binding_passed` — a gate that
has nothing to do with redirect states. Each gate is blocked by its own failures
now. Caught by a test running against an in-memory database that has only the
three tables it needs.

## Three response constants that became false

`_envelope` hardcoded `real_session_created`, `real_user_created` and
`provider_contacted` to `False` on every auth response. All three were true when
this gate's callback ran: it contacted Google, wrote an identity row, and minted
a session. They default to `False` and `/callback` passes what it actually did.

A field asserting otherwise is not a safety property. It is a false statement in
a response body, and it would have been trusted precisely because it had been
true for sixteen gates.

## Two activation gates that were literals

```python
callback_session_validated = False                      # assigned once, never again
def run_auth0_live_validation(*, org_binding_passed: bool = False, ...)   # no caller passed it
```

Both are measured now, by `customer_auth_binding_evidence_service`, from rows:

```text
org_binding_passed            an identity, and a membership that resolves for it
callback_session_validated    the above, plus a CONSUMED redirect state
```

The consumed state is the half a script cannot manufacture — only a callback can
spend one. Without it the gate would be satisfiable by inserting two rows.

Evidence is supplied by the caller. A route with a session passes it; artifact
generation passes nothing and every field is false. That keeps
`build_customer_auth_activation_gate` deterministic for the artifacts it feeds,
and the artifacts record both numbers rather than one.

## Readiness: nothing flipped, and why

```text
login_live                       false
customer_auth_live               false
verified_operational_binding     false
customer_persistence_live        false
awarded_operational_tracking     false
tenant_digest_operational        false
source_monitoring_live           false
email_delivery                   false
object_store_configured          false
```

`login_live` has three remaining blockers and none of them is Gate 132's to
clear:

```text
issuer_jwks_validated   the callback verifies an ID token against Google's JWKS
                        on every login - which IS this gate's subject - but
                        nothing durable records it. A gate satisfied by a value
                        held in a local is a gate satisfied by an assertion.
role_mapping_passed     provider roles are not configured or mapped. The role on
                        the membership came from the membership record, which is
                        the trusted source and is not a provider role mapping.
owner_approval          NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL is Mayhem's
                        out-of-band decision. Setting it would make it meaningless.
```

`customer_auth_live` additionally needs `dev_header_disabled_for_production`,
which 15 route modules still depend on. That is Gate 122's work.

## Next

Record a durable validation run for the JWKS check the callback already
performs. It is the only remaining `login_live` blocker that is a measurement
problem rather than a decision or a migration.
