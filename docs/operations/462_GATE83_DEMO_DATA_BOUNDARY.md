# 462 — Gate 83: Demo data boundary

Where the SC demo's data comes from, what it is allowed to claim, and why there
is no backend route.

## The data path

```text
per-section assembler services  (~60, now 61)
        |  build_<name>_demo_surface()  +  invariant check
sc_monday_demo_bridge_service.build_sc_customer_demo_bridge_payload()
        |  raises if ANY surface fails its invariants
write_sc_customer_demo_bridge_json()
        v
frontend/src/demo/sc_customer_demo.json     committed, ~3.5 MB
        |  static module import, bundled at build time
ScCustomerDemoPage.tsx
```

Nothing is fetched at view time. The page runs with no API, no auth, no
database and no network.

## Why there is no backend route

Gate 83C allows a read-only demo route "if the SC demo uses backend routes". It
does not. Adding `GET /api/demo/sc-negative-intelligence` would:

- introduce a live code path serving customer-facing eligibility content where
  today there is only a static artifact;
- require the same claim-boundary enforcement the bridge already performs;
- add attack surface to a demo whose main safety property is that it has none.

**Generation-time enforcement is strictly stronger than runtime enforcement.**
A surface that violates its claim boundary raises inside
`build_sc_customer_demo_bridge_payload`, so the bad payload never reaches the
committed JSON. A runtime route could only fail *after* a request, in front of a
viewer.

The decision is therefore documented rather than implemented, per the gate's own
allowance.

## What the demo may claim

Allowed, because it is true of the synthetic fixture:

```text
this notice text appears to limit eligibility to federally recognized tribes
the cited sentence, quoted, with its span and artifact hash
the same notice gives different answers to different applicant classes
the opportunity remains visible
```

Forbidden, and enforced by invariants on every build:

```text
synthetic_demo            must be true
live_coverage_claimed     must be false
source_monitored          must be false
freshness_claimed         must be false
url_fetch_performed       must be false
excluded_hidden           must be false
final_eligibility_claimed must be false
not_eligible_asserted     must be false
```

The page displays these flags rather than only carrying them, so a viewer sees
the boundary without reading the source.

## Fixture boundary

The surface reads exactly one file:

```text
tests/fixtures/nofo_artifacts/synthetic_notice.html
```

It is committed, declares itself a test fixture on line 1, and claims no
opportunity number. `is_recorded_fixture` is confirmed through
`hermetic_test_guard_service.is_source_controlled` rather than asserted, and the
surface's `artifact_hash` is checked against the file on disk by test.

Reading a committed fixture from `src/` has precedent —
`hermetic_test_guard_service.RECORDED_TRANSPORT_DIR` is
`tests/fixtures/grants_gov`.

`frontend/src/demo/` is **not** watched by
`scripts/verify_nativeforge_fixture_cleanliness.sh`, which covers `fixtures/`,
`tests/fixtures/` and `src/nativeforge/data/`. Regenerating the demo JSON is an
intended output. The artifact fixture it reads *is* watched and stays
byte-identical.

## A finding: the demo payload is not deterministic

Two consecutive builds of `build_sc_customer_demo_bridge_payload()` produce
different bytes. The churn is in generated identifiers and timestamps across the
pre-existing surfaces:

```text
review_item_id  linked_item_id  checklist_item_id  question_id
approval_id  probe_run_id  created_at  nonce  timestamp  event_id  run_id
```

Regenerating the JSON for this gate produced 567 insertions and 476 deletions,
the large majority unrelated to the change.

This is **pre-existing behaviour, not introduced by Gate 83**, and it was not
fixed here: it spans ~60 assembler services and is a separate piece of work.
Two consequences worth knowing:

- A demo-payload diff cannot be reviewed meaningfully. "What changed in this
  commit" is not answerable from the JSON.
- The committed artifact is not reproducible from its inputs, which weakens the
  auditability story for this file specifically. The stamped build
  (`nativeforge-build-sha`, `source_dirty`) still pins *which commit* produced
  the deployed bundle.

The Gate 83 surface itself **is** deterministic — it derives only from a
committed fixture — and a test pins that, so this one section can be diffed and
audited even while the surrounding payload cannot.

Recommended follow-up: thread a seed or a fixed clock through the assembler
services so the payload becomes reproducible. That would make the whole demo
artifact auditable rather than only this section.

## What is not claimed anywhere in this gate

No source was identified, fetched, seeded or monitored. No real notice was
parsed. No opportunity, eligibility, ineligibility, amendment status or source
freshness was fabricated. The pilot boundary is unchanged.
