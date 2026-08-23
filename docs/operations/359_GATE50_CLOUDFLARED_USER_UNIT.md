# 359 — Gate 50: cloudflared user unit + verifier tunnel hardening

Status: implemented
Scope: operational hardening only. No app code, no claim-boundary change.

## Why this exists

On 2026-08-22 the public demo returned **HTTP 404 to every authenticated request
for roughly 5.5 hours** while every automated check reported healthy.

Timeline:

| Time (EDT) | Event |
| --- | --- |
| 14:32:05 | `cloudflared` started as a bare foreground process |
| 14:55:01 | `~/.cloudflared/config.yml` edited — 23 minutes later |
| 14:55 → 20:24 | Running process kept the **pre-edit** ingress. `nf-dev.mayhem-nc.dev` matched no rule and fell through to `- service: http_status:404` |
| 20:24 | Tunnel restarted, ingress reloaded, demo restored |

Two failures made this expensive:

1. **cloudflared was a bare process.** It does not hot-reload config, nothing
   restarted it, and nothing would have restarted it after a crash or reboot.
2. **The verifier could not see it.** It checked loopback (healthy) and treated an
   unauthenticated Access `302` as success. But Access redirects at Cloudflare's
   **edge, before the tunnel** — so a completely dead origin path still produces a
   302. `RESULT=PASS` was reported throughout the outage. It took a screenshot of a
   browser console to find.

## Part A — the user unit

Tracked files:

```text
ops/systemd/nativeforge-cloudflared.service
scripts/install_nativeforge_cloudflared_user_unit.sh
```

No tunnel UUID, token, credential path beyond the config file, or credential JSON
appears in the repo. `~/.cloudflared/` is **not** copied into the repo.

Key unit properties:

- user service (`WantedBy=default.target`), never system-wide
- `ExecStart=/usr/local/bin/cloudflared --no-autoupdate --config /home/josefgray/.cloudflared/config.yml --metrics 127.0.0.1:20241 tunnel run`
- `Restart=on-failure`, `RestartSec=5`
- `WorkingDirectory=/home/josefgray`
- logs to the user journal

The metrics port is **pinned to 127.0.0.1:20241** deliberately: cloudflared
auto-increments to 20242 if 20241 is taken, which would silently move the health
endpoint the verifier depends on.

### Install

```bash
./scripts/install_nativeforge_cloudflared_user_unit.sh --start
```

Omit `--start` to enable without starting. The installer refuses to run if the
binary or the config is missing, and prints the sanitized ingress afterwards.

### Cutover from a bare process (zero downtime)

Cloudflare tunnels support multiple replicas, so never stop the old process first:

```bash
./scripts/install_nativeforge_cloudflared_user_unit.sh --start   # 2nd replica registers
systemctl --user is-active nativeforge-cloudflared.service        # confirm healthy
kill <bare-pid>                                                   # then retire the old one
```

This was used for the live cutover on 2026-08-22 with no interruption.

**Do not use `kill -HUP` to reload config.** cloudflared 2026.3.0 **exits** on
SIGHUP rather than reloading; that caused a ~90s outage across all three
hostnames on this tunnel during the incident. Use `systemctl --user restart`.

### Operate

```bash
systemctl --user status nativeforge-cloudflared.service --no-pager
systemctl --user restart nativeforge-cloudflared.service
journalctl --user -u nativeforge-cloudflared.service -n 80 --no-pager
curl -s http://127.0.0.1:20241/ready
```

`/ready` returns `{"status":200,"readyConnections":N,...}`. Expect `N >= 1`
(normally 4).

### Verify ingress without printing credentials

```bash
grep -nE 'hostname:|service:' ~/.cloudflared/config.yml
cloudflared tunnel --config ~/.cloudflared/config.yml ingress validate
cloudflared tunnel --config ~/.cloudflared/config.yml ingress rule https://nf-dev.mayhem-nc.dev/
```

Expected mapping:

```text
hostname: nf-dev.mayhem-nc.dev
service:  http://127.0.0.1:5175
```

Never `cat` the config in full, never read the credentials JSON, never print the
tunnel UUID or token.

### Linger

```text
To survive WSL/session boundaries, Mayhem may need:
loginctl enable-linger josefgray
```

The installer prints this note and **does not** run it — that is an explicit
owner decision. Without linger, the unit stops when the user session ends.

### Do not expose 5175

The origin stays bound to `127.0.0.1:5175`. It is reachable only through the
tunnel, behind Cloudflare Access. Never bind `0.0.0.0`, never publish the port.

## Part B — verifier hardening

`scripts/verify_nativeforge_demo_deployment.sh` gained modes and tunnel checks.

### Modes

| Mode | Behaviour |
| --- | --- |
| default | loopback + artifact checks enforced. Tunnel/ingress drift reported as `status=WARN`, does not change PASS/FAIL. Backwards compatible. |
| `--local-only` | skips every tunnel/public check. |
| `--public` | also probes the public edge; edge problems WARN. |
| `--strict-public` | **demo-readiness gate** — every tunnel, ingress and edge check is fail-affecting. |

`NF_VERIFY_STRICT_PUBLIC=1` is equivalent to `--strict-public`. A positional
argument is still accepted as the base URL, and `NF_VERIFY_BASE_URL` still works.

Env overrides: `NF_PUBLIC_URL`, `NF_EXPECT_HOSTNAME`, `NF_EXPECT_ORIGIN`,
`NF_CF_METRICS`.

### Checks added

| Check | Asserts |
| --- | --- |
| `listener_loopback_only` | the **running** socket is 127.0.0.1:5175, and 5175 is not bound to `0.0.0.0`/`[::]`. Hard FAIL if public — never advisory. |
| `cloudflared_process` | a cloudflared process exists |
| `cloudflared_unit_active` | the tracked user unit is active (SKIP if not installed) |
| `cloudflared_ready_connections` | `/ready` reports ≥1 edge connection |
| `cloudflared_config_present` | `~/.cloudflared/config.yml` exists |
| `ingress_hostname_present` | config contains `nf-dev.mayhem-nc.dev` |
| `ingress_origin_present` | config maps to `http://127.0.0.1:5175` |
| `ingress_config_not_stale` | **config mtime is not newer than the running process start** — the exact 2026-08-22 failure |
| `public_access_redirect` | unauthenticated public request is a 302 to `cloudflareaccess.com` |
| `public_edge_origin_error` | hard FAIL on 502/503/504/521/522/523/525/526/530 (error 1033) and on **404** (ingress not matching) |
| `public_cloudflare_header` | the `server: cloudflare` header is present |

The pre-existing `listener_loopback_documented` only greps the scripts; the new
`listener_loopback_only` asserts the live socket.

### Proof the drift check works

Negative-tested by touching `config.yml` so its mtime moved past the running
process start:

```text
--strict-public : check=ingress_config_not_stale status=FAIL
                  "config.yml modified 30s AFTER cloudflared started — restart the tunnel"
                  RESULT=FAIL, exit 1
default         : status=WARN, RESULT=PASS, exit 0
after restart   : status=PASS, RESULT=PASS, exit 0
```

This is the check that would have caught the outage in seconds.

### Honest limit

An unauthenticated 302 proves the edge and Access are up. **It does not prove the
post-Access origin path.** Only a human with a valid Access session can confirm
the demo actually renders. The verifier now prints this explicitly:

```text
note=post_access_render_requires_human_confirmation
```

Do not claim the public demo renders on the strength of a verifier PASS.

### Before a demo, run

```bash
./scripts/verify_nativeforge_demo_deployment.sh --strict-public
```

Then have a human load
`https://nf-dev.mayhem-nc.dev/?view=sc_customer_demo` through Access.

## Part C — stamped-build-last doctrine

Recorded in `339_GATE36B_MONDAY_DEMO_RUNBOOK.md` and
`350_UX06_CLAUDE_DESIGN_DIRECTION_IMPLEMENTATION.md`. See those documents.
