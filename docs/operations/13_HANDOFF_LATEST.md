# NativeForge Handoff — emergency visual correction

**Date:** 2026-09-28
**Protected stash:** `stash@{0}: wip-sprint8-ui-redesign-do-not-commit` — never drop

The sign-in page was an ivory field with a diagonal wallpaper and a small card on the right. That composition is replaced.

- Shared tokens `--nf-bg-primary` through `--nf-success` now drive the existing surface names. The application background is midnight navy. Ivory is ink, not the field.
- Sign-in is a two-zone frame: canonical lockup `/brand/nf-lockup.png`, headline, Find / Pursue / Govern, then a dark auth panel with a copper edge and no drop shadow.
- The rail and page use the same dark surfaces, so a signed-in session does not return to the ivory prototype.
- OAuth paths, session behavior, and the stash were not changed.

Local checks: vitest App, SignInPage, BrandLockup — 22 passed. Layout measured at 1920, 1440, 1024, and 390 with no horizontal overflow.
