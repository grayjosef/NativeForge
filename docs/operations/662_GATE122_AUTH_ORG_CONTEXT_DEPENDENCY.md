# 662 — Gate 122B/C: the auth org context dependency

```text
src/nativeforge/services/customer_auth_org_context_dependency_service.py
src/nativeforge/api/deps_customer_auth.py
```

## The dev header is not production auth

`X-NF-Org-Id` selects an organization by being present. Anybody who can reach
the API can send one, and the value they send becomes the RLS context — which is
a cross-tenant read the moment a second tenant exists.

Gate 111's claim guard has said so since it was written:

```text
claim_source          production_context   rls_context_allowed
dev_request_header    True                 False
dev_request_header    False                False
verified_auth_claim   True                 True
```

Nothing routed that answer. This gate routes it.

## Three modes

```text
required            a verified session, or 401
optional            a verified session, or no org context - never a fake one
dev_demo_explicit   X-NF-Org-Id, outside production, with the setting on
```

`unknown` is the fourth and refuses everybody, because a route whose mode nobody
declared is a route nobody thought about. Bridged from Gate 117's contract
rather than restated.

The third mode is named for what it is. Today's behaviour is the same posture
reached by accident — `nf_dev_org_headers` defaults true and nobody turned it
off — and the difference between this and that is that one of them is a
decision.

## optional does not mean anonymous-gets-an-organization

The failure worth guarding is not a route that refuses too much. It is a route
in `optional` mode that, finding no session, substitutes a default organization
so the page renders:

```text
optional + no session  ->  org_context_available: False
                           organization_id:       absent from the result
                           http_status:           200
```

Two hundred, and no organization. The route renders nothing scoped to anybody,
which is correct and looks empty — and looking empty is the point.

`organization_id` is **omitted** rather than set to `None`, and an invariant
fails any result carrying one without `organization_id_resolved`. A test forges
exactly that.

## A verified session is not an organization, and not a membership

Gate 112's rule arriving at the dependency layer. Three conjuncts, reported
separately:

```text
session_valid            somebody holds a credential we issued
organization_id_resolved ...and a claim resolved to a UUID-shaped org id
membership_verified      ...and a membership record backs it
```

A signed cookie proves the first. It proves neither of the others, because
memberships get revoked and a session outlives the revocation until it expires.
`org_context_available` requires all three plus `rls_claim_guard_passed`.

## The dev path carries its provenance

In `dev_demo_explicit`, outside production, with the setting enabled and a
UUID-shaped header:

```text
dev_org_context_available   True
organization_id             the header's value
dev_header_used             True
production_safe             False
rls_claim_guard_passed      False
org_context_available       False
```

Six fields, and four of them say what it is not. A caller gets an organization
and can see exactly what chose it.

The UUID check matters more than it looks: a dev context that could not survive
the `::uuid` cast would fail at the database rather than at this boundary, and a
dev path that fails somewhere less legible than production teaches the wrong
lesson.

## An unknown environment counts as production

```text
NON_PRODUCTION_ENVIRONMENTS = {"local", "dev", "test"}
```

`production` is absent, and so is `unknown`. A deployment that cannot say what
it is does not get the convenience — a misconfigured `app_env` should tighten
the posture, not loosen it.

## Nothing here sets the RLS context

`apply_org_rls_gucs` is deliberately not called. The decision is made here; the
GUCs are applied by whatever ends up owning the session, in a gate where a
session can exist. A dependency contract that set `app.current_org_id` on the
strength of a decision nobody had acted on would be this campaign's recurring
defect one layer lower.

```text
current_org_id_set     False, a constant
organization_created   False, a constant
session_created        False, a constant
```

## Three functions, imported by no route

```text
get_customer_org_context_required   raises 401 with named blocked_reasons
get_customer_org_context_optional   returns None
get_dev_org_context_explicit_only   403 in production, 503 with the setting off
```

A test asserts no route module imports this file. That is not an oversight —
Gate 122A records why converting any of the fourteen today would make it
unreachable, and doc 663 lists them.

The required dependency's 401 carries `blocked_reasons` and
`WWW-Authenticate: Cookie`, so a caller learns which conjunct failed rather than
receiving a bare refusal.
