# 697 — Gate 131: current-user and the org binding blocker

## Current-user status

```text
GET /api/auth/current-user   401 unauthenticated
```

Unchanged by this gate, and correctly so. A 401 here is not a failure of the
login flow — it is the accurate answer to "is this caller authenticated", asked
by a browser that holds no session because none was minted.

## Why no session was minted

A real Google identity was verified. The callback reports:

```text
identity_validated    true
session_created       false
org_binding_missing   true
```

`customer_session_format_service` refuses a session with no organization. With
every other field supplied, `session_without_an_organization_id` is the only
blocked reason — so the organization is the only thing between a verified
identity and a session.

## Identity is not authorization

This is the distinction the whole campaign turns on, and it arrives here
concretely for the first time.

```text
Google says      this is quiet.mayhem@gmail.com, and it verified that
NativeForge asks which Tribal government does this person act for
Google's answer  none. It does not know and was never asked.
```

An email address is not an organization. A verified subject is not a
membership. Gate 112 settled that a claim says *which* organization and a
membership record says they *belong* — both, or no RLS context — and the session
format enforces it by refusing to encode a session that has neither.

Deriving an organization from the email domain would be the obvious shortcut and
is exactly the failure this refuses: `gmail.com` is not a Tribe, and for a real
customer `@some-nation.gov` would be a guess dressed as an authorization.

## The state of the three tables

Nothing in this gate created a row in any of them:

```text
nf_identities                    0
nf_org_memberships               0
nf_tenant_customer_org_bindings  0
```

No fake user, no fake session, no fake binding. The only rows this gate wrote
anywhere are redirect-state rows, and those hold a digest and a ciphertext.

## Liveness, stated plainly

```text
login_live           false
customer_auth_live   false
```

`login_live` could not become true. It requires a session that
`/api/auth/current-user` recognises, and no session exists. Forcing one would
have meant minting a cookie the verifier already rejects, which is a session in
name only — precisely the shape this campaign exists to refuse.

`customer_auth_live` additionally requires `org_binding_passed`, which requires
a membership record that no one has.

## What Gate 132 has to do

```text
1  resolve a verified claim to an organization_id
     oidc_organization_id_resolution_service implements this and has never
     been run against a real identity
2  create the membership record
     nf_org_memberships, migration 0024
3  create the tenant/customer org binding
     nf_tenant_customer_org_bindings, migration 0029
4  re-run the browser login
     the session then mints, current-user answers with an identity, and
     login_live can be measured rather than asserted
```

Step 1 is code that exists. Steps 2 and 3 write the first rows tying a real
person to a real organization in NativeForge, and that is a decision about who is
let in — Mayhem's to authorize, not a side effect of a login smoke.

`customer_auth_live` also needs `role_mapping_passed`,
`dev_header_disabled_for_production` and owner approval, so it will remain false
past Gate 132 even once a binding exists.

## The next required action, as the API reports it

```json
"next_required_action": "create a dev organization binding for this identity"
```

The route says it itself, so an operator reading the callback response does not
have to consult this document to know what is missing.
