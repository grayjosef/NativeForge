# Clear Briefing — sign-in finalization and source inventory

Date: 2026-09-28

## Shipped

- Sign-in lockup tagline is the same artwork with FIND. PURSUE. GOVERN. ink set to product teal `#3f9c8f`. Asset: `frontend/public/brand/nf-lockup-dark.png`. Anvil, wordmark, and spark are unchanged pixels. No shadow, glow, stroke, or gradient.
- Sign-in pillars:
  - Find — Discover and qualify the right opportunities.
  - Pursue — Move every opportunity from decision to submission.
  - Govern — Keep the work accountable, compliant, and under control.
- Approved dark shell stays the reference. No composition change.
- Authoritative ingestion inventory: `docs/operations/SOURCE_INGESTION_COVERAGE_INVENTORY.md`.

## Build / test

- Vitest: SignInPage, BrandLockup, App — 23 passed.
- Pytest: Grants.gov search adapter, eligibility discovery, eligibility completeness, Phase 1 collector readiness — 159 passed.
- No migrations.
- Collectors were not activated. `collectors_live` stays 0.

## Visual direction (locked)

Deep navy field, graphite surfaces, NativeForge green and teal, restrained copper, warm ivory text, cool slate secondary text. Richness from tone, border, type, and composition. Not from shadows. Ivory is not the application background.

## Do not touch

Stash `stash@{0}: On main: wip-sprint8-ui-redesign-do-not-commit`. OAuth, sessions, discovery architecture, pursuit lifecycle.

## Next safe action

Authorize one warranted Grants.gov search2 fetch. Do not flip `collectors_live` until the readiness invariant is deliberately changed.
