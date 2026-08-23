# 350 — UX-06 Claude Design Direction, Implemented

Status: implemented
Source of truth: Claude Design project `6119b075-37f2-4ce2-9cc9-eea704ce43c3`
("NativeForge customer demo"), imported via the DesignSync MCP.
Files read: `CLAUDE.md`, `SC Customer Demo - Direction.dc.html`, `github.md`.

This gate **supersedes the visual language in `346`–`349`**. Those documents
describe a navy/ivory/copper *dashboard* with bordered cards. Design reviewed the
committed `main` branch and returned a different direction, which is now the one in code.

## What design actually called for

> Register: editorial/prospectus, not dashboard. Ivory field, hairline rules, no
> bordered card boxes for most content.

That is a direct reversal of the card-and-elevation system in `347`/`348`. Design also
noted that the ivory/navy/copper/serif description it was given did not match `main` —
correct, because that work was uncommitted at the time. Design audited the committed
baseline, which is the right thing to have done.

## Implemented

**Palette** — replaced navy/copper with the mockup's editorial values:

| Token | Value | Role |
| --- | --- | --- |
| `--nf-page` | `#faf7f0` | ivory field |
| `--nf-text` / `--nf-muted` / `--nf-muted2` / `--nf-faint` | `#1c1a15` / `#4a4538` / `#6b6558` / `#8a8477` | ink ramp |
| `--nf-rule` / `--nf-rule-fine` | `#e4ddd0` / `#ede7d9` | hairlines |
| `--nf-accent` / `--nf-accent-deep` | `#8a6a3c` / `#6b5230` | ochre — links, eyebrows, tier labels, **Held** |
| `--nf-sage` | `#4c7a63` | ready / allowed / link active |
| `--nf-dot-neutral` | `#c9bfa8` | factual, non-judging status dot |

`--nf-held`, `--nf-warn` and `--nf-blocked` all resolve to ochre: a held gate is a
deliberate decision at the same weight as a passing one, never red, never green.
`--nf-error` stays red for genuine failures on the operator surfaces.

**Type** — `"Iowan Old Style", Georgia, "Palatino Linotype", "Book Antiqua", serif` for
headlines, tier numerals and sub-heads, at **weight 400** (the previous system used bold);
`-apple-system, "Segoe UI", system-ui` for UI; mono strictly for machine flags. Hero
headline `clamp(34px, 5vw, 54px)`, 17ch measure, `line-height: 1.12`.

**Composition** — three tiers by decision weight, delivered with CSS `order` over the 95
pinned sections so no pinned JSX moves:

- **I. Decision** — command center, controlled pilot GO/NO-GO, claim guardrails
- **II. System state** — the gate ledger, condensed to one row per gate
- **III. Case work** — opportunities, eligibility, packages, given room

Each tier band uses the mockup's `220px + 48px + 1fr` editorial rail. Sections carry no
border, no radius, no shadow, no background — structure comes from hairlines and rhythm.

**Gate ledger** — the "NOT 15 duplicate cards" requirement. Every non-hoisted section is
now a `280px | 1fr` row: gate name, judgment, machine flags, hairline rule. Applied as
the *default* for `.nf-sc-customer-demo > section`, with a generated selector group
opting the 23 buyer sections back out. All ~70 gates stay fully visible.

**Hero** — rebuilt benefit-forward per the mockup: section nav (Decision / System state /
Case work), mono eyebrow, the outcome headline *"Find, qualify, and pursue the state and
federal grants your organization can actually win."*, the screening lede, a three-column
value strip (Qualify faster / See what's missing / Nothing goes out unreviewed), and the
credential row as plain text rather than pills.

**Copy generalized** off South Carolina in the sales-facing lines, per the design note that
the product is not SC-only. The payload's own environment label and advisory banner still
render verbatim — those describe the actual demo pack and stay accurate.

**Links** — ochre, underline on hover, `#6b5230` visited, sage active.

**Internal vocabulary removed from a buyer heading** — "Controlled pilot GO/NO-GO +
3000-sprint closeout" is now "Controlled pilot GO / NO-GO".

## Deliberately not implemented

**Per-gate "Held" / "Ready" labels.** The mockup shows an explicit status column. Deriving
it would mean heuristically parsing arbitrary `key=value` flag strings per gate. On a
surface whose entire value is claim honesty, a mis-derived "Ready" on a held gate is the
worst possible defect. The dot is therefore neutral and the judgment stays in the gate's
own words. Doing this properly needs a status field in the payload — assembler work, not
frontend work.

For the same reason the safe-verb dots were changed from sage to neutral: that row mixes
allowed actions with held states ("Owner Action Required", "Production Claim Blocked"), and
a green dot would have read those as passing.

**Teaming / pass-through match concept (`sc-demo-teaming-example`).** Present in the mockup,
but design's own next-steps say to revisit it as a real feature spec "before deciding what
(if anything) ships in the demo", and "do not fabricate matching results". Adding a concept
block to a live buyer surface is a product decision, not a styling one. Not added — flagged
for the owner.

## Measured

| | doc 348 (cards) | now (editorial) |
| --- | --- | --- |
| Page height @1440 | 51,253px | 68,934px |
| Page height @390 | 117,799px | 101,779px |
| Hero @1440 | 991px | 1,541px |
| Doc h-overflow | none | none |
| Sections rendered | 95 | 95 |

Desktop is taller because the editorial register is a single measured column rather than a
two-column card grid — that is the direction, not a regression. Mobile improved 14%. The
length lever design chose was ledger condensation and tiering, both of which are in.

## Validation

- `npm run typecheck` — clean
- `npm run test` — 39/39
- `playwright e2e/` — 2/2 (SC + NM/WA)
- `verify_nativeforge_demo_deployment.sh` — `RESULT=PASS`, `claim_boundary_preserved=PASS`
- Workspace / Workbench / Activation / NM-WA re-rendered, no overflow, no regression

## Still open

- Page length at desktop (68,934px). Further reduction needs either payload-level
  condensation or collapsing, and collapsing is blocked by the Playwright visibility contract.
- Dark mode retuned to the ochre/ink palette but not visually reviewed.
- Docs `346`–`349` describe the superseded card system; they are kept as the audit and
  measurement record, not as current visual direction.

## Artifact ordering doctrine — stamped build LAST

Recorded here because this trap was hit twice during this UX work.

`frontend/playwright.config.ts` declares
`webServer.command = "npm run build && npm run preview ..."`, so running
`npx playwright test` **rebuilds `frontend/dist` as an UNSTAMPED artifact** —
removing the `nativeforge-build-sha` meta and deleting `build-manifest.json`.

Correct order, always:

```text
1. npm run typecheck / npm run build / vitest / Playwright   <- all tests FIRST
2. ./scripts/build_frontend_stamped.sh                       <- stamped build LAST
3. systemctl --user restart nativeforge-demo-preview.service
4. ./scripts/verify_nativeforge_demo_deployment.sh           <- verifier LAST
```

**Do not trust `frontend/dist` after Playwright unless the stamped build is rerun.**

A verifier `RESULT=PASS` recorded *before* a Playwright run does not describe the
artifact being served *after* it. Re-stamp, restart, then re-verify.

`build_frontend_stamped.sh` refuses a dirty tracked tree. `NF_ALLOW_DIRTY_BUILD=1`
is for iteration only; the final build must come from a clean tree so the manifest
records `source_dirty: false`.

See `359_GATE50_CLOUDFLARED_USER_UNIT.md` for the tunnel-durability and verifier
hardening that came out of the same incident.
