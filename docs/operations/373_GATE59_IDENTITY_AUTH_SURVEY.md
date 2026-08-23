# 373 — Gate 59A: Identity / auth survey

Status: survey complete.

## Files inspected

**25 existing Auth0/OIDC services** — this area has substantial prior art and
Gate 59 composes with it rather than restating it:

`auth0_preflight_service`, `auth0_mode_detector_service`,
`auth0_live_validation_runner_service`, `auth0_live_validation_assembler_service`,
`auth0_login_rbac_validation_service`, `auth0_mode_b_execution_service`,
`auth0_mode_b_live_unlock_service`, `auth0_validation_smoke_service`,
`auth_context_resolver_service`, `external_auth_context_adapter_service`,
`gate29_auth0_real_input_service`, `gate35_auth0_ingest_service`,
`login_claim_resolver_service`, `login_live_promotion_gate_service`,
`oidc_callback_validation_harness_service`, `oidc_config_schema_service`,
`oidc_identity_mapper_service`, `oidc_live_path_assembler_service`,
`session_tenant_enforcement_service` (+ assemblers).

API layer: `api/isolation_deps.py`, `api/org_context.py`, `api/deps.py`,
`api/deps_db.py`, `api/tenant_guard.py` (Gate 58).
Settings: `lib/settings.py`, `lib/demo_isolation.py`.

## Current identity source

**There is none for customers.** What exists:

| Mechanism | What it proves |
| --- | --- |
| `X-NF-Org-Id` header + `NF_DEMO_ORG_IDS` allowlist | which demo/real org bucket to route to |
| `require_demo_org_db` / `require_real_org_db` | plane isolation |
| `tenant_guard` (Gate 58) | path org matches context org |

`OrgContext` carries exactly two fields: `org_id` and `org_type`. **No subject,
no email, no role, no membership.** `isolation_deps.py` says so itself:

> Production must replace this with JWT + organizations.org_type lookup.

`lib/settings.py` contains **no** OIDC settings at all — the OIDC services read
`os.environ` directly.

## Current dev/demo header behaviour

`get_org_context_dev` resolves org from `X-NF-Org-Id`, validates it is a UUID,
and looks it up against the demo allowlist. Notably it already refuses to accept
a second header asserting `org_type`, with the comment that the allowlist is the
source of truth — the right instinct, and Gate 59 extends it to roles.

When `NF_DEV_ORG_HEADERS=false` these routes return 503.

## Auth0/OIDC stubs

Rich, and reusable:

- `auth0_preflight_service` reads presence of `OIDC_ISSUER`, `OIDC_CLIENT_ID`,
  `OIDC_CLIENT_SECRET`, `OIDC_AUDIENCE`, `OIDC_CALLBACK_URL`, `OIDC_LOGOUT_URL`,
  `OIDC_ALLOWED_ORIGIN` — presence only, values never returned.
- `oidc_config_schema_service` models config without storing secret values.
- `login_live_promotion_gate_service` defines **10 required gates** before
  `login_live` may be claimed, including `issuer_jwks_validated` and
  `callback_session_validated`.
- `oidc_identity_mapper_service` maps claims to an auth context.

**Env naming discrepancy, resolved deliberately.** The repo standardised on
`OIDC_*` (19 references). The Gate 59 brief specified `NATIVEFORGE_OIDC_*`.
Introducing a second convention silently would be a trap for whoever supplies
the real credentials, and ignoring the brief would be unhelpful, so
`oidc_readiness_service` accepts **both**, canonical `OIDC_*` first, and reports
which key satisfied each requirement via `config_source_keys`.

## Membership / role lookup

**None exists.** No membership table, no directory, no role claim mapping into
`OrgContext`. `org_tenant_seat_model_service` (Gate 51) models memberships as a
contract over caller-supplied state; nothing populates it from a store.

## Gaps

1. No authenticated subject on any request.
2. No membership resolution — so Gate 51's seat/membership model has no input.
3. No role resolution — so Gate 53's capability matrix has nothing to key on.
4. No token verification path. No JWKS fetch, no signature check anywhere.
5. Nothing distinguishes "Cloudflare Access session" from "customer login" in
   code, which is the single most dangerous conflation available here.

## Safest seam for real identity

```text
request
  -> resolve_request_identity()        # reads headers, trusts almost nothing
  -> request identity contract         # states + trusted/untrusted separation
  -> OrgContext (existing)             # plane + org routing
  -> tenant_guard (Gate 58)            # org-scoped access, now identity-aware
  -> enforce_capability (Gate 58)      # only once a role is TRUSTED
```

The seam must be additive: attaching the identity dependency to a route changes
no behaviour on its own. It only makes a trustworthy identity available and
records what the client asserted. That property is what lets it land while
`login_live` is still false.

Deliberately **not** done: wiring `enforce_capability` to a live route. With no
verifier, every identity is anonymous, demo_operator or unverified, so a live
capability check would deny every request including the demo. See doc 376.
