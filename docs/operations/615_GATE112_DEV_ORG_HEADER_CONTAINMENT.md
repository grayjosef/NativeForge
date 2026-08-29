# 615 — Gate 112E: dev org header containment

`src/nativeforge/services/dev_org_header_containment_service.py`

## The dev org header is not customer auth

```python
# api/deps_db.py
async def get_org_context_with_db(
    x_nf_org_id: str | None = Header(default=None, alias="X-NF-Org-Id"),
) -> OrgContext:
    ...
    apply_org_rls_gucs(db, oid, ot)
```

An unauthenticated request header sets `app.current_org_id`, the session variable
every row-level security policy reads. `NF_DEV_ORG_HEADERS` gates it and
**defaults to `True`**. Sixteen route modules depend on it.

`dev_header_is_customer_auth` is a constant `False`. It authenticates nobody: it
asserts an organization and the code believes it.

## The dev org header is not production-safe

```text
production_safe                     false, always
must_disable_before_customer_auth   true
must_replace_with_auth_claim_guard  true
replacement_service                 rls_context_claim_guard_service
```

`production_safe` is a constant, not a measurement. While an unauthenticated
header can set the org context, the answer is no — regardless of how well the
deployment happens to be closed. An invariant fails any result claiming
otherwise, and the mutation that declares it safe is caught.

## Containment is measured, and it is a different question

```text
backend_unit_active      false - the API is not running
backend_loopback_only    true  - parsed from the unit file's ExecStart lines
tunnel_routes_backend    false - the ingress origin is the static preview
backend_publicly_exposed false
contained_by_deployment_posture true
```

Nothing reaches the API. That is what makes an unauthenticated header harmless
today — **not the flag**, which is on by default.

"The door is unlocked and the building is empty" is not a security property. It
is a true statement about right now, and it stops being true the moment somebody
starts the unit or adds it to the tunnel's ingress.

So the service reports both answers, separately: contained today, not safe ever.

## Detected, not declared

Unit state comes from `systemctl is-active`. The bind address is parsed from
every `ExecStart` line in the unit file. The tunnel ingress is read from the
cloudflared config.

Both detectors are tested against a temp tree in both directions — a unit binding
`0.0.0.0` reports `backend_loopback_only: false`, and an ingress carrying `:8000`
reports the backend as publicly exposed and containment as false. Without those,
a detector hardcoded to the reassuring answer would pass every other assertion.

## What replaces it

`rls_context_claim_guard_service` (Gate 111D). It refuses `dev_request_header` as
a claim source explicitly, so an auth-driven path cannot inherit this call by
routing a claim into it.

The header is not removed here. Removing it without auth to replace it would
break sixteen route modules for nothing, and the obligation to do so before
customer auth goes live is recorded on every result rather than left to memory.
