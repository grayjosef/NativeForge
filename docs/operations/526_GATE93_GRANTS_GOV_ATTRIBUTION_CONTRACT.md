# 526 — Gate 93C: Grants.gov attribution contract

**No collectors were activated. No URLs were fetched. No live coverage is
claimed.** The attribution is a standing notice, not a claim that anything is
being collected — the trust manifest states `grants_gov_collector_active:
false` alongside it.

## The required notice, verbatim

```text
This product uses the Grants.gov API but is not endorsed or certified by the
U.S. Department of Health and Human Services.
```

The Grants.gov API Terms require that services using the API *"display the
following notice prominently within the application."* This is a **runtime,
customer-visible precondition**, not a collector implementation detail: a
collector that fetches correctly and a UI that shows the results without the
notice is still non-compliant.

## What Gate 92 actually had

Gate 92 stated the attribution requirement in three documents and stored the
string in one Python constant. The Gate 93A survey checked what that bought:

```text
grep -ri "endorsed or certified" frontend/   ->  no matches
```

The notice was not runtime-visible and not customer-visible. It could not have
been seen by anyone.

## Docs are not a surface

`ATTRIBUTION_SURFACES` distinguishes where a string lives:

```text
runtime_payload   in a response a customer's browser receives   COUNTS
rendered_ui       drawn on screen                               COUNTS
service_constant  a Python constant                             does not count
documentation     a markdown file                               does not count
```

`attribution_is_customer_visible` requires at least one of the first two, and
`attribution_satisfied` requires **verbatim text AND customer visibility** —
both, with invariants for each. A contract claiming satisfaction from
documentation alone fails.

## Verbatim means `==`

Not normalized whitespace, not case-folded, not "contains". A paraphrase that
means the same thing is a different string and fails, because the terms name a
notice rather than an idea. `verify_attribution_text` reports *how* a candidate
differs so a reviewer can tell a reflow from a rewrite:

```text
present_and_verbatim   exact match
altered                whitespace, casing, or wording differs
paraphrased            mentions Grants.gov but is not the notice
missing                absent or empty
```

Tested rejections include the notice with its trailing period dropped, lowercased,
uppercased, respaced, and with `U.S.` shortened to `US`.

## Where it is wired

```text
trust_surface_service.build_trust_manifest()
  -> "source_attribution": {"grants_gov_notice": ATTRIBUTION_TEXT, ...}
     served at /trust  (api/trust_routes.py)
     rendered by frontend/src/components/TrustCenterCard.tsx  (App.tsx:927)
     as <p className="nf-trust-attribution" data-testid="nf-grants-gov-attribution">
```

The component reads the string **from the manifest** and never hardcodes it — a
test asserts the literal text does *not* appear in the component, so there is
exactly one source of the string and it cannot drift.

`grants_gov_attribution_service` reads the manifest and verifies the notice
survived. It does not build the manifest, so the check cannot pass by
construction.

## Gating source output

`grants_gov_output_may_be_customer_visible` refuses to surface data from any of:

```text
GRANTS-GOV-EXTRACT          grants_gov_daily_extract
GRANTS-GOV-SEARCH2          grants_gov_search2_fetch
```

without a satisfied attribution contract. Non-Grants.gov sources are unaffected —
Federal Register data does not require this notice, and pretending it did would
be inventing an obligation.

## What is still missing

The notice is rendered on the Trust Center card. It is not yet on every surface
that could eventually show Grants.gov data, because no surface shows Grants.gov
data — no collector is active. When a Phase 1 collector is built, the surfaces
that render its output each need the notice, and the contract should be extended
to enumerate them rather than checking one card.
