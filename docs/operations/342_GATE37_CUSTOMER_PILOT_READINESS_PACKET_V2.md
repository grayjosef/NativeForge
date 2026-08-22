# Gate 37 — Customer pilot readiness packet v2

Honest split. Production-grade engineering continues. Production **claims**
stay closed.

## Ready for Monday limited demo

- Stamped local deploy (`scripts/build_frontend_stamped.sh`)
- Route verified: `/?view=sc_customer_demo`
- Claim boundary verified (UI strip + docs + verifier)
- Runbook exists (`docs/operations/339_GATE36B_MONDAY_DEMO_RUNBOOK.md`)
- Loopback listener: `127.0.0.1:5175`

**Limited external demo:** GO **candidate** after local verifier PASS **and**
public Cloudflare verifier PASS
(`NF_VERIFY_BASE_URL=https://nf-dev.mayhem-nc.dev`).

## Still blocked for controlled customer pilot

- Real auth (Auth0/OIDC OOB) — not live
- Production storage — not live
- Customer persistence — not live
- Pen-test — not passed
- Support owner / escalation path — not staffed as a customer SLO
- Customer approval — not granted

**Controlled customer pilot:** NO_GO  
**Production rollout:** NO_GO

## Status board

| Claim | Status |
| --- | --- |
| Limited external demo | GO candidate after public verifier PASS |
| Controlled customer pilot | NO_GO |
| Production rollout | NO_GO |
| Login live | false |
| Production storage | false |
| Customer persistence | false |
| Pen-test passed | false |
| Production-ready | false |

## Allowed claims

- Limited external demo
- Dev-domain demo
- Evidence-backed Native-relevant opportunity workflow
- Customer pilot pending auth/storage/security gates
- Production rollout blocked until gates pass

## Forbidden claims

Do not claim controlled customer pilot GO.
Do not claim production rollout GO.
Do not claim production-ready.
Do not claim login live.
Do not claim production storage.
Do not claim customer persistence.
Do not claim pen-test passed.
Do not claim pilot-ready.
Do not claim customer access live.
