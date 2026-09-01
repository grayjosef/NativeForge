# 702 — Gate 133: login-live blockers and dev-header exposure survey

Measured before anything was implemented.

## Numbering

The brief asked for `699_GATE133_...`, `700_GATE133_DEV_HEADER_KILL_PLAN.md` and
`701`–`703`. Gate 132 already committed 699, 700 and 701. Recorded rather than
overwritten: this campaign has had one gate-number collision (130 ×2) and
silently reusing a document number would lose Gate 132's survey. Gate 133 uses
702–706.

## The brief's module names, mapped

Three of the modules named for survey do not exist:

```text
customer_auth_current_user_service      ABSENT
customer_identity_repository_service    ABSENT
org_membership_repository_service       ABSENT
```

The real modules with those responsibilities:

```text
api/auth.py::current_user                        the current-user route
dev_org_membership_bootstrap_service             identity + membership writes (Gate 132)
identity_org_session_resolution_service          membership reads -> organization (Gate 132)
postgres_membership_directory_service            the older membership read path
```

Fourth gate running where a brief names modules nobody built. The other seven
named modules do exist.

## Where JWKS validation happens

```text
oidc_token_verification_service.fetch_jwks()        the network fetch
oidc_token_verification_service.verify_oidc_token() the signature check
```

Called from exactly one place: `api/auth.py::callback`. No other module in
`src/` imports either function.

`verify_oidc_token` returns a rich result — `state`, `verified`, `issuer`,
`audience`, `kid`, `algorithm`, `verification_source` — and fails closed on
fourteen named states.

### Is it measured durably? **No.**

The verification result is assigned to a local named `verification` in the
callback and discarded when the request ends. No table records it; no migration
mentions a validation run. Grepping `alembic/versions/` for `auth_validation` or
`validation_run` returns nothing.

So the fact exists once per login, in a local, and then stops existing. That is
why `issuer_jwks_validated` is false: not because validation failed, but
because nothing wrote it down. `auth0_live_validation_runner_service` has
`provider_validated = False` as a literal, assigned once and never again — the
same shape Gate 132 fixed for two neighbouring gates.

## Where role mapping happens

```text
identity_org_session_resolution_service.resolve_session_organization()
```

Reads `nf_org_memberships` for one identity, filters to `state='active'`,
`revoked_at IS NULL` and not expired, requires a trusted `membership_source` and
a trusted `role_source`, and returns `roles`, `membership_source`, `role_source`
and `organization_id`.

### Is it measured durably? **Yes — but nothing asks.**

Unlike JWKS, role mapping's evidence *is* a row: the membership. It survives the
process because it is the thing itself rather than a report about an event. So
133C needs no new storage — it needs the activation gate to read what already
exists.

`role_mapping_passed` is currently a parameter of
`run_auth0_live_validation(role_mapping_passed=False)` that no caller passes.

## Where owner approval is represented

```text
NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL   env var
compared against
"MAYHEM_APPROVES_NATIVEFORGE_CUSTOMER_AUTH_ACTIVATION"
```

Compared, never reported — a wrong token is the same as no token. It is **not
set** on this machine.

That one approval currently gates *both* `customer_auth_live` and `login_live`,
which is the thing 133D has to separate. Approving "a demo login may be called
live" and approving "customer authentication is live for real Tribes" are not
the same decision, and one env var cannot express both.

## Why `login_live` is still false

`REQUIRED_LOGIN_GATES` has eleven conjuncts. Nine hold. Measured against the
running deployment:

```text
provider_configured               true
secret_present                    true
issuer_configured                 true
audience_configured               true
callback_route_available          true
session_cookie_policy_available   true
session_signing_key_ready         true
callback_session_validated        true    (Gate 132, from rows)
org_binding_passed                true    (Gate 132, from rows)

issuer_jwks_validated             FALSE   validation happens and is not recorded
role_mapping_passed               FALSE   membership rows exist and nothing reads them
owner_approval                    FALSE   one env var for two different decisions
```

## Which routes still consume `X-NF-Org-Id`

Derived by walking the FastAPI app and inspecting each route's resolved
dependency tree, rather than by grep — a route inherits the header through a
dependency it does not name.

```text
total API routes                  217
dev-header routes                 209
modules                            15
```

| module | routes | dependencies |
|---|---:|---|
| opportunity_discovery_routes | 84 | `get_org_context_with_db`, `require_demo_org_db`, `require_real_org_db` |
| source_ingestion_routes | 26 | same |
| pursuit_routes | 20 | same |
| sprint0_routes | 10 | same |
| grant_spark_routes | 9 | same |
| operator_workbench_advisory_routes | 8 | same |
| tribal_profile_routes | 8 | same |
| trust_routes | 8 | same |
| activation_routes | 6 | same |
| form_package_routes | 6 | same |
| nofo_extraction_routes | 6 | same |
| pursuit_brief_routes | 6 | same |
| spark_scoring_routes | 6 | same |
| stage12_guided_demo_routes | 4 | same |
| isolation_routes | 2 | `get_org_context_dev`, `require_demo_org`, `require_real_org` |

The three non-consumers: `auth` (5 routes, `/api/`), `backend_runtime_routes`
(2, `/backend/`), `health` (1).

Gate 122 recorded fourteen modules. It is fifteen — `isolation_routes` runs on
the *other* chain, `isolation_deps`, which classifies from the settings allowlist
rather than from `organizations.org_type`. That is the chain Gate 132's
reconciliation fixed.

## Which dev-header consumers are public through `/api/*`

**Zero.** Every one of the 209 is under `/v1/`.

```text
/api        5 routes    0 dev-header
/backend    2 routes    0 dev-header
/health     1 route     0 dev-header
/v1       209 routes  209 dev-header
```

### And that does not make them unreachable

The tunnel's ingress routes `^/api/.*` to the backend and everything else to the
stamped Vite preview on 5175. So `/v1/*` never reaches the backend by that
rule — but the **preview proxies it**:

```text
frontend/vite.config.ts, preview.proxy
  /v1            -> http://127.0.0.1:8000
  /docs          -> http://127.0.0.1:8000
  /openapi.json  -> http://127.0.0.1:8000
  /redoc         -> http://127.0.0.1:8000
```

Measured on the loopback, through the preview rather than the backend:

```text
GET http://127.0.0.1:5175/v1/isolation/demo-only   with X-NF-Org-Id   200
{"scope":"demo","org_id":"bbbbbbbb-cccc-dddd-eeee-ffffffffffff"}
```

So the backend's public surface is two paths, not one:

```text
/api/*                                 tunnel ingress        -> 8000
/v1/*, /docs, /openapi.json, /redoc    tunnel -> preview     -> 8000
```

**Gate 130's containment detector does not model the second one.** It reads the
cloudflared configs and asks whether any routes to the backend. Its answer
(`backend_publicly_exposed: true`) is correct today *because of the `/api/*`
rule* — and every dev-header route is outside that rule. If somebody removed the
`/api/*` ingress line, the detector would report the backend contained while the
preview proxy still exposed all 209 dev-header routes.

That is the third instance of this exact shape: Gate 130's detector reading
`~/.cloudflared/config.yml` while the live tunnel ran a different file, Gate
131's migration reader hardcoding one filename for a table spanning two, and now
a detector that models one of two hops.

## Which consumers are protected by Access

All of them, and only by Access. Measured from outside with no Access session:

```text
/v1/isolation/demo-only                    302 -> cloudflareaccess.com
/v1/nf/demo/orgs/<demo>/grant-sparks       302 -> cloudflareaccess.com
/api/auth/current-user                     302 -> cloudflareaccess.com
/health                                    302 -> cloudflareaccess.com
/api/auth/callback                         200   the one documented bypass
```

Access is a real boundary and it is an *edge* boundary, not an application one.
It gates who reaches the app; it does not stop a header from choosing an
organization once someone is through. Anybody in the Access policy can set
`X-NF-Org-Id` to any organization id and read that organization's rows.

## Do the auth routes consume the dev header?

No. `api/auth.py` mentions `X-NF-Org-Id` once, in prose, explaining that these
routes deliberately do not depend on it: "a replacement that depends on the
thing it replaces is not one."

## Exact `customer_auth_live` blockers

`REQUIRED_AUTH_GATES` is `REQUIRED_LOGIN_GATES` plus five. After the three
login blockers above:

```text
dev_header_disabled_for_production   FALSE   NF_DEV_ORG_HEADERS defaults true,
                                             209 routes depend on it, backend
                                             publicly reachable
invite_binding_passed                FALSE   never validated against a real flow
owner_approval                       FALSE   and this is the customer-auth
                                             approval, which is NOT what Gate
                                             132's authorization granted
```

Plus, outside the gate list: `verified_operational_binding` is false because the
demo organization's binding is a `demo_fixture`, which Gate 113's contract
requires — a demo binding may not carry a verifier.

## What can safely be activated in this gate

```text
CAN     issuer/JWKS validation evidence, recorded durably from the real callback
CAN     role-mapping evidence, derived from the membership rows that exist
CAN     a demo-scoped login activation decision, separate from customer auth
CAN     login_live, if and only if those three plus the nine existing hold
CAN     the dev-header exposure matrix and kill plan, derived from the app

CANNOT  customer_auth_live       needs the dev header gone from 209 routes
CANNOT  verified_operational_binding   refused by Gate 113 on a demo org
CANNOT  a real-org binding       explicitly forbidden
CANNOT  removing the dev header globally   209 routes would 401, and the demo
                                            shell is one of them
```

## The dev-header conversion, honestly scoped

Converting a route means it must get its organization from an authenticated
session. Exactly one identity has a membership, and the demo frontend sends no
cookie — it sends a header. So a converted route returns 401 to the demo UI.

`isolation_routes` is the only module that is not part of the demo product: two
routes whose entire purpose is proving demo/real separation. It is also on the
weaker `isolation_deps` chain. That makes it the safe first conversion, and
Gate 134 the place for the rest.
