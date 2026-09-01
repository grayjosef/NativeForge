# 704 — Gate 133: `login_live` is true

Measured on the dev deployment, 2026-09-01, through a real Google login in a
browser:

```text
login_live           true
customer_auth_live   false
```

## What changed

Three of the eleven `REQUIRED_LOGIN_GATES` were false. None of them was false
because something had failed.

### `issuer_jwks_validated` — the fact that kept not existing

The callback has verified Google's ID token against Google's JWKS on every
login since Gate 131. The result lived in a local named `verification` and was
discarded when the request ended, so nothing could read it:

```python
verification = verify_oidc_token(token=..., jwks=..., ...)   # used, then gone
```

Meanwhile `auth0_live_validation_runner_service` had
`provider_validated = False` — assigned once, never assigned again. The gate
read a constant while the thing it described happened repeatedly.

Migration **0037** adds `nf_auth_validation_events`. Every login now writes one
sanitized row, and `issuer_jwks_validated` is derived from those rows.

```text
stored     issuer URL, verification state, algorithm, sha256(kid)[:32],
           five booleans, blocked reasons
refused    the token, the JWKS document, key material, the audience value, the
           provider subject, the email, every claim
```

There is no column any of the refused values could go into, which is a stronger
guarantee than a rule about what to put in one. Two database CHECKs make the
gate's input un-forgeable by direct INSERT: a signature cannot validate without
a JWKS document, and `verification_state = 'verified'` requires all four
validations true.

The table has no `organization_id` and no RLS, for the reason migration 0030
gives for `nf_auth_redirect_states`: the row is written before any organization
is known, and an invented anchor would make the RLS predicate pass on a value
nobody chose.

**A recorded event that reached the provider is also a network check.** The
preflight runs offline and reported `jwks_reachable: None`, which an existing
invariant treated as "no check happened" — true of the preflight, and false of
the deployment. `issuer_jwks_network_check_performed` now also derives from the
evidence's `provider_called`, which comes from the fetcher's own report of
whether it went out.

### `role_mapping_passed` — no new storage needed

Its evidence is a **membership row**, and a row is the thing itself rather than
a report about an event. It survives the process because it is not a memory of
anything. So this needed a query, not a migration.

```text
role from            nf_org_memberships.role
role_source          'membership_record', and only that
membership_source    verified_directory | operator_approved | org_owner_approved
organization_id      the membership row's, never the cookie's
```

`role_mapping_passed` was a parameter of `run_auth0_live_validation` that no
caller ever passed — the same shape Gate 132 fixed for `org_binding_passed` and
`callback_session_validated`. Fourth instance in this campaign.

### The owner decision, split from the one it was standing in for

One env var gated both flags:

```python
owner_approval = os.environ.get(APPROVAL_ENV, "") == APPROVAL_TOKEN
customer_auth_live = all_auth_gates and owner_approval
login_live         = all_login_gates and owner_approval      # the same input
```

So the only way to admit that a working demo login works was to also claim
customer authentication is live for real Tribal governments. Those are different
decisions.

`customer_auth_owner_activation_decision_service` represents the narrow one and
**cannot represent the broad one**: `approves_customer_auth_live()` takes no
arguments and has no branch that returns True. Its scope is checked per call.

```text
organization    bbbbbbbb-cccc-dddd-eeee-ffffffffffff, and no other
refused         aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee, by name
provider        Google
environment     local | dev | test. production and unset are refused.
revocation      NF_DEMO_LOGIN_ACTIVATION_REVOKED turns it off
grant           there is no environment variable that turns it on
```

`login_live = all_login_gates and (owner_approval or login_activation_approved)`.
`or`, not replacement: approving customer auth approves the login path it runs
on, so the broad approval subsumes the narrow one. The narrow one cannot work in
the other direction.

The decision is a committed record rather than an env var because an approval is
a decision, not a measurement, and because `login_live` should not depend on
which machine ran the code. What keeps a committed "approved" from being the
declared-vs-derived defect is that it approves almost nothing — and it does not
make `login_live` true. It removes the last reason it was false.

Which organization the decision is checked against is **derived**: the route
reads `mapped_organizations` out of the role-mapping evidence and offers the
single mapped organization. Nought or several, and no organization is offered
and the decision refuses by name.

## The live sequence

```text
/api/auth/login                     302 to accounts.google.com
callback: state validated           true
callback: PKCE validated            true
callback: token exchange            HTTP 200
callback: ID token verified         true, via JWKS
callback: validation event written  true          <- new
callback: organization resolved     true
callback: membership verified       true
callback: session created           true
callback response: login_live       false         <- see below
next request: login_live            TRUE
/api/auth/current-user              200, org bbbbbbbb-..., roles [org_owner]
```

The callback's own response still read `login_live: false`, correctly: the gate
is computed at the start of the request and the validation event is written
during it. The next request saw it. Recorded rather than smoothed over — a gate
that reported the future would be a gate reporting something it had not measured.

## What did not change

```text
customer_auth_live               false
verified_operational_binding     false
customer_persistence_live        false
controlled_customer_pilot        false
production_rollout               false
awarded_operational_tracking     false
tenant_digest_operational        false
source_monitoring_live           false
email_delivery                   false
object_store_configured          false
```

See `706_GATE133_AUTH_READINESS_DELTA.md` for each remaining blocker and whose
it is.
