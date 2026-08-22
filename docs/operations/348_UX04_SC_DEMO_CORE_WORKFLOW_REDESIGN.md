# 348 — UX-04 SC Demo and Core Workflow Redesign

Status: implemented
Route: `/?view=sc_customer_demo` (preserved; not renamed, not gated, not removed)
Files: `frontend/src/pages/ScCustomerDemoPage.tsx`, `frontend/src/index.css`

## The constraint that shaped the design

The SC page is 95 sibling `<section>`s. A Playwright contract pins ~90 of them as
**visible** and pins ~86 `data-testid="sc-demo-*-flags"` elements as containing exact
key=value substrings (`live_ingest_claimed=false`, `monday=GO`, `production=NO_GO`, …).

So the machine flags could not be deleted, and could not be folded into a closed
`<details>` — `toBeVisible()` would fail. The redesign therefore changes **rank, not
content**. Playwright's `toBeVisible()` does not require in-viewport, which makes
relocation below the buyer surface safe.

Two consequences:

1. Almost all of the visual change is delivered through the shared `.nf-sc-demo-section`
   class and a `[data-testid$="-flags"]` attribute selector — no rewrite of 3780 lines of
   pinned JSX, and no way to silently break the contract.
2. Ordering is done with CSS `order` on `data-testid` selectors rather than by moving JSX.

JSX changes were limited to: the hero block, one ledger divider element, one command-strip
`<nav>`, and five `id` attributes for anchors.

## Required structure — implementation

### 1. Executive hero — done

Rebuilt as a navy band with a copper top rule and a two-column layout at ≥1024px:

- **Left:** `NativeForge` brandline · serif display H1 **"Native-relevant grant
  intelligence and pursuit command center"** · the environment label (the payload
  `data.title`, which used to *be* the H1) · the Monday/SC kicker · three claim badges ·
  the opening line · the five-verb product promise.
- **Right:** the trust-chip strip, both claim-boundary panels, the presenter note, and the
  machine-verifiable evidence registers.
- **Full width below:** the command strip.

Badges: `Limited external demo` (copper), `South Carolina demo environment` (neutral),
`Production rollout blocked` (maroon). No green anywhere in the hero.

Hero height went from ~2,600px to **991px** at 1440 — the entire executive hero plus the
command strip now fits on one screen.

**Copy added** (handoff direction, verbatim intent):
> Find the right Native-relevant opportunity. Understand the requirements. Prove
> eligibility. Build the evidence-backed package. Keep human approval in control.

### 2. Command strip — done

A new five-tile `<nav>` in the hero, each tile numbered `01`–`05` with a copper top rule,
anchored to the section it names:

| Tile | Anchor | Target |
| --- | --- | --- |
| 01 SC opportunity intelligence | `#nf-opportunity-intelligence` | `sc-demo-opportunity-engine` |
| 02 Eligibility evidence | `#nf-eligibility` | `sc-demo-eligibility-evidence` |
| 03 Authority-to-apply | `#nf-authority` | `sc-demo-applicant-authority` |
| 04 Evidence package readiness | `#nf-readiness` | `sc-demo-readiness-queue` |
| 05 Customer feedback and reporting | `#nf-feedback` | `sc-demo-feedback-loop` |

This is also the answer to the UX-01 §5 finding that a 78,000px document had no navigation
of any kind. `scroll-margin-top` is set on the anchors; smooth scroll is disabled under
`prefers-reduced-motion`.

### 3. Opportunity intelligence — done

`sc-demo-opportunity-engine` (which contains the eligibility evidence block),
`sc-demo-opportunities`, `sc-demo-review-table`, `sc-demo-combined-summary`,
`sc-demo-profiles` and `sc-demo-nofo-showcase` are hoisted to orders 6–11, the wide ones
spanning both columns. State vs federal distinction, fit confidence, source/freshness/
provenance and the honest-unknown fields are unchanged in content — they are now the
second thing on the page instead of appearing after 23 gate-closeout sections.

**Data-loss defect fixed.** The review table was 1751px wide inside a 1040px card with
`overflow-x: visible` under an ancestor `overflow-x: clip`: 711px of columns were
unreachable at every breakpoint. Tables now scroll inside their own card
(`display:block; overflow-x:auto`) with sticky, uppercase column headers and zebra rows.
Verified at all four breakpoints: the table reports `overflowX: auto` and its content is
reachable.

### 4. Eligibility / recognition and authority — done

`sc-demo-eligibility-evidence` rides with its parent card at order 6 and carries the
`#nf-eligibility` anchor. `sc-demo-applicant-authority` was sitting in the middle of the
gate register; it is hoisted to order 12 as one of the seven buyer surfaces.

Federal vs state-only recognition, "human review required" and "not a final legal
determination" are unchanged. `final_eligibility_claimed=false` and
`submission_authority_claimed=false` remain rendered and visible.

### 5. Evidence binder / package readiness — done

`sc-demo-pursuit-workspace` (13), `sc-demo-application-checklist` (14),
`sc-demo-readiness-queue` (15), `sc-demo-evidence-intake` (16).

These were the tallest cards on the page: each stacked three or four
`article.nf-sc-demo-nofo-card` detail blocks of 1,100–1,600px vertically inside a 592px
column, producing single cards up to **5,878px** tall. Sections containing those articles
now span the full width and lay them out as a nested `auto-fill / minmax(19rem)` grid, so
per-opportunity detail flows horizontally. Tallest card is now **2,890px** — a 51% cut on
the worst offender. The articles themselves became real nested cards (inset surface,
hairline, radius) instead of a `border-top` separator.

Required items, missing evidence and owner action are unchanged. No fabricated facts were
added anywhere.

### 6. Feedback / reporting — done

`sc-demo-feedback-loop` hoisted to order 17 and anchored from command tile 05.
`slack_live_sent_claimed=false` remains rendered — the Slack alert path is described as
existing, and "sent" is still not claimed.

### 7. Trust rail — done

`sc-demo-missing-data` (18), `sc-demo-provenance` (19), `sc-demo-customer-data-policy`
(20), `sc-demo-claim-guardrails` (21, full width), `sc-demo-buyer-trust-views` (22, full
width). Data sovereignty, audit trail, human approval, export/delete posture and the
pending production gates all keep their existing content.

## The evidence register — the central new pattern

Every `data-testid$="-flags"` element inside `.nf-sc-customer-demo` is now rendered as a
machine-verifiable evidence register: monospace, `--nf-t-xs`, inset surface, hairline
border, 2px copper left rule, its own horizontal scroll, and a generated
`MACHINE-VERIFIABLE` micro-label. On the navy hero the register inverts to a dark inset.

This converts the audit's single worst content problem into an asset. Every flag is still
present, still exact, still visible — but it now reads as cryptographic-style proof
subordinate to a human sentence, rather than as leftover debug text at body weight.

The `Owner Action Required` line gets a held-gate treatment: maroon left rule and tinted
wash, stated as deliberately held rather than as an error.

## The gate ledger

A new band divider (`sc-demo-ledger-divider`, order 30) separates the buyer surface from
the ~70 remaining engineering gate sections:

> **Evidence and gate register — Every gate, including the ones still held**
> Below is the complete build and claim record behind this demo — authority, storage,
> authentication, security, coverage and pilot gates, each with its machine-verifiable
> flags. Held gates stay held and are never shown as passing. This register is written for
> operators, auditors and technical reviewers; the buyer surface above is the product.

Nothing below the divider is hidden, collapsed, greened or removed. The internal
vocabulary that UX-01 §3.4 flagged (`gate33`, `Mode B`, `SCA`) is still there — it is now
correctly *framed* as an operator/auditor register rather than presented as the customer
product surface.

## Copy discipline

- The `<h1>` is no longer the internal artifact name "SC Customer Demo — Curated State +
  Federal Opportunities"; that string is retained as the environment label under the
  headline (still `data-testid="sc-demo-title"`).
- The presenter talk-track is moved into a collapsed **Presenter note** disclosure. It is
  asserted only as `html).toContain("sc-demo-buyer-talk-track")` — markup presence, not
  visibility — so this is contract-safe. The audience no longer reads the speaker's notes.
- The claim boundary and advisory banner were `.nf-muted` (the lightest grey on the page).
  They are now labelled panels — **"What this is, exactly"** and **"Scope of this demo"** —
  with copper rules. Honesty is the differentiator and is now styled like it.
- No forbidden phrasing introduced. No "AI-powered", no "revolutionary", no "autonomous
  grant writer", no "production-ready", no "pilot-ready", no unqualified "secure".

## Measured result

| | before | after | change |
| --- | --- | --- | --- |
| Page height @1440 | 78,256px | **51,253px** | −34.5% |
| Page height @1280 | 78,256px | 51,253px | −34.5% |
| Page height @834 | 78,256px | 73,527px | −6% |
| Page height @390 | 139,675px | 117,799px | −15.7% |
| Hero height @1440 | ~2,600px | **991px** | −62% |
| Tallest single card | 5,878px | 2,890px | −51% |
| Doc horizontal overflow | none | none | held |
| Unreachable table columns | 711px | **0** | fixed |
| Buyer error banner on route | yes | **no** | fixed |
| Sections rendered | 95 | 95 | unchanged |

The page is still long — 95 sections of genuine evidence is inherently long, and none of it
was cut. What changed is that the buyer now reaches the product in the first screen instead
of scrolling past 23 gate closeouts, and the depth below reads as an auditor's register
rather than as an undesigned dump.

## Contract verification

- `npm run typecheck` — clean
- `npm run test` — 39/39 passed
- `playwright e2e/sc_customer_demo.smoke.spec.ts` — passed (all ~90 sections and ~86 flag
  assertions)
- `playwright e2e/nm_wa_operator_demo.smoke.spec.ts` — passed
- `verify_nativeforge_demo_deployment.sh` — `RESULT=PASS`, `claim_boundary_preserved=PASS`

Proceed to UX-05 (`349_UX05_RESPONSIVE_VISUAL_QA.md`).
