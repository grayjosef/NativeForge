# Gate 131 — where the login stops, and why

## What works now

A real Google login runs end to end.

```text
/api/auth/login             302 to accounts.google.com/o/oauth2/v2/auth
state persisted             nf_auth_redirect_states, one-time, expiring, replay-detected
PKCE verifier               encrypted at rest, recovered for the exchange
Google consent              completed
callback reached the API    yes, through the Access bypass
state validated             yes
PKCE validated              yes
token exchange              HTTP 200
ID token verified           yes, via JWKS
identity                    verified
```

## Where it stops

```text
session_created   false
reason            session_without_an_organization_id
```

`customer_session_format_service` refuses a session with no organization. With
every other field supplied that is the *only* blocked reason, so it is the only
thing between a verified identity and a session.

That is not an omission. It is Gate 112's rule expressed in the session format:
an organization claim says which, membership says they belong — both, or no RLS.
A session with a null organization would be refused by the verifier anyway
(`session_cookie_carries_no_organization_id`), so minting one would produce a
cookie in name only.

## Therefore

```text
login_live           false   no session exists, so nothing proves a login
customer_auth_live   false   no organization owns the identity
```

`login_live` could not become true in this gate, and forcing it would have meant
minting a session the verifier rejects.

## Gate 132

Bind a verified identity to an organization:

```text
1  resolve the verified claim to an organization_id
     oidc_organization_id_resolution_service already implements this
2  create a membership record
     nf_org_memberships, migration 0024
3  create the tenant/customer org binding
     nf_tenant_customer_org_bindings, migration 0029
4  re-run the browser login
     the session then mints, and current-user answers with an identity
```

Nothing in this gate created any of those rows:

```text
nf_identities                    0
nf_org_memberships               0
nf_tenant_customer_org_bindings  0
```

The first binding is a decision about who NativeForge lets in, and it is
Mayhem's to authorize rather than a side effect of a login smoke.
