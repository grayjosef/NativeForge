# Gate 36B — Dev Domain Deployment Machinery

**Status:** local loopback deployment machinery only. Public cutover is **not**
performed by this gate.

**Listener:** `127.0.0.1:5175`

**Recommended hostname (Mayhem ops, later):** `nf-dev.mayhem-nc.dev`.

## What this gate is

NativeForge can now:

1. Build the frontend **once** (`scripts/build_frontend_stamped.sh`).
2. Stamp build identity into served HTML.
3. Fail closed if `frontend/dist` is missing or unstamped
   (`scripts/serve_frontend_preview_5175.sh`).
4. Preview with Vite **preview** (not `npm run dev` / HMR). Preview does
   not proxy `/health` to the API; `frontend/dist/health` is static.
5. Verify loopback with `RESULT=PASS` or `RESULT=FAIL`.

Runtime config (hostname, Access password, tunnel) stays **outside** the
bundle.

## What this gate is not

- Not a live public cutover.
- Not Cloudflare credential edits.
- Not starting `cloudflared`.
- Not binding `0.0.0.0`.
- Not exposing API, DB, object storage, or Redis.
- Not production auth, login live, production storage, or customer persistence.

Cloudflare ingress (later, Mayhem-only) should map
`nf-dev.mayhem-nc.dev` to `http://127.0.0.1:5175`.
Cloudflare Access / password gate is configured **outside** this repo.
Do not store Cloudflare secrets in the repo.
Do not expose port 5175 on the public internet.

## Scripts

| Script | Role |
| --- | --- |
| `scripts/build_frontend_stamped.sh` | One Vite build + stamp + `/health` + `/version` + manifest |
| `scripts/serve_frontend_preview_5175.sh` | Fail-closed preview on loopback 5175 |
| `scripts/verify_nativeforge_demo_deployment.sh` | Loopback (or `NF_VERIFY_BASE_URL`) verifier |
| `scripts/install_nativeforge_demo_user_unit.sh` | Copy/enable user unit; `--start` optional |

Tracked unit: `ops/systemd/nativeforge-demo-preview.service`.

Dirty tracked trees are refused unless `NF_ALLOW_DIRTY_BUILD=1`.

## Allowed claims

- Local loopback deployment machinery exists.
- Monday target remains a **limited external demo** after Mayhem enables
  DNS / tunnel / Access and the verifier PASSes on the public hostname.
- Demo route: `/?view=sc_customer_demo`.

## Forbidden claims

Do not claim controlled customer pilot GO.
Do not claim production rollout GO.
Do not claim production-ready.
Do not claim login live.
Do not claim production storage.
Do not claim customer persistence.
Do not claim pen-test passed.

## Rollback (local)

Stop the user unit (`systemctl --user stop nativeforge-demo-preview.service`).
Do not rebuild to roll back; keep the last known stamped `frontend/dist` if
needed.
