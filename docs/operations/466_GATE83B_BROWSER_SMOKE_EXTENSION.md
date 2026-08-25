# 466 — Gate 83B: Browser smoke extension

`frontend/e2e/sc_customer_demo.smoke.spec.ts`, run against the built bundle by
`npx playwright test --project=chromium`.

## Why extend it

Gate 83 covered the negative-intelligence section with vitest, which renders the
component to static markup. That proves the component emits the right strings
from the right payload. It does not prove the section survives the **built,
stamped bundle** loaded by a real browser — bundling, CSS, hydration and the
static JSON import are all outside vitest's reach.

The Playwright smoke is what the demo actually is: a stamped `dist/` served on
loopback behind Cloudflare Access.

## What the browser smoke now covers

Two new tests, alongside the existing surface smoke.

### `renders applicant-class negative intelligence with cited evidence`

```text
sc-demo-negative-intelligence          section is visible
sc-demo-ni-headline                    "Relevant does not mean eligible"
sc-demo-ni-row-state_recognized_tribe  the excluded class renders
sc-demo-ni-status-state_recognized_tribe        excluded_by_evidence
sc-demo-ni-quote-state_recognized_tribe         the cited sentence
sc-demo-ni-row-federally_recognized_tribe       the other tier renders
sc-demo-ni-status-federally_recognized_tribe    eligible
sc-demo-ni-class-contrast              applicant_class_changes_the_answer=true
sc-demo-ni-visibility-note             "remain visible"
   (row)                               remains_visible=true
sc-demo-ni-synthetic-label             synthetic_demo=true
sc-demo-ni-no-live-coverage            live_coverage_claimed=false
                                       source_monitored=false
```

The section is scrolled into view first, so the assertions describe what a
viewer would actually see rather than what merely exists in the DOM.

### `never tells the customer they are legally ineligible`

Reads the whole rendered body and asserts it does **not** contain:

```text
you are not eligible
you are ineligible
legally ineligible
```

and does contain `not a legal determination`.

This is the same guard as the vitest one, but applied to the real page. It is
worth duplicating: the phrasing rule matters more than most assertions here,
because this language is shown to a tribal grant office, and the guard already
caught one violation — the Gate 83 review note originally used the banned phrase
inside a negation, and the copy was reworded rather than the guard loosened.

## Keeping it stable rather than brittle

- Assertions target `data-testid` hooks and short, load-bearing phrases, never
  full sentences or layout.
- Status is asserted as the machine value (`excluded_by_evidence`) rather than
  the display label, so a wording change to the label does not fail the smoke —
  but a change to the *verdict* does.
- The quote is matched on the distinctive fragment
  `federally recognized Indian tribes`, not the full sentence with its
  whitespace and quotation marks.
- No timing assumptions beyond Playwright's own auto-waiting.

## What it does not cover

The smoke runs on loopback against the stamped bundle. It does not prove the
post-Access public render — the strict-public verifier still reports
`post_access_render_requires_human_confirmation`, and that remains an owner
check.

It also asserts nothing about visual design. The section is rendered in the
page's diagnostic house style, and a design pass would change the markup this
smoke reads; the `data-testid` hooks are the contract that should survive it.

## Result

```text
4 passed  (was 2)
  NM/WA operator demo smoke
  SC customer demo — required Monday surfaces
  SC customer demo — applicant-class negative intelligence   [new]
  SC customer demo — never claims legal ineligibility        [new]
```
