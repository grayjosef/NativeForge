# 531 — Gate 94B: global live-network guard contract

**Before Gate 94, three of four known live-HTTP call sites bypassed every
guard — and the real count was six, not four.** After Gate 94, every live HTTP
path in `src/nativeforge` is deny-by-default. No collectors were activated, no
live coverage is claimed, and source monitoring remains zero.

## One guard, deny by default

`live_network_guard_service` decides; it never fetches. `fetch_performed` is
`False` on every decision, held by an invariant.

`allow_live_fetch` defaults to `False`. Every status input defaults to the
blocking member of its vocabulary, and an unrecognised value resolves to that
blocking member rather than to a pass — so a typo blocks, and a status nobody
has taught the guard about blocks.

Two invariants make deny-by-default structural rather than incidental: an
allowed decision must carry `allow_live_fetch: True` and an `https` scheme, or
the decision itself is invalid.

## Purpose, because not every request is a collection

Two of the six call sites are not source collection: a Slack operational alert
and an OIDC JWKS fetch. Asking whether a JWKS URL has cleared
`TERMS_REVIEW_REQUIRED` is a category error. A guard that demanded it would
either block identity verification forever or be given a bypass — and a bypass
is how this problem started.

Both already denied by default on their own (`allow_network=False`,
`force_dry_run=True`). That is *a* guard, not *the* guard, so both now route
through this one as well: a choke point where two callers keep their own private
gates is not a choke point, and their decisions would not appear in one place or
carry a caller name.

```text
source_collection       live_fetch_opt_in, https, host_permitted,
                        user_agent_canonical, rate_limit_policy, terms_cleared,
                        activation_allowed, collector_active, robots_permits,
                        credential
source_discovery        the above minus activation, collector and credential
identity_verification   live_fetch_opt_in, https, host_permitted,
                        issuer_configured
operational_alert       live_fetch_opt_in, https, host_permitted,
                        endpoint_configured
```

A purpose outside the vocabulary has no satisfiable requirement set and blocks —
the only safe answer to "I want to make a request for a reason you have never
heard of".

## Nobody self-exempts

The Gate 93 defect was a caller declaring a requirement `not_required` when its
own collector type created that requirement. Here the requirement set is derived
from `purpose` and `collector_type`, both structural, and the caller supplies
only *evidence*. There is no input meaning "skip this one".

`allow_live_fetch=True` is necessary and never sufficient: it is one requirement
among ten and cannot carry a decision alone.

## Robots failure is not permission

```text
allowed        fetched, and it permits this path          -> may crawl
absent         404 — conventionally no restrictions       -> may crawl
disallowed     fetched, and it forbids this path          -> blocked
fetch_failed   timeout / 5xx / connection error           -> blocked
unknown        not checked                                -> blocked
```

Only `allowed` and `absent` permit a crawl. Flipping all five to deny would have
been simpler and wrong: a 404 robots.txt is a real answer, and treating it as a
failure would block most of the registry for no reason.

## Gate 77B is wrapped, not weakened

For a Grants.gov host the guard consults Gate 77B's `live_network_allowed()`,
which reads `NATIVEFORGE_ALLOW_LIVE_GRANTS_GOV_TESTS`. That flag stays
authoritative and this guard adds requirements on top. A test asserts no path
through the new guard reaches Grants.gov with the flag unset, and Gate 77B's own
raise-behaviour is re-tested here.

Attribution is reported separately from permission. `requires_attribution` and
`may_surface_customer_data` describe whether the *output* may reach a customer,
which is a different question from whether the request may go out — the Gate 93C
distinction, preserved.

## Raising and non-raising forms

`assert_live_network_allowed(...)` raises `LiveNetworkPermissionError` naming the
caller, purpose, host and reasons. `require_live_network_permission(...)` returns
the decision for callers that want to degrade rather than fail.

The raising form follows Gate 77B's reasoning: *there is no useful partial
answer to a request we were not allowed to make, and a silent empty result is
indistinguishable from a genuine empty response* — which is how the corpus
fixture got overwritten with a placeholder in the first place.

## Every decision names its caller

`caller` is required and appears in both the decision and its `audit_event`. An
invariant fails a decision whose audit event disagrees with it. A refusal nobody
can trace to a call site is a refusal nobody will fix.
