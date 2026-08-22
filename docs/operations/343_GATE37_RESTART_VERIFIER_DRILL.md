# Gate 37 — Restart / verifier drill

## Purpose

Harden Gate 36B machinery without a public tunnel.

## Logs

```text
journalctl --user -u nativeforge-demo-preview.service -n 80 --no-pager
```

## Script

```bash
./scripts/drill_nativeforge_demo_restart.sh
./scripts/drill_nativeforge_demo_restart.sh --run
```

`--run` restarts the user unit only if it is already enabled. It does not
run `loginctl enable-linger`. It does not start cloudflared.

## Fail-closed expectations

- Unstamped dist blocks serve
- Missing manifest blocks serve
- Duplicate stamp blocks serve
- 5175 collision blocks serve
- Verifier FAIL when nothing listens on 5175
- Verifier PASS when stamped preview is up on 127.0.0.1:5175

## Allowed claims

- Limited external demo loopback drill

## Forbidden claims

Do not claim controlled customer pilot GO.
Do not claim production rollout GO.
Do not claim production-ready.
Do not claim login live.
Do not claim production storage.
Do not claim customer persistence.
Do not claim pen-test passed.
