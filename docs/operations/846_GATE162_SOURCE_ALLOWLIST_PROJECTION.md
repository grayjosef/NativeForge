# Gate 162 — the source allowlist projection

A projection, not a source of truth.

## There is no `allowlisted` column

Nowhere. Not on `nf_active_opportunity_sources`, not on the decisions table,
not anywhere in the schema — and the gate's tests assert that by inspecting
every column of every table rather than by saying so.

A source is allowlisted exactly when its recorded facts authorize it, computed
every time it is asked:

```text
allowlisted = authorization_status == approved
```

And nothing else. Not "could be allowlisted", not "is a candidate", not "has an
adapter".

## Why a stored flag would have been wrong

The drift is not hypothetical. `nf_active_opportunity_sources` already carries
`activation_approved_by`. If an allowlist flag existed beside it, revoking the
activation and forgetting the flag would leave a source allowlisted with
nothing behind it.

A projection cannot go stale because it has nothing to go stale from. The
existing activation columns remain the one place an activation decision is
**stored**; the projection **reads** them.

## What it reports per source

```text
source_id
allowlisted                 the derived boolean
authorization_state         approved / denied / needs_review / missing_fact /
                            stale / unknown
is_synthetic_fixture        so a reader can tell a fixture from a real source
missing_requirements        blocking DECISIONS
denied_requirements         only when a human actually refused
blocking_prerequisites      technical shortfalls, listed separately
evidence_refs
live_transport_permitted    always false
```

## Decisions and prerequisites are reported separately

`collector_status=not_active` and `runtime_status=not_ready` are measured
technical states. Neither is anybody's decision.

The first draft let them set `authorization_status=denied`, which told an
operator that a human had refused a source when nothing of the kind had
happened — and sent them to argue with a reviewer who had never said anything.
Precedence is now applied to **decision facts first**; a measured shortfall is
reported as a blocking prerequisite and `denial_is_a_decision` says which kind
of no it is.

`denied_without_a_recorded_denial` fails if a technical shortfall is ever
reported as a denial again.

## Falsifiability: the list must be populatable

```text
sources evaluated                179   (177 shipped + 2 synthetic fixtures)
real sources allowlisted           0
synthetic fixtures allowlisted     1   with decisions recorded
```

Without something able to appear on this list, "the list is empty" would be
indistinguishable from "the list cannot be populated". So the reserved
`nf162.fixture.` prefix exists, holding two synthetic sources:

```text
nf162.fixture.permittable    reaches approved once decisions are recorded
nf162.fixture.undecided      never receives a decision, and refuses exactly
                             like a real source does
```

The second one matters as much as the first: it shows that **being a fixture is
not itself permission**.

## Why the fixtures are not a parameter

The obvious implementation is a `registry_rows` argument on the resolver. That
would break the property the resolver is built on: registry membership IS a
fact (`source_registered`), so a caller who could supply the registry could
introduce a source and then record decisions for it.

Instead the fixtures live in source code under a reserved prefix, and the
resolver merges them without being told to. `merge_fixture_rows` refuses any id
lacking the prefix and refuses to shadow a shipped registry id.

`is_fixture_source` requires **both** the prefix and declared membership. The
prefix alone would let a caller name a real source `nf162.fixture.grants.gov`;
declared membership alone would be a list somebody could grow without the
prefix rule noticing. The tests assert both halves refuse.

## What a fixture approval proves

That the authorization chain can say yes: the facts resolve, the guard is
satisfied from records, and the permitted branch is live code rather than dead
code.

It proves nothing whatever about any real source. The fixture's terms decision
is signed by `reviewer:nf162-verify`, its evidence fingerprint is a sha256 of a
string in `source_authorization_fixture_registry_service`, and its URL points
at `.invalid` — reserved by RFC 2606 precisely so it cannot exist.

And an allowlisted fixture still cannot be called: Gate 161 built no live
transport, `live` is not in `DISPATCHABLE_KINDS`, and migration 0047's CHECK
constraints refuse a live attempt row.

## The invariant that matters most

```python
real = int(projection.get("real_sources_allowlisted") or 0)
if real:
    fails.append(f"real_sources_allowlisted:{real}")
```

A real source on the allowlist is the one outcome Gate 162 was forbidden to
produce. It is checked per-source as well as in aggregate, and the verifier
checks it again after cleanup, against the database a commit would be made
against.

## The route

`GET /v1/nf/demo/orgs/{org_id}/source-authorization/allowlist` returns the
summary without the per-source list, which is what an operator reads. The
per-source route answers the detail question.

There is no route that flips an entry. The mutation surface of the whole
authorization API is empty, and `mutation_endpoints: 0` is asserted from the
served OpenAPI document rather than claimed in a docstring.
