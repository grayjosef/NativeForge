# Gate 132 — what moved, what did not, and why

## Moved

```text
identity persistence     nf_identities can be written, and holds 1 row
membership creation      nf_org_memberships can be written, and holds 1 row
org resolution           a verified identity resolves to an organization_id
                         through a membership row, and through nothing else
session minting          a real Google login now mints a session
current-user             200, with an organization and a role
callback_session_validated  measured from rows instead of a literal False
org_binding_passed          measured from rows instead of a parameter nobody passed
```

## Did not move, and cannot yet

### `login_live` — three blockers, none of them Gate 132's to clear

```text
issuer_jwks_validated   the callback verified an ID token against Google's JWKS,
                        which is the fact this gate describes - but nothing
                        durable records it, and a gate satisfied by a value held
                        in a local is a gate satisfied by an assertion. Deriving
                        it needs a recorded validation run.
role_mapping_passed     provider roles are not configured or mapped. The role on
                        the membership came from the membership record, which is
                        the trusted source - it is not a provider role mapping.
owner_approval          NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL is Mayhem's
                        out-of-band decision. Not mine to set, and setting it
                        would make the gate meaningless.
```

### `verified_operational_binding` — refused by Gate 113's own contract

The authorization was demo-only, and a demo binding may not carry a verifier and
may not be a `verified_binding`. Both refusals fired when a `verified_binding`
was attempted:

```text
demo_fixture_binding_cannot_carry_a_verifier
demo_fixture_cannot_be_a_verified_binding
```

So the binding is a `demo_fixture` and `verified_operational_binding` is false.
That is the contract working, not a gap: a verified operational binding on a
demo organization would be a fixture wearing production's label. It becomes
reachable when a real organization is authorized, which is a separate decision.

### `customer_persistence_live`

`dev_header_disabled_for_production` is still false and 15 route modules still
read `X-NF-Org-Id`. Customer persistence under an authenticated claim needs that
header gone, which is Gate 122's work and touches every one of them.

## Unchanged, and stated so nothing reads the above as progress on them

```text
awarded_operational_tracking   false
tenant_digest_operational      false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
```

## The next thing worth doing

Record a durable validation run for the JWKS check the callback already
performs. It is the only remaining `login_live` blocker that is a measurement
problem rather than a decision or a migration - the check happens on every
callback and nothing writes it down.
