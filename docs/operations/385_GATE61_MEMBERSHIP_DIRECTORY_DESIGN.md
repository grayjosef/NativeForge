# 385 — Gate 61C: Membership directory design

Service: `src/nativeforge/services/membership_directory_service.py`
Tests: `tests/test_gate61_membership_directory_storage_path.py` (43 tests)

This is the link between Gate 60 (`verified token → verified identity`) and
Gate 53 (`role → capability`). It is the piece whose absence made Gate 59
correctly refuse to wire capability enforcement.

## Record fields

| Field | Source of truth |
| --- | --- |
| `subject` | verified OIDC token (Gate 60) |
| `email`, `email_verified` | token claims — informational only |
| `organization_profile_id` | the directory record, never the client |
| `state` | directory, with expiry/revocation **derived** |
| `membership_source` | directory |
| `role` | directory |
| `role_source` | directory |
| `invited_by`, `approved_by` | directory |
| `created_at`, `revoked_at`, `expires_at` | directory |
| `membership_trusted`, `role_trusted`, `trusted_role` | **derived, never accepted from the caller** |

## Membership states

`invited`, `pending`, `active`, `suspended`, `revoked`, `expired`, `unknown`.

`ACTING_STATES = {"active"}` and `DENYING_STATES` is **derived** as the
remainder, so a state added later denies by default rather than silently
permitting. A test asserts `ACTING_STATES` is exactly `{"active"}`.

## Trusted vs untrusted sources

**Trusted membership sources** — each can grant when the record is active:
`verified_directory`, `operator_approved`, `org_owner_approved`.

**Untrusted, always** — `client_header`, `dev_header`, `cloudflare_access`,
`email_domain_only`. Each is parametrized in a test that asserts denial.

**Role sources.** Only `membership_record` is trusted. Notably `token_claim` is
**not**: an IdP group or role claim is the identity provider's opinion, not this
product's membership record. Auth0 roles are configured by whoever administers
the tenant, which is not the same trust domain as "this person may act for this
tribal organization". `client_header` and `email_domain` are likewise untrusted.

## Derived guards

Four things are computed rather than believed:

1. **Expiry** — `expires_at` in the past relative to a supplied `now` forces
   `expired`, whatever state the caller passed.
2. **Revocation** — any `revoked_at` forces `revoked`.
3. **Approval** — a record claiming `operator_approved` or `org_owner_approved`
   with no `approved_by` is downgraded to `unknown`. An approval by nobody is
   not an approval.
4. **Unknown roles are dropped** — a role outside `ALL_ROLES` becomes `None`
   rather than passing through as a string.

## Trust derivation

```text
membership_trusted = trusted source
                     AND subject present
                     AND organization present
                     AND state == active

role_trusted       = membership_trusted
                     AND a known role
                     AND role_source == membership_record
                     AND role is not an internal role
```

`trusted_role` is populated only when `role_trusted`. An invariant fails any
record where `trusted_role` is set without it.

## Denial rules — all test-enforced

| Rule | Enforced by |
| --- | --- |
| verified token alone is not membership | `no_membership_record` |
| email domain alone is not membership | untrusted source parametrized test |
| Cloudflare Access is not membership | `identity_verification_not_trusted` |
| client header is not membership | untrusted source + untrusted role source |
| membership must be active | `DENYING_STATES` parametrized test |
| role must come from a trusted membership | `role_not_trusted` |
| revoked / expired / suspended deny | derived state + parametrized test |
| `operator_internal` never customer authority | explicit reason + invariant |
| membership in org B grants nothing in org A | lookup keyed on (subject, org) |

## The resolver

`resolve_trusted_membership(identity, organization_profile_id, directory)`
returns `{allowed, blocked_reasons, trusted_role, membership_state,
membership_source, storage_backend_state, production_storage_live, ...}` plus a
modeled audit event on denial (`persisted: false`).

It requires the identity's `verification_trusted` to be true, so a
demo_operator or unverified identity can never reach a membership lookup even if
a matching record exists — proven by a test that plants a valid record and still
denies a Cloudflare Access identity.

## Storage honesty

`storage_backend_status()` reports one of `no_backend`,
`in_memory_test_adapter`, `local_dev_sqlite`, `approved_production_backend`,
`unknown`.

`production_storage_live` requires **both** an approved backend **and** a
present approval token. Tests prove each alone is insufficient. Neither exists,
so it is `false` everywhere.

The adapter is `InMemoryMembershipDirectory` — a test asserts the class name
contains neither "production" nor "live", because a future reader skimming for
"is this real" should get the answer from the name.

## What this design does not do

- It does not persist anything.
- It does not create a schema (see `384` §5 — migrations `0023`–`0027` are
  specified but deliberately unwritten).
- It is not wired to any live customer route (see `386`).
- It does not make `customer_login_live` true.
