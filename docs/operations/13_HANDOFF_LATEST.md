# NativeForge Handoff — product completion (not demo freeze)

**Date:** 2026-09-28
**Path:** `/home/josefgray/projects/nativeforge`
**Live:** `https://nativeforge.mayhem-nc.dev`
**HEAD at write:** pending commit on session-bound org (follows `3edbea74`)
**Protected stash:** `stash@{0}: wip-sprint8-ui-redesign-do-not-commit` — never drop
**Push policy:** commits and pushes allowed after tests; never force-push; never prune

## Operating objective

Finish NativeForge as a product. Demo is a live checkpoint, not a freeze line.
Controlled-customer launch is the finish line. Collectors stay off unless Mayhem authorizes activation. Do not touch real tenants / Carolina Fire Protection Microsoft / Auth0.

## Repo / deploy state

| Item | Value |
|------|--------|
| Live `/health` (last verified) | `git_sha=82033c28` (logo commit), `source_dirty=false` |
| Logo on live sign-in | Compact kit artwork (desktop dark panel + mobile card). CSS fake wordmark removed from expanded rail in `82033c28`. |
| Auth path | Sentinel `after_begin`, returning-member lookup, unsigned onboarding bounce — shipped `56b470b3` / `a6e9c54d` / `df4bf3e5`. Live Workspace after Google not re-proven this run. |
| Collectors | `collector_activated: false` |

## Gates 173–180 (from repo + ops docs, not old pending assumptions)

| Gate | Classification | Evidence |
|------|----------------|----------|
| 173 Native relevance + coverage | **PARTIAL** | Tests complete. Ops: BUILT-UNPROVEN; keyword-built catalogue; real graph still thin. |
| 174 Eligibility intelligence | **COMPLETE** | PROVEN at verifier (deny-by-default, typed requirements). No real opportunity has fully normalized requirements in customer UX. |
| 175 Document / NOFO / attachment | **PARTIAL** | Tests complete. BUILT-UNPROVEN against a real NOFO corpus. Gate 182 OCR exists. Tranche 2 made this load-bearing for EPA, still not customer-fed. |
| 176 Early signals + award/recurrence/miss | **PARTIAL** | Tests complete. DEMO-ONLY: near-zero real input; award rows are fixtures; recurrence needs ≥3 real cycles. |
| 177 Tribal authority + onboarding + tenant admin | **PARTIAL** | Service layer PROVEN. Workspace identity tier was hardcoded unverified (`3edbea74`). Session org id is now read from `/api/auth/session` and Settings locks it. Invites not built (Organization page states that honestly). |
| 178 Commercial entitlements / licence | **COMPLETE** | PROVEN (consortium refuses an unjustified price). Not a live billing integration. |
| 179 Customer experience + customization + scale | **PARTIAL** | Isolation and customization PROVEN in tests. Customer workflow PROVEN on demo data. No Tranche 2 source feeds a customer. Operator tools still sit on Settings. |
| 180 World-class reassessment + controlled launch | **COMPLETE as reassessment; launch NOT STARTED** | Docs-only gate. Verdict: fabric built, not pointed at the world. Not `CUSTOMER_LAUNCH_READY`. |

## Post-180 boundary (actual)

Gates **181** (deployment identity, logical opportunity, Grants.gov eligibility discovery, publishers) and **182** (OCR bounds, regulatory classifier, programme roster, ALN, entity classes, funding channel, certification/zero) exist as **COMPLETE tests**. Tranche 2 measured five live publishers and added **zero** customer-visible opportunities because collectors are not activated.

**Current coding boundary:** customer-facing auth/session/tenant/UX + branding, with engines proven in tests and unactivated in production.

## This run

- Rail/sign-in draw compact kit artwork instead of CSS “NativeForge” (`82033c28`, live).
- Workspace reports signed-in identity as verified (`3edbea74`).
- Session client now reads `organization_id` from the `/api/auth/session` envelope (it was looking in a nested blob that does not exist). Settings locks the org identifier to that membership.

## Remaining launch-critical (do not treat as done)

- Live Google → Workspace re-verify after latest SHAs.
- Hide or gate operator surfaces for customer sessions.
- Real non-demo observations in customer UX (blocked on authorized collector activation).
- Discover remains empty by design until activation.
- Support runbook ABSENT. Adversarial tenant isolation campaign unrun. Privacy / Indigenous data governance framework incomplete.
- Remaining UNKNOWNs stay documented, not guessed.

## Proposed next

1. Re-verify live login → Workspace → compact rail lockup after this SHA deploys.
2. Gate operator surfaces so they are not in the customer Settings path.
3. Continue customer UX (pursuits, documents, intake) against the engines that already exist.
4. Do not activate collectors without explicit authorization.
