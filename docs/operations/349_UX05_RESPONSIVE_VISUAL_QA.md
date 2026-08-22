# 349 — UX-05 Responsive and Visual QA

Status: complete
Method: Playwright (chromium) against the running stamped preview at
`http://127.0.0.1:5175/?view=sc_customer_demo`, four breakpoints, screenshots plus
measured layout metrics. Screenshots are working artifacts under `/tmp/nfux/shots/`
(not committed).

## Breakpoint results

| Metric | 1440x1000 | 1280x900 | 834x1112 | 390x844 |
| --- | --- | --- | --- | --- |
| Grid columns | 2 | 2 | 1 | 1 |
| Page height (before) | 78,256px | 78,256px | 78,256px | 139,675px |
| Page height (after) | 51,253px | 51,253px | 73,527px | 117,799px |
| Hero height (after) | 991px | 991px | 1,482px | 2,208px |
| Document h-overflow | none | none | none | none |
| Hero headline | 48px | 48px | 40.8px | 32px |
| Section `h2` | 19.2px | 19.2px | 17.9px | 16.5px |
| Heading ratio | 2.50 | 2.50 | 2.28 | **1.94** |
| Table scroller | auto | auto | auto | auto |
| Nav scroller | auto | auto | auto | auto |

## Defects found and fixed

### 1. Header navigation clipped on mobile — FIXED
`.nf-segment` measured a right edge of 504px against a 390px viewport. "NM/WA Demo" was
cut mid-word and the last controls were unreachable. Now a horizontal scroller with
`overscroll-behavior-x: contain`, hidden scrollbar, nowrap children, and a right-edge mask
fade that signals more content. Confirmed by screenshot at 390px: the partially visible
control fades rather than hard-clipping. The fade is removed at ≥900px.

### 2. Review table clipped and unreachable — FIXED
1751px table in a 1040px card, `overflow-x: visible`, ancestor `overflow-x: clip` —
711px of columns lost at every breakpoint. Tables now scroll inside their own card. At all
four breakpoints the table reports `overflowX: auto` with `scrollWidth > clientWidth`,
i.e. the overflow is now *inside a scroller* and reachable rather than clipped away.

### 3. Zero heading hierarchy at mobile — FIXED
`h1` and `h2` were both 24px at 390px (ratio 1.00). Every size token is now `clamp()`-based;
the mobile ratio is 1.94.

### 4. Buyer-facing error banner — FIXED
See `347` §4. Removed from the two offline demo bridges, retained everywhere it is true.

### 5. Cramped hero — FIXED
Six undifferentiated grey paragraphs became a two-column navy band at ≥1024px: 2,600px →
991px at 1440. At 640px and below the hero tightens further (two-up command tiles, reduced
padding and gaps): 2,348px → 2,208px.

### 6. Excessive card density / vertical stacking — FIXED
Sections holding repeated per-opportunity `article` blocks span the full width and lay
those articles out as a nested grid. Tallest card 5,878px → 2,890px.

## Deliberate decisions

**Tablet portrait stays single-column.** Two ~390px columns at 834px were measured and
bought only ~5% total page height — narrow cards grow taller by roughly what the second
column saves — while clearly hurting line length and readability. The two-column
breakpoint is therefore 900px (tablet landscape and up), not 820px. This is recorded in a
comment in `index.css` so it is not "re-optimised" later without the measurement.

**Mobile is still a long page (117,799px).** 95 sections of genuine evidence in one column
is inherently long and none of it was cut. The mitigations are the command strip (five
anchored jumps from the hero) and the ledger divider, which together mean a buyer on a
phone reaches any of the five key surfaces in one tap rather than by scrolling.

## Remaining visual risks (not blocking)

- **Page length.** Even at 51,253px the desktop page is ~51 screens. The structural fix
  (buyer surface first, anchored command strip, framed ledger) is in; a further reduction
  would require either paginating the gate register or collapsing it, and collapsing is
  blocked by the Playwright visibility contract. Flagged for the next loop.
- **Duplicate boilerplate in the trust-view grid.** `Owner Action Required: …` and
  `freeze allowed=6 forbidden=12 fake_green=false` still repeat on each of the ten trust
  view cards. Content is generated from the payload, so de-duplicating means changing the
  assembler — out of scope for a frontend-only pass and deliberately not done.
- **Left column of the hero has unused vertical space at 1440** (story column ends ~760px
  against a 991px band). Cosmetic.
- **`:has()` dependency.** The nested article grid uses `:has()`. Chrome 105+/Safari
  15.4+/Firefox 121+. On an older engine it degrades to the previous stacked layout — no
  breakage, just less dense.
- **Dark mode** tokens were rewritten to match but the SC route has not been visually
  reviewed under `prefers-color-scheme: dark`. The demo machine renders light.

## Screenshot inventory (working artifacts, not committed)

```
/tmp/nfux/shots/before_sc_{d1440,d1280,t834,m390}_top.png
/tmp/nfux/shots/before_sc_d1440_mid.png
/tmp/nfux/shots/resp_{d1440,d1280,t834,m390}.png
/tmp/nfux/shots/hero_{1440,1280}.png
/tmp/nfux/shots/surface_{workspace,workbench,activation,nm_wa_operator_demo}.png
```

Proceed to UX-06 validation.
