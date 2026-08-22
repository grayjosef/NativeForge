# 347 — UX-03 Premium Shell Implementation

Status: implemented
Input: `345_UX01_FULL_PRODUCT_UI_AUDIT.md`, `346_UX02_PREMIUM_DESIGN_SYSTEM_DIRECTION.md`

This gate covers the global shell — tokens, masthead, navigation, status, and the
cross-surface fixes. The SC demo route is documented separately in `348`.

## Files touched

| File | Change |
| --- | --- |
| `frontend/src/index.css` | full token replacement + shell restyle |
| `frontend/src/App.tsx` | offline-demo surface detection; `data-surface` on `.nf-app` |
| `frontend/src/components/WorkspaceHeader.tsx` | `offlineDemo` prop; surface-accurate status; conditional operator chrome |
| `frontend/index.html` | title + meta description |

## 1. Token system replaced

`:root` went from 27 ad-hoc variables to a structured system: surfaces, ink,
institutional navy, actions, copper accent, semantic status, three font stacks, an
8-step type scale, an 8-step spacing scale, a 3-step elevation scale, and a 4-step radius
scale. Legacy names (`--nf-trust*`, `--nf-success`, `--nf-error`, `--nf-shadow`,
`--nf-radius*`, `--nf-font`) are retained as aliases so no existing selector broke.

The `prefers-color-scheme: dark` block was rewritten to match (navy-black surfaces rather
than the previous green-grey).

**Defect fixed:** `.nf-sc-demo-cockpit` referenced `var(--nf-bg, #0b0f14)` — a token that
never existed — silently falling back to a near-black mix on a light page. Replaced with
real tokens.

## 2. Typography

- Display face (`--nf-font-display`, system serif stack) applied to the wordmark, the SC
  hero headline and the ledger band title. This is the single largest departure from the
  "generic internal tool" read, and it costs no network request.
- UI face upgraded from `"Segoe UI", system-ui` to a proper cross-platform stack.
- Monospace face introduced for the evidence register.
- Every size is a `clamp()` token, which structurally fixes the mobile hierarchy collapse
  found in UX-01 §2 (`h1` and `h2` were both 24px at 390px).

Measured hierarchy, SC route:

| | before | after |
| --- | --- | --- |
| Hero headline @1440 | 32px | **48px** |
| Section `h2` @1440 | 24px | 19.2px |
| Hero headline @390 | 24px | **32px** |
| Section `h2` @390 | 24px | 16.5px |
| Heading ratio @390 | **1.00** | **1.94** |

## 3. Masthead

- Wordmark set in the display serif, weight 600, tightened tracking.
- Eyebrow ("Grant pursuit workspace") re-tokenised to micro/uppercase/tracked.
- A single 96px copper rule sits under the masthead — the only brand ornament in the shell.
  No gradients, no icons, no motifs.
- Segment active state moved from green fill to institutional navy fill.

## 4. Status and claim-boundary placement

The header previously reported workspace API reachability on **every** surface, including
the two offline static demo bridges that never call that API. On the SC route this
produced a guaranteed error banner as the first thing a buyer saw (UX-01 §3.1).

`App.tsx` now computes:

```ts
const offlineDemoSurface =
  surface === "sc_customer_demo" || surface === "nm_wa_operator_demo";
```

and passes `backendHint={offlineDemoSurface ? "" : backendHint}` plus `offlineDemo`.

On those surfaces the header now shows a single accurate pill — **"Curated demo data ·
offline"** — instead of a red `Offline` verdict and a `Trust` error pill, and the
"Refresh workspace" action (which does nothing there) is not rendered.

This is scoping, not suppression. On Workspace / Workbench / Activation the banner, the
Offline pill, the Trust pill and the refresh action all still appear exactly as before —
verified by screenshot: the workspace surface still shows "We couldn't reach the workspace
service…" and per-card "Can't reach the workspace" errors, because there the message is true.

## 5. Mobile navigation defect fixed

`.nf-segment` was clipped at 390px (right edge 504px against a 390px viewport) with no way
to reach the last controls. It is now a horizontal scroller with
`overscroll-behavior-x: contain`, hidden scrollbar, `white-space: nowrap` children, and a
right-edge mask fade so a partially visible control reads as "scroll me". The fade is
removed at ≥900px where nothing overflows.

## 6. Cards, badges, buttons

- Cards moved onto the elevation scale (`--nf-e1` resting, `--nf-e2` raised) with the
  new radius scale.
- A new `.nf-claim-badge` family (`--demo`, `--verified`, `--pending`, `--blocked`,
  neutral) replaces ad-hoc pill styling. `--verified` is only ever applied to claims the
  payload actually supports; no blocked gate renders green anywhere.
- Cluster pills re-tokenised to the semantic status colours.
- Focus-visible rings added globally (2px copper, 2px offset) — there was no visible focus
  treatment before.

## 7. Cross-surface regression check

All four non-SC surfaces re-rendered at 1440x1000 after the token change:

| Surface | Height | Horizontal overflow | Result |
| --- | --- | --- | --- |
| `workspace` | 2003px | none | intact, errors still shown (correct) |
| `workbench` | 1837px | none | intact |
| `activation` | 1000px | none | intact |
| `nm_wa_operator_demo` | 2193px | none | intact |

`npm run test` — 39 tests / 14 files passed.
`playwright e2e/nm_wa_operator_demo.smoke.spec.ts` — passed.

## 8. Copy

`frontend/index.html` title changed from **"NativeForge — M0 demo shell"** to
**"NativeForge — Native Grant Intelligence & Pursuit"**, and a meta description added.
This is the browser tab and the screen-share title during the demo. Neither string
contains any phrase in `FORBIDDEN_HTML_CLAIMS`; `claim_boundary_preserved` still passes.

Proceed to UX-04 (`348_UX04_SC_DEMO_CORE_WORKFLOW_REDESIGN.md`).
