# Backend unit install plan

Template: `deploy/systemd/nativeforge-backend.service` — present, binding `127.0.0.1:8000` and nothing else.

## What this gate did

```text
operator_approval        install_and_start_without_enable
installed_by_this_gate   true
enabled_by_this_gate     false
```

The operator was asked before anything touched the host and chose **install and start, without enable**. `systemctl --user enable` was not run and does not appear in the commands below, so the service **will not come back after a reboot**. That is deliberate: it keeps a loopback development backend trivially reversible.

## Install

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/nativeforge-backend.service ~/.config/systemd/user/nativeforge-backend.service
systemctl --user daemon-reload
systemctl --user start nativeforge-backend.service
sleep 5
systemctl --user status nativeforge-backend.service --no-pager
curl -fsS http://127.0.0.1:8000/backend/health
curl -fsS http://127.0.0.1:8000/backend/readiness
```

## Remove

```bash
systemctl --user stop nativeforge-backend.service
rm ~/.config/systemd/user/nativeforge-backend.service
systemctl --user daemon-reload
```

## Why loopback

A Cloudflare tunnel is already running on this host. A backend bound to `0.0.0.0` would be published through it. Every `ExecStart` binds `127.0.0.1`, a test parses the unit to prove it, and the writer refuses to emit this plan for a template that does not.

No credential appears in the unit or in these commands.

