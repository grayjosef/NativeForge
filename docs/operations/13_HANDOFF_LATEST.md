# NativeForge Handoff — hostname mayhem-nc.dev + feedback alert modes

**Date:** 2026-08-22
**Path:** `/home/josefgray/projects/nativeforge`
**Public hostname:** `nf-dev.mayhem-nc.dev` via Cloudflare Tunnel → `127.0.0.1:5175`
**Not claimed:** public cutover, live Slack proven, customer pilot GO

## Next Mayhem ops

1. Cloudflare Tunnel + Access for `nf-dev.mayhem-nc.dev`
2. Set `NATIVEFORGE_FEEDBACK_SLACK_WEBHOOK_URL` out of repo
3. Dry-run script, then optional live test
4. Do not push until asked
