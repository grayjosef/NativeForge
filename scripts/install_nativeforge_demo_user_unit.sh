#!/usr/bin/env bash
# Install tracked user systemd unit. Does not enable linger.
# Pass --start to start the unit after enable.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/ops/systemd/nativeforge-demo-preview.service"
DEST_DIR="${HOME}/.config/systemd/user"
DEST="$DEST_DIR/nativeforge-demo-preview.service"

mkdir -p "$DEST_DIR"
cp "$SRC" "$DEST"
systemctl --user daemon-reload
systemctl --user enable nativeforge-demo-preview.service

START=0
if [[ "${1:-}" == "--start" ]]; then
  START=1
fi
if [[ "$START" -eq 1 ]]; then
  systemctl --user start nativeforge-demo-preview.service
  echo "unit started: nativeforge-demo-preview.service"
else
  echo "unit enabled, not started (pass --start to start)"
fi

echo
echo "To survive WSL session boundaries, Mayhem may need:"
echo "loginctl enable-linger josefgray"
echo "(this installer does not run loginctl enable-linger)"
