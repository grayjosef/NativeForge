#!/usr/bin/env bash
# Install tracked cloudflared user systemd unit. Does not enable linger.
# Pass --start to start the unit after enable.
#
# Never prints tunnel UUID, tunnel token, or credentials-file contents.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/ops/systemd/nativeforge-cloudflared.service"
DEST_DIR="${HOME}/.config/systemd/user"
DEST="$DEST_DIR/nativeforge-cloudflared.service"
CF_CONFIG="${HOME}/.cloudflared/config.yml"

if [[ ! -x /usr/local/bin/cloudflared ]]; then
  echo "cloudflared not found at /usr/local/bin/cloudflared" >&2
  echo "found instead: $(command -v cloudflared || echo none)" >&2
  echo "update ExecStart in ops/systemd/nativeforge-cloudflared.service" >&2
  exit 1
fi

if [[ ! -f "$CF_CONFIG" ]]; then
  echo "missing tunnel config: $CF_CONFIG" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"
cp "$SRC" "$DEST"
systemctl --user daemon-reload
systemctl --user enable nativeforge-cloudflared.service

START=0
if [[ "${1:-}" == "--start" ]]; then
  START=1
fi
if [[ "$START" -eq 1 ]]; then
  systemctl --user start nativeforge-cloudflared.service
  echo "unit started: nativeforge-cloudflared.service"
else
  echo "unit enabled, not started (pass --start to start)"
fi

echo
echo "ingress (sanitized — hostname/service lines only):"
grep -nE 'hostname:|service:' "$CF_CONFIG" || true

echo
echo "To survive WSL session boundaries, Mayhem may need:"
echo "loginctl enable-linger josefgray"
echo "(this installer does not run loginctl enable-linger)"
echo
echo "Cutover note: if a bare cloudflared process is already running, start this"
echo "unit FIRST (it registers as an additional replica), confirm it is healthy,"
echo "then stop the bare process. That avoids a tunnel outage."
