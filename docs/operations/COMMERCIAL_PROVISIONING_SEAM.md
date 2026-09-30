# Commercial provisioning seam (NativeForge reference)

## Lifecycle

```text
DEMO → commercial_intent → entitlement_pending → provisioning → organization_setup → active
```

Commercial intent is **not** active entitlement. Entitlement is **not** Tribal authority.

## Customer APIs

- `POST /api/commercial-provisioning/intent` — demo lane only; records intent.
- `GET /api/commercial-provisioning/status` — authenticated caller’s latest request.
- `GET /api/commercial-provisioning/contract` — future payment-provider hook (documented).

## Operator path (no checkout)

Header: `X-NF-Commercial-Operator-Approval: MAYHEM_APPROVES_NATIVEFORGE_COMMERCIAL_PROVISIONING`  
Env: `NF_COMMERCIAL_OPERATOR_APPROVAL` must match the same token.

`POST /api/commercial-provisioning/operator/fulfill` with `request_id`, `operator_actor` (UUID), optional `existing_organization_id` to claim.

Steps: authorize `RECORD_LICENSE_PURCHASE` → create or claim org → persist Gate 178 ledger → operator-approved membership → `organization_setup`.

Ambiguous display-name matches against existing **real** orgs fail closed (`blocked_ambiguous_org`).

## Workspace lane

Lane remains `demo` until the user holds a **verified membership session** (typically sign in again after provisioning). Intent and entitlement alone never switch the lane.

## Production smoke

Do not fabricate production entitlement. Safe smoke: unaffiliated user submits intent (or reads status), demo summary stays 401/403 for org feed without membership.
