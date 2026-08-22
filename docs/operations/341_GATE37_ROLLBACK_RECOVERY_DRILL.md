# Gate 37 — Rollback / recovery drill

Do **not** touch live Cloudflare from this repo.

## Rollback drill

1. Stop user unit:
   `systemctl --user stop nativeforge-demo-preview.service`
2. Verify loopback down:
   `./scripts/verify_nativeforge_demo_deployment.sh` must print `RESULT=FAIL`
3. Restore prior stamped dist if present (copy aside `frontend/dist` before
   rebuild; dist is gitignored).
4. Rerun build: `./scripts/build_frontend_stamped.sh`
5. Rerun serve + verifier on `127.0.0.1:5175`
6. Disable/remove Cloudflare ingress **outside** this repo if public hostname
   was enabled.

Do not rebuild merely to “undo” public DNS; stop the unit and disable ingress.

## Recovery

- Port collision: free 5175, then serve again.
- Unstamped dist: refuse serve; stamp again.
- Missing manifest: refuse serve; stamp again.
- WSL session drop: re-login, `systemctl --user start …`, consider linger.

## Allowed claims

- Limited external demo / loopback recovery of the same stamped bytes.

## Forbidden claims

Do not claim controlled customer pilot GO.
Do not claim production rollout GO.
Do not claim production-ready.
Do not claim login live.
Do not claim production storage.
Do not claim customer persistence.
Do not claim pen-test passed.
