# 707 — Gate 134: dev-header conversion survey

Measured before anything was converted.

## Numbering, and the brief's file names

The brief asked for `704_GATE134_DEV_HEADER_CONVERSION_SURVEY.md` and
`705`–`707`. Gate 133 committed 702–706 yesterday, so Gate 134 uses 707–710.
Second numbering collision in three gates; recorded rather than overwritten.

The brief also cited `700_GATE133_DEV_HEADER_KILL_PLAN.md` and
`703_GATE133_AUTH_READINESS_DELTA.md`. The real files are
`703_GATE133_DEV_HEADER_KILL_PLAN.md` and
`706_GATE133_AUTH_READINESS_DELTA.md`.

## The measurement that decided how aggressive this could be

The brief's two instructions looked like they were in tension: *convert
aggressively* and *do not break the public demo shell*. Gate 133 recorded that
the demo shell "sends `X-NF-Org-Id` and no cookie", so converting a module it
calls would return 401 to the demo.

They were not in tension, and it took one measurement to see why.

### The deployed bundle calls the viewer's own machine

```ts
// frontend/src/m0ApiClient.ts
export function apiFetchBase(): string {
  if (import.meta.env.DEV) return "";
  const fromEnv = import.meta.env.VITE_API_BASE as string | undefined;
  return fromEnv?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
}
```

`VITE_API_BASE` is not set at build time — not in `scripts/`, not in any
`frontend/.env`. The built bundle contains the literal `http://127.0.0.1:8000`,
so every API call the deployed demo makes targets **the viewer's own loopback**,
not the deployment.

### And the demo surfaces make no calls at all

```ts
const offlineDemoSurface =
  surface === "sc_customer_demo" || surface === "nm_wa_operator_demo";
...
if (offlineDemoSurface) return;   // in every API-firing effect
```

`App.tsx` says why: firing them "means the viewer's browser probes
`http://127.0.0.1:8000` on THEIR OWN machine — which can never succeed, is mixed
content on an https page, and puts eight red errors in front of a buyer".

Measured in a browser against the live deployment: `?view=workspace` and
`?view=sc_customer_demo` both produced **zero** `/v1` network requests. The SC
demo renders and is labelled "Curated demo data · offline".

So the public demo cannot break, because it never reaches these routes.

## Who does call them

```text
local development     vite dev server, base "" -> same-origin -> proxied to 8000
the Python suite      TestClient
an operator with curl
```

The cost was entirely in the tests, and it was uniform.

## The remaining consumers, per module

Derived by walking the registered routes and reading each one's resolved
dependency tree — a route inherits the header through a dependency it never
names, and grepping the fourteen route modules for `X-NF-Org-Id` finds none of
them.

| order | module | routes | dependency | public via preview proxy | replacement | risk | test files |
|---|---|---:|---|---|---|---|---:|
| 1 | `stage12_guided_demo_routes` | 4 | `require_demo_org_db`, `require_real_org_db` | yes | available | low | 1 |
| 2 | `trust_routes` | 8 | same | yes | available | low | 2 |
| 3 | `activation_routes` | 6 | same | yes | available | medium | 2 |
| 4 | `form_package_routes` | 6 | same | yes | available | medium | 2 |
| 5 | `nofo_extraction_routes` | 6 | same | yes | available | medium | — |
| 6 | `pursuit_brief_routes` | 6 | same | yes | available | medium | — |
| 7 | `spark_scoring_routes` | 6 | same | yes | available | medium | 5 |
| 8 | `tribal_profile_routes` | 8 | same | yes | available | medium | 7 |
| 9 | `operator_workbench_advisory_routes` | 8 | same | yes | available | high | — |
| 10 | `grant_spark_routes` | 9 | same | yes | available | high | 11 |
| 11 | `sprint0_routes` | 10 | same | yes | available | high | 9 |
| 12 | `pursuit_routes` | 20 | same | yes | available | high | 4 |
| 13 | `source_ingestion_routes` | 26 | same | yes | available | high | — |
| 14 | `opportunity_discovery_routes` | 84 | same | yes | available | highest | — |

```text
total routes          217
dev-header routes     207
path roots            /v1 for all 207
```

Every module uses the same two dependencies, imported the same way, which is
what makes a conversion an import swap rather than a rewrite.

## Required replacement

`deps_customer_auth` exists from Gate 122 and was upgraded in Gate 133F, but its
guards return `OrgContext` through a different call shape and it was written for
routes that would take it directly. A drop-in with the *same names' shapes* is
what 207 routes need, so Gate 134E adds
`api/customer_org_context_dependency.py`:

```text
require_demo_org_db   ->  require_demo_org_session
require_real_org_db   ->  require_real_org_session
```

Same return type, same 403 semantics, same `apply_org_rls_gucs` call, and no
header parameter anywhere.

## Test coverage present

Fifty-one test files share one helper, character for character:

```python
def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}
```

Four more have variants: a two-argument form carrying a role header, a
no-argument form, and two inline dicts. That is the whole surface, so the test
conversion is a one-line change per file plus a shared helper that seeds an
organization, an identity and a membership and returns a signed session in the
same header-dict shape.

Excluded by name: the eight files whose subject *is* the header. Rewriting them
would delete the assertion.

## Recommended conversion order

Gate 133's, unchanged — least risky first, smallest surface first within a band.
The survey found no reason to depart from it, and one reason to go faster than
it assumed: the demo does not call any of them.
