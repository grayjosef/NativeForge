# 346 — UX-02 Premium Design System Direction

Status: direction fixed
Input: `345_UX01_FULL_PRODUCT_UI_AUDIT.md`
Implementation target: `frontend/src/index.css` tokens + shared component classes

This is a component-mapped direction, not a brand board. Every rule below names the
selector it lands on.

---

## 1. Target visual language

**Institutional, not startup.** The register is a sovereign wealth report, a federal
register notice, and an evidence console — printed on good paper, rendered as software.

Refined **light executive** surface is the default (warm ivory field, deep navy ink,
white cards, restrained copper accent), with a matching dark executive variant retained
under `prefers-color-scheme: dark`. Light-first is the deliberate choice: this product is
shown to boards and grant offices, screen-shared in bright rooms, and printed. A dark
console default would read as "security tool demo" rather than "institutional system of
record".

Three deliberate moves separate this from the current surface:

1. **A serif display face**, used only for the hero and ledger group titles. This is the
   fastest, cheapest departure from "generic AI SaaS" and toward institutional gravity.
2. **A monospace evidence register**, used for every machine flag. Machine-verifiable
   evidence gets its own typographic voice so it reads as proof, not as leftover debug text.
3. **Real elevation and density.** Cards, a two-column console grid, and a proper spacing
   rhythm instead of a single flat column.

No external font/CDN requests. The demo advertises offline operation and sits behind
Cloudflare Access; adding a font CDN would add a network dependency and a failure mode to a
live buyer demo. All three faces are high-quality system stacks.

## 2. Color system

Semantic tokens on `:root`, redefined under `@media (prefers-color-scheme: dark)`.

| Token | Light | Role |
| --- | --- | --- |
| `--nf-page` | `#f1eee7` | warm ivory field |
| `--nf-page-accent` | `#e8e3d9` | field wash foot |
| `--nf-card` | `#ffffff` | card surface |
| `--nf-card-muted` | `#faf8f4` | inset / evidence surface |
| `--nf-navy` | `#12283c` | deep navy band, hero, ledger header |
| `--nf-navy-deep` | `#0d1e2d` | navy gradient foot |
| `--nf-text` | `#10202e` | primary ink |
| `--nf-muted` | `#4a5a68` | secondary ink |
| `--nf-muted2` | `#6e7d89` | tertiary ink / eyebrow |
| `--nf-border` | `#ded8cd` | hairline |
| `--nf-border-strong` | `#c4bcae` | emphasis hairline |
| `--nf-primary` | `#1c4a3e` | primary action (retained green) |
| `--nf-accent` | `#a8632b` | restrained copper — accent rules, eyebrows, focus |
| `--nf-accent-soft` | `rgba(168,99,43,.09)` | accent wash |
| `--nf-verified` | `#1f6b4f` | verified / allowed |
| `--nf-warn` | `#95590a` | pending / needs review |
| `--nf-blocked` | `#a32530` | blocked / forbidden |

Rules:

- Copper is an **accent**, never a fill. Rules, eyebrows, 2-3px left borders, focus rings.
- Green means **verified by evidence**, never "everything is fine". A blocked gate never
  renders green under any state.
- Blocked is a **maroon-red hairline + tinted wash**, never a loud alert bar. A blocked gate
  should read as "deliberately held", not "error".
- The existing `--nf-trust` copper tokens are retained as aliases so no existing selector breaks.

**Fixed defect:** `.nf-sc-demo-cockpit` currently references `var(--nf-bg, …)`, a token that
does not exist, silently falling back to near-black on a light page. Replaced with real tokens.

## 3. Typography scale

Three faces:

- `--nf-font-display`: `ui-serif, "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif`
- `--nf-font`: `system-ui, -apple-system, "Segoe UI Variable Text", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
- `--nf-font-mono`: `ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace`

Fluid scale (all `clamp()`, so the mobile hierarchy collapse in UX-01 §2 is fixed by
construction):

| Token | Value | Use |
| --- | --- | --- |
| `--nf-t-display` | `clamp(2rem, 1.35rem + 2.3vw, 3rem)` | hero H1 (serif) |
| `--nf-t-h1` | `clamp(1.45rem, 1.2rem + 1vw, 1.9rem)` | page/group titles |
| `--nf-t-h2` | `clamp(1.02rem, .96rem + .3vw, 1.2rem)` | section H2 |
| `--nf-t-h3` | `.95rem` | card sub-heads |
| `--nf-t-body` | `.95rem` | body |
| `--nf-t-sm` | `.86rem` | secondary |
| `--nf-t-xs` | `.78rem` | meta, chips |
| `--nf-t-micro` | `.7rem` | eyebrow, evidence label |

Eyebrows: `--nf-t-micro`, `text-transform: uppercase`, `letter-spacing: .14em`, `--nf-muted2`.
Hero display gets `letter-spacing: -.015em` and `line-height: 1.08`.

## 4. Spacing scale

`--nf-s1: 4px` · `--nf-s2: 8px` · `--nf-s3: 12px` · `--nf-s4: 16px` · `--nf-s5: 24px` ·
`--nf-s6: 32px` · `--nf-s7: 48px` · `--nf-s8: 64px`

Card padding `--nf-s5`; card gap `--nf-s4`; section band gap `--nf-s7`.

## 5. Elevation and radius

- `--nf-e1`: `0 1px 2px rgba(16,32,46,.05), 0 1px 1px rgba(16,32,46,.04)` — resting card
- `--nf-e2`: `0 2px 4px rgba(16,32,46,.06), 0 10px 28px -14px rgba(16,32,46,.20)` — raised
- `--nf-e3`: `0 16px 44px -18px rgba(16,32,46,.30)` — hero band
- `--nf-radius-sm: 6px` · `--nf-radius: 10px` · `--nf-radius-lg: 14px` · `--nf-radius-pill: 999px`

## 6. Card system

`.nf-sc-demo-section` becomes the primary executive card:

```
background: var(--nf-card);
border: 1px solid var(--nf-border);
border-radius: var(--nf-radius);
padding: var(--nf-s5);
box-shadow: var(--nf-e1);
```

with a 2px copper top-rule on buyer-critical cards (`.is-buyer`) and a maroon left rule on
blocked cards. Hover raises to `--nf-e2`. Cards must never invent a status colour they do
not have evidence for.

## 7. Badge / status system

One family, `.nf-claim-badge`, uppercase micro type, pill radius, hairline border, tinted wash:

| Variant | Meaning | Colour |
| --- | --- | --- |
| `--demo` | limited external demo | copper |
| `--verified` | evidence-backed / allowed | green |
| `--pending` | human review required | amber |
| `--blocked` | gate held, claim forbidden | maroon |
| `--neutral` | factual label | slate |

Hard rule: `--verified` is reachable only from real evidence in the payload. No badge
variant may render a blocked gate in green.

## 8. Button / action hierarchy

- Primary (`.nf-btn-primary`): navy fill, one per view, the single next action.
- Secondary (`.nf-btn-secondary`): white fill, strong hairline.
- Ghost/inline: text + copper underline for evidence links.
- Minimum target `--nf-touch: 44px` retained.

## 9. Evidence / provenance display pattern (the central new pattern)

Every `data-testid$="-flags"` element inside `.nf-sc-customer-demo` becomes an **evidence
register**, not body text:

```
font-family: var(--nf-font-mono);
font-size: var(--nf-t-xs);
color: var(--nf-muted);
background: var(--nf-card-muted);
border: 1px solid var(--nf-border);
border-left: 2px solid var(--nf-accent);
border-radius: var(--nf-radius-sm);
padding: var(--nf-s3) var(--nf-s4);
overflow-x: auto;
```

prefixed by a generated `MACHINE-VERIFIABLE` micro-label via `::before`.

This is the pattern that converts the audit's worst content problem into an asset: the flags
stay **fully visible and unedited** (the Playwright contract requires it), but they now read
as cryptographic-style proof rather than leftover debug output. Provenance fields
(`capture_date`, `pack_id`, source labels) use the same register.

## 10. Blocked-gate display pattern

`.nf-sc-demo-section.is-blocked`: maroon 3px left rule, faint maroon wash, `--blocked` badge
in the head row, and the reason stated in plain language above the machine flags. Blocked
gates are never hidden, never collapsed, never greened, and never softened into "coming soon".

## 11. Layout / density rules

`.nf-sc-customer-demo` becomes a CSS grid:

- `<header>` spans all columns.
- Seven buyer-critical sections are hoisted with CSS `order` and span all columns.
- The remaining ~85 engineering closeout sections flow into a **2-column dense console grid**
  at ≥1120px, 1 column below.

This is the fix for the 78,256px page. It is delivered through `order` and `grid-column` on
existing `data-testid` selectors, so it needs **no reordering of the 3780-line JSX** and
cannot break the pinned test contract. Playwright `toBeVisible()` does not require
in-viewport, so relocation below the buyer surface is safe.

## 12. Mobile rules

- Every scale token is `clamp()`-based, so hierarchy survives to 390px by construction.
- `.nf-segment` gets `overflow-x: auto`, momentum scrolling, and an edge fade — fixing the
  clipped-nav defect in UX-01 §9.
- Grid collapses to one column below 1120px; card padding steps down to `--nf-s4`.
- Evidence registers scroll horizontally inside themselves rather than pushing the page.
- Tables become their own horizontal scrollers — fixing the 711px clipped-table defect
  (UX-01 §10).

## 13. No-go design list

- No gradients as decoration (one restrained navy band in the hero is the only gradient).
- No cartoon icons, no emoji as UI, no AI sparkles.
- No tribal clip art, no decorative "Native-themed" ornament, no borrowed motifs. Native
  relevance is expressed through **what the product does** — recognition-tier handling, data
  sovereignty, authority-to-apply, human approval — never through decoration.
- No fake green production badges, no "Secure" shield without a pen-test report.
- No fabricated counts, orgs, awards, or sources.
- No collapsing/hiding of machine flags or blocked gates.
- No external font or asset CDN.
- No ContractForge branding, no Spark language.

## 14. Component implementation map

| Component / selector | Change |
| --- | --- |
| `:root` tokens | full replacement: colour, 3 font stacks, type scale, spacing, elevation, radius |
| `@media (prefers-color-scheme: dark)` | matched dark executive variant |
| `html`, `body` | ivory field + wash, display/UI font split |
| `frontend/index.html` `<title>` | "NativeForge — Native Grant Intelligence & Pursuit" |
| `.nf-app` | container rhythm, overflow discipline |
| `WorkspaceHeader.tsx` + `.nf-header-*` | executive brand lockup, operator chrome de-emphasised on demo routes |
| `.nf-segment` | horizontal scroll + edge fade (mobile clip fix) |
| `App.tsx` connectivity banner | suppressed on offline demo surfaces (error-banner fix) |
| `.nf-sc-customer-demo` | grid console layout + `order` hoisting |
| `.nf-sc-customer-demo-header` | executive hero band (navy, serif display, badge, claim boundary panel) |
| `.nf-sc-demo-section` | executive card + `.is-buyer` / `.is-blocked` variants |
| `.nf-sc-customer-demo [data-testid$="-flags"]` | evidence register pattern |
| `.nf-sc-demo-trust-strip` | claim-boundary chip row (promoted, not muted) |
| `.nf-sc-demo-verbs`, `.nf-sc-demo-trust-card` | chip + tile system |
| `.nf-sc-demo-section table` | self-scrolling table (clipped-data fix) |
| `.nf-claim-badge` | new status badge family |
| `.nf-ledger-divider` | new: ledger band label between buyer surface and gate register |
| `.nf-card`, `.nf-btn-*`, `.nf-chip`, `.nf-pill` | re-tokenised against new scales |

Proceed to UX-03 (`347_UX03_PREMIUM_SHELL_IMPLEMENTATION.md`).
