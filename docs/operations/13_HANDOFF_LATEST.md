# NativeForge Handoff — Gate 36B (loopback deploy machinery)

**Date:** 2026-08-22
**Path:** `/home/josefgray/projects/nativeforge`
**Branch:** `main`
**Mode:** local loopback deployment machinery only — no public cutover

## What Gate 36B did

Added stamped Vite build, fail-closed preview on `127.0.0.1:5175`, user
systemd unit template, verifier (`RESULT=PASS|FAIL`), and operator docs.
Did **not** start cloudflared, edit tunnel credentials, or bind `0.0.0.0`.

## Claims

Monday limited external demo: **not GO** until Mayhem DNS/Access/tunnel
and public verifier PASS.
Controlled customer: NO_GO
Production rollout: NO_GO

## Next Mayhem ops

DNS for `nf-dev.josef-gray.dev`, Cloudflare ingress to `127.0.0.1:5175`,
Access password, start tunnel, then public verify.
