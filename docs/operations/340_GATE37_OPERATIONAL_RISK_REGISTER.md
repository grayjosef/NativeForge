# Gate 37 — Operational risk register

Local loopback demo machinery exists. Public cutover is **not** done by this
gate. Do not claim controlled customer pilot GO. Do not claim production-ready.

## Risks

| Risk | Effect | Mitigation |
| --- | --- | --- |
| WSL session ends | user systemd units may stop without linger | Mayhem may `loginctl enable-linger josefgray` (not auto) |
| systemd user/linger unset | preview dies when session closes | Installer prints linger note only |
| Cloudflare tunnel not running | public hostname unreachable | Keep loopback; start tunnel only with Mayhem approval |
| Access/password not configured | accidental public exposure if tunnel is up | Do not start tunnel until Access exists off-repo |
| Wrong URL missing query route | buyer sees workspace shell, not SC demo | Always use `/?view=sc_customer_demo` |
| Stale dist | old UI bytes served | Rebuild stamped artifact from current HEAD |
| Unstamped artifact | fail-closed serve refuses start | `scripts/build_frontend_stamped.sh` |
| Port collision on 5175 | `--strictPort` + pre-check refuse serve | Stop the other listener |
| Public bind accident | WSL port on all interfaces | Serve script binds `127.0.0.1` only |
| Lack of pen-test | not a production security claim | Keep pen-test passed = false |
| Slack feedback alert not proven | Mayhem may miss buyer reports | Default `dry_run`; live needs webhook out-of-repo + tests |

## Logs

```text
journalctl --user -u nativeforge-demo-preview.service -n 80 --no-pager
```

## Allowed claims

- Limited external demo (after public verifier PASS)
- Dev-domain demo
- Evidence-backed Native-relevant opportunity workflow

## Forbidden claims

Do not claim controlled customer pilot GO.
Do not claim production rollout GO.
Do not claim production-ready.
Do not claim login live.
Do not claim production storage.
Do not claim customer persistence.
Do not claim pen-test passed.
