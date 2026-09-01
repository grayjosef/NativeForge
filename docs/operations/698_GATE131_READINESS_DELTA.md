# 698 — Gate 131: readiness delta

## Moved

```text
alembic head                     0035        0036
PKCE verifier at rest            digest      digest + encrypted ciphertext
redirect state persisted         no          yes, durable, one-time, expiring
replay detection                 unexercised recorded and refused
/api/auth/login                  200 refusal 302 to Google
authorization redirect issued    constant    derived from four conjuncts
token exchange client            none        built, chokepoint-registered
token exchange performed         never       yes, HTTP 200, against Google
ID token verified                never       yes, via JWKS
identity validated               never       yes, a real Google account
callback state validation        impossible  working
```

## Not moved, and this is the honest part

```text
session_created                  false
login_live                       false
customer_auth_live               false
verified_operational_binding     false
customer_persistence_live        false
org_binding_passed               false
rows in nf_identities            0
rows in nf_org_memberships       0
rows in nf_tenant_customer_org_bindings  0
```

## The finding that shaped the gate

Migration 0030 stored the PKCE verifier as a SHA-256 digest. PKCE requires
presenting the **raw** verifier to the token endpoint, so the exchange was
impossible — by schema, not by policy. Every readiness surface said "token
exchange not performed", which was true and read as a decision when it was an
inability.

Migration 0036 and an encrypted, recoverable verifier are what turned it from
impossible into working.

## The wall, and why it is the right one

A verified Google identity produces `identity_validated: true` and
`session_created: false`, because `customer_session_format_service` refuses a
session with no organization. With every other field supplied that is the only
blocked reason.

```text
Google knows      who this person is
Google does not   which Tribal government they act for
```

An email domain is not an organization. Deriving one would be a guess dressed as
an authorization, and the session format refuses to encode it.

So `login_live` could not become true in this gate. That was the expected
outcome only in the sense that the wall was expected *after* session minting; it
turned out to sit one step earlier, at minting itself. Reporting it where it
actually is matters more than reaching a boolean.

## Two smaller findings, recorded rather than fixed

**The contract state service has a silent no-op.**
`customer_auth_redirect_state_store_service.store_state` accepts `database` as a
valid scope, implements no branch for it, and returns `stored: False` with no
blocked reason. Off the login path now, but a future caller asking it for
durable storage gets silence.

**The backend unit could not write its own database.** `ProtectHome=read-only`
with only `artifacts` writable meant `/login` refused with
`redirect_state_store_unavailable` — correct, but for a reason no operator would
guess. SQLite needs the *directory* writable to create its journal, so naming
only the `.db` file fails namespace setup on a journal that does not exist yet.

The unit now grants the repository directory, which is broader than ideal. The
narrow fix is to move the dev database out of the source tree; that changes
`DATABASE_URL` and belongs in its own change. `ProtectSystem=full` and
`ProtectHome=read-only` still hold everywhere else.

## What Gate 132 needs

```text
1  resolve a verified claim to an organization_id     code exists, never run
2  create the membership record                       nf_org_memberships
3  create the tenant/customer org binding             nf_tenant_customer_org_bindings
4  re-run the browser login                           session mints, current-user
                                                      answers, login_live measurable
```

Steps 2 and 3 write the first rows tying a real person to a real organization,
which is a decision about who is let in rather than a side effect of a smoke
test.

Even with a binding, `customer_auth_live` stays false: it also requires
`role_mapping_passed`, `dev_header_disabled_for_production` and owner approval.

## The sentence to refuse

> Customers can log in to NativeForge now.

They cannot. A verified identity can reach the callback and be recognised, and
then nothing happens, because NativeForge does not yet know which government
that person speaks for. That is the correct behaviour and the last hard problem
before it stops being true.
