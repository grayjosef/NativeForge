# 754 — Gate 144: the frontend cockpit foundation

## A sixth surface, wired the existing way

```text
frontend/src/viewSurface.ts      "beta_onboarding_cockpit" added to the union
                                 and to readSurface()
frontend/src/App.tsx             a setSurface branch and a dispatch branch
frontend/src/pages/
  BetaOnboardingCockpitPage.tsx  the page
  BetaOnboardingCockpitPage.test.tsx  seven tests
```

Five surfaces already used exactly this pattern — `workspace`, `workbench`,
`activation`, `nm_wa_operator_demo`, `sc_customer_demo`. Nothing about it is
being invented for this gate, and a test asserts all five still dispatch.

Reachable at `?view=beta_onboarding_cockpit`.

## It requires a session

```text
fetch(..., { credentials: "include" })
```

against routes that require a demo org session. A signed-out visitor is told to
**sign in**, not shown a readiness summary — so no public bypass was added, and
`--strict-public` still passes.

A 401 is rendered as "Sign in to your demo organization to see readiness."
rather than as an error, because for a signed-out operator it is the correct
answer rather than a fault.

## What it renders

One card per lane, in the summary's own order:

```text
Login                          Customer Persistence
Awarded Grants                 Tenant Digest
Document Metadata              Document Storage
Email Readiness                Email Delivery
Source Monitoring Preflight    Source Monitoring
Object Storage                 Customer Auth
Verified Operational Binding   Controlled Customer Pilot
Production Readiness
```

Each carries a status caption, the lane's one-sentence summary, its blockers,
and its owner. Then one section for the next safe action and what is
deliberately not yet.

The status captions are plain English for the seven statuses:

```text
operational              Working
readiness_only           Proved, not activated
preview_only             Preview only
blocked                  Blocked
not_configured           Not configured
requires_human_approval  Needs a person
production_false         Not approved
```

## What the page must not do, asserted

```text
names a Tribe, an eligibility or a deadline   asserted absent in the rendered text
claims production ready                        asserted absent
claims live monitoring                         asserted absent
hides a false lane                             every lane given is rendered
hides a blocker                                every blocker is rendered
```

The last two matter most. A cockpit that filtered to the green lanes would be
worse than no cockpit, and the test that asserts the false lanes render is the
one to keep if any were ever dropped.

## A foundation, not finished UX

Status cards, blockers, one next action. No charts, no filtering, no history, no
drill-down. What it does have is the property the gate was for: an operator can
see the truth, including the parts that are false, without opening a shell.

## One thing found on the way

This repo's vitest setup registers no automatic testing-library cleanup —
`frontend/src/setupTests.ts` imports the jest-dom matchers and nothing else. A
file that renders more than once therefore leaves every previous tree in the
document, and three tests here failed with "Found multiple elements".

Fixed locally with `afterEach(cleanup)` in the new test file rather than by
adding cleanup to the shared setup: sixteen other test files pass today, and
changing what happens between every one of their tests to fix one new file would
be a much larger change than the problem.

## Build and tests

```text
npm run typecheck    clean
npm run build        clean
npm test             17 files, 61 tests, all passing
npm run test:e2e     4 passing — ?view=sc_customer_demo unaffected
```
