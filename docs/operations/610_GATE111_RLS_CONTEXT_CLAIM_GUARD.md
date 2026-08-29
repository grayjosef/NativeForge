# 610 — Gate 111D: RLS context claim guard

`src/nativeforge/services/rls_context_claim_guard_service.py`

## Why this exists, concretely

Gate 111A found the one code path in the tree that sets the RLS context:

```python
# api/deps_db.py
async def get_org_context_with_db(
    x_nf_org_id: str | None = Header(default=None, alias="X-NF-Org-Id"),
) -> OrgContext:
    ...
    apply_org_rls_gucs(db, oid, ot)
```

An **unauthenticated request header**, gated by `NF_DEV_ORG_HEADERS`, which
defaults to `True`. Sixteen route modules depend on it.

### What contains it today

Stated precisely, because "a header sets the RLS context" deserves an accurate
exposure statement rather than an alarming one:

```text
nativeforge-backend.service        inactive - the API is not running
backend bind                       127.0.0.1:8000, and a test parses the unit
                                   file to prove it
cloudflared ingress origin         http://127.0.0.1:5175 - the static preview
public edge                        Cloudflare Access, 302 to the Access login
```

So it is a latent dev-only path, not a live exposure. What contains it is
deployment posture rather than the flag, since the flag defaults on.

"The door is unlocked and the building is empty" is not a security property. The
moment auth arrives there will be pressure to route a claim into that same call.
This guard is what that path must go through instead.

## Only the authority sets the authority

```text
organization_id, UUID, verified claim   may set app.current_org_id
org_id, UUID, verified claim            may set it - Gate 110 alias rule
tenant_id                               never, whatever its shape
customer_org_id                         never directly
dev_request_header                      never - not an authenticated claim
unverified claim                        never
demo value or demo principal            never sets a production context
```

`tenant_id` is refused on the **name**, so a UUID-shaped one is still refused —
Gate 110 established that the name governs authority and the shape only governs
whether an eligible name may act.

## The cast is a backstop, not the check

Every policy does `current_setting('app.current_org_id', true)::uuid`, so a value
that cannot cast raises rather than matching. That is real protection, and
relying on it would still be wrong: an exception inside a request handler is a
worse outcome than a refusal, and it tells the caller nothing.

So the guard checks the shape itself and refuses with a named reason.

## customer_org_id is refused directly, not permanently

A verified binding resolves it to an `organization_id`, and the context is then
set from *that* — the same rule Gate 110's persistence guard holds for writes.
The guard reports a resolved value when a caller supplies one and never derives
one.

## The guard sets nothing

```text
current_org_id_set        false
session_variable_written  false
identity_derived          false
```

It decides whether a claim may set the context. It touches no session and calls
no `set_config`.

## Invariants

Every refusal is enforced and every one was verified by mutation:

```text
tenant_id / customer_org_id permitted to set app.current_org_id
ineligible identity name permitted
non-uuid claim permitted
untrusted claim source permitted
unverified claim permitted
demo claim permitted a production context
claim permitted despite blocked reasons
cross-tenant risk without human review
claim refused without a reason
```

The permission path is tested too — a verified `organization_id` claim from a
verified principal really does set the context — because a guard that refuses
everything proves nothing.
