# 611 — Gate 111E/F: readiness delta

## Customer auth is not live, and login is not live

Read from `login_live_promotion_gate_service`, which already owns the question,
rather than asserted by this gate:

```text
login_live_claimed          False
production_auth_claimed     False
controlled_pilot_auth_ready False
```

Seven of ten promotion gates missing: `provider_configured`, `secret_present`,
`issuer_jwks_validated`, `callback_session_validated`, `invite_binding_passed`,
`org_binding_passed`, `role_mapping_passed`. Three pass — the internal plumbing
is built and no provider is attached.

The artifact carries the missing-gate list verbatim, so the claim is checkable
rather than a bare `false`.

## Cloudflare Access is not customer app auth

The public edge returns a 302 to Cloudflare Access. That controls who reaches the
host; it establishes no organization and sets no RLS context. A
Cloudflare-authenticated visitor is `authenticated_unverified_org` at best.

## Verified organization membership is required for production binding verification

An `authenticated_verified_org` principal with a UUID `organization_id`. An
authenticated person whose organization nobody established cannot verify a
binding, and the refusal names itself.

## What remains false

```text
customer auth live               false
login live                       false
binding store built              false
verified operational binding     false
operational awarded tracking     false
operational digest               false
beta onboarding                  false
customer persistence             false
document storage                 false
live source collection           false
source monitoring                false
source coverage                  false
```

No live fetch occurred. No identity provider was contacted, no session was
created, no credential was stored, no collector ran.

## Readiness patch

The three readiness services already required a verified binding from Gate 109
and already reported false. Adding a duplicate auth key would have been noise
rather than safety, so none was added.

What changed is the binding store decision's next-action sequence, which now
records two things this gate established:

1. Gate 111 built the contracts that decide who may verify — the auth principal,
   the binder authorization and the RLS claim guard — but no provider is
   attached, so no verifier exists.
2. **The OIDC identity mapper resolves a claim to `organization_profile_id`**, a
   `String(128)` with no foreign key on a table with no RLS. Even a live login
   would not produce the UUID the policies enforce on.

The second is new work this gate surfaced and did not fix. Attaching a provider
alone would not be enough; the claim path has to terminate in an
`organization_id` before a verified binding can mean anything.

## Demo fixtures

Nine labelled principals, one per state the binder authorization must handle:
unauthenticated, three demo roles, verified-org tenant_admin, unverified-org
tenant_admin, grants_viewer, auditor, revoked.

```text
customer_auth_live            false
login_live                    false
real_user_data                false
real_sessions_created         false
identity_provider_contacted   false
credentials_stored            false
```

The pair worth reading together is `verified_org_tenant_admin` and
`unverified_org_tenant_admin`: same person, same role, same provider, and one may
verify a binding while the other may not.

### A note on the verified-org fixture

It carries `authenticated_verified_org`, which is what lets the binder matrix
demonstrate a permitted verification. It is still labelled `demo_fixture` and
still reports `customer_auth_live: false`.

That combination is deliberate and slightly uncomfortable, so it is stated
plainly: the fixture shows what a verified principal *would* be allowed to do. It
is not evidence that any such principal exists.

In the production binder matrix, no demo-sourced principal is authorized for
anything — 54 rows, checked by test and by artifact.
