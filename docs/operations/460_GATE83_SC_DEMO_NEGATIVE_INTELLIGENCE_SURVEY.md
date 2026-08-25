# 460 — Gate 83A: SC demo surface and data path survey

## Current demo data flow

The SC customer demo is **static-payload driven**. Nothing is fetched at view
time.

```text
per-section assembler services
  build_<name>_demo_surface()  +  <name>_demo_surface_invariant_failures()
        |
sc_monday_demo_bridge_service.build_sc_customer_demo_bridge_payload()
  composes ~60 surfaces, raising if any surface fails its invariants
        |
write_sc_customer_demo_bridge_json()
        v
frontend/src/demo/sc_customer_demo.json      (3.5 MB, committed)
        |
loadScCustomerDemo.ts  ->  static JSON import, typed by scCustomerDemoTypes.ts
        v
ScCustomerDemoPage.tsx (3,872 lines)  <-  App.tsx, surface === "sc_customer_demo"
```

Route: `/?view=sc_customer_demo`, resolved in `App.tsx:944` and typed in
`viewSurface.ts`.

## Backend route status

**There is none, and none is needed.**

The page imports the payload as a module (`import demoJson from
"./sc_customer_demo.json"`), so it is bundled at build time. It runs with no
API, no auth, no database, and no network — which is exactly the property that
makes the demo safe to serve from a loopback preview behind Cloudflare Access.

Adding `GET /api/demo/sc-negative-intelligence` would introduce a live code path
serving customer-facing eligibility content where today there is only a static
artifact, and it would need the same claim-boundary enforcement the bridge
already performs at generation time. It would add surface area and remove a
guarantee. Gate 83C is therefore satisfied by **documenting the decision**, per
the gate's own allowance.

The generation-time invariant check is strictly stronger than a runtime one: a
surface that violates its claim boundary raises during
`build_sc_customer_demo_bridge_payload`, so the bad payload never reaches the
committed JSON at all.

## Safest insertion point

Follow the established pattern exactly:

1. New assembler `sc_demo_negative_intelligence_service.py` exposing
   `build_sc_demo_negative_intelligence_surface()` and
   `sc_demo_negative_intelligence_invariant_failures()`.
2. Compose it in the bridge alongside the other ~60 surfaces, raising on
   invariant failure.
3. Add its type to `scCustomerDemoTypes.ts`.
4. Render a section in `ScCustomerDemoPage.tsx`.
5. Regenerate `sc_customer_demo.json`.

`frontend/src/demo/` is **not** covered by
`scripts/verify_nativeforge_fixture_cleanliness.sh`, which watches `fixtures/`,
`tests/fixtures/` and `src/nativeforge/data/`. Regenerating the demo JSON is an
intended output, not a fixture mutation — but the Gate 82 artifact fixtures the
new surface *reads* are watched, and must stay byte-identical.

## Where the evidence comes from

The surface runs the **real Gate 82 pipeline over the real Gate 82 fixture**:

```text
tests/fixtures/nofo_artifacts/synthetic_notice.html
  -> notice_ingestion_pipeline_service.ingest_notice_artifact()
  -> Gate 81 extraction / eligibility parse / amendment detection
```

This matters. The alternative — hand-writing a quote into a demo payload —
would produce a screen that *looks* identical while proving nothing, and would
be indistinguishable from a mockup. Running the pipeline means the quote on
screen is the sentence the parser actually cited, at the span it actually found,
from the artifact whose hash is displayed beside it. If the parser regresses,
the demo changes or the invariants fail.

Reading a committed fixture from `src/` has precedent:
`hermetic_test_guard_service.RECORDED_TRANSPORT_DIR` is
`tests/fixtures/grants_gov`, and `nofo_extraction_pilot_extractor_service` reads
`fixtures/nofo_extraction_pilot/`.

## Existing components to reuse

There is no callout/warning component. The page is built from plain
`<section>` / `<div>` elements with `data-testid` hooks and `nf-*` class names:

```text
.nf-sc-demo-section   section wrapper
.nf-sc-demo-why       "what NativeForge explains" explanatory paragraph
.nf-muted             claim-flag lines
```

`sc-demo-eligibility-evidence` (recognition-tier evidence) is the nearest
existing section and the natural neighbour for the new one.

Note the house style is diagnostic — `key=value` strings and JSON dumps aimed at
an operator reading flags. Gate 83 asks for customer-readable prose and an
evidence quote, so the new section is written as prose while keeping the
`data-testid` conventions the vitest and Playwright smokes depend on.

## What must remain synthetic / demo-only

Everything. The notice is `synthetic_notice.html`, which declares itself
`SYNTHETIC TEST FIXTURE - NOT A REAL NOTICE` on line 1 and states that no
opportunity number is claimed.

The surface must carry and the page must display:

```text
synthetic_demo         true
live_coverage_claimed  false
source_monitored       false
freshness_claimed      false
```

The exclusion is real *about the synthetic text*. It is not a claim about any
actual programme, and the wording must not let a viewer conclude otherwise.

## Gaps Gate 83 fills

- Four gates of capability (79–82) that no customer surface displays.
- No screen anywhere shows an **evidence quote** for an exclusion.
- No screen shows that the answer **changes with applicant class** — the single
  most important consequence of the recognition-tier split.
- No screen states *why* an excluded opportunity is still listed.

## Deliberately not touched

- No backend route, for the reasons above.
- No change to Gate 81/82 service behaviour — the surface consumes them.
- No change to scoring; this is presentation of an existing result.
- The Gate 82 artifact fixtures stay byte-identical.
- The demo's existing sections and their `data-testid` hooks.
