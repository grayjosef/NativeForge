# Gate 36B — Monday demo runbook (loopback first)

This is **local loopback deployment machinery only**.
Public cutover is **not** performed by this gate.

**Listener:** `127.0.0.1:5175`
**Recommended hostname:** `nf-dev.mayhem-nc.dev`.
**Demo route:** `/?view=sc_customer_demo`

Cloudflare ingress should map `nf-dev.mayhem-nc.dev` to
`http://127.0.0.1:5175`.
Cloudflare Access / password is outside the repo.
Do not store Cloudflare secrets in the repo.
Do not expose 5175 publicly.

## Artifact ordering doctrine — stamped build LAST

> **Playwright overwrites `frontend/dist` with an UNSTAMPED artifact.**
> `frontend/playwright.config.ts` declares
> `webServer.command = "npm run build && npm run preview ..."`, so `npx playwright
> test` rebuilds `dist` — stripping the `nativeforge-build-sha` meta and deleting
> `build-manifest.json`.

Correct order, always:

```text
1. npm run typecheck / npm run build / vitest / Playwright   <- all tests FIRST
2. ./scripts/build_frontend_stamped.sh                       <- stamped build LAST
3. systemctl --user restart nativeforge-demo-preview.service
4. ./scripts/verify_nativeforge_demo_deployment.sh           <- verifier LAST
```

**Do not trust `frontend/dist` after Playwright unless the stamped build is rerun.**

This is not hypothetical: on 2026-08-22 a verifier `RESULT=PASS` was recorded, then
a Playwright run silently clobbered `dist`, leaving the service handing out an
unstamped artifact while the recorded PASS looked current. Caught only by comparing
the served HTML against the manifest.

`build_frontend_stamped.sh` refuses a dirty tracked tree. During iteration use
`NF_ALLOW_DIRTY_BUILD=1`; the final pre-demo build must be from a clean tree so
`build-manifest.json` records `source_dirty: false`.

## Sequence

1. Build stamped artifact: `./scripts/build_frontend_stamped.sh`
2. Verify artifact files exist: `frontend/dist/index.html`,
   `frontend/dist/health`, `frontend/dist/version`,
   `frontend/dist/build-manifest.json`
3. Install user unit: `./scripts/install_nativeforge_demo_user_unit.sh`
   (does not start unless `--start`; does not run `loginctl enable-linger`)
4. Start/restart local preview:
   `./scripts/serve_frontend_preview_5175.sh`
   or `./scripts/install_nativeforge_demo_user_unit.sh --start`
5. Verify loopback: `./scripts/verify_nativeforge_demo_deployment.sh`
6. Mayhem applies DNS / Cloudflare Access / tunnel **outside** this repo.
7. Verify public URL (after step 6):
   `NF_VERIFY_BASE_URL='https://nf-dev.mayhem-nc.dev' ./scripts/verify_nativeforge_demo_deployment.sh`
8. Use `/?view=sc_customer_demo` for the demo (not bare `/` as the buyer URL).
9. State claim boundary (below). Talk-track: limited external / dev-domain demo
   of an evidence-backed Native-relevant opportunity workflow; customer pilot
   pending auth/storage/security gates; production rollout blocked until gates
   pass.
10. Rollback: stop user unit and remove/disable Cloudflare ingress.
    Do not rebuild to roll back; keep the stamped bytes.

Vite **preview** only. Do not use `npm run dev` as deployment.

`frontend/vite.config.ts` keeps `/health` API proxy for **dev** only. Preview
does **not** proxy `/health`, so `frontend/dist/health` answers loopback
checks without the API.


## Allowed claims

- Limited external demo after Mayhem public cutover + verifier PASS.
- Loopback preview of stamped SPA for operator rehearsal.

## Forbidden claims

Do not claim controlled customer pilot GO.
Do not claim production rollout GO.
Do not claim production-ready.
Do not claim login live.
Do not claim production storage.
Do not claim customer persistence.
Do not claim pen-test passed.
