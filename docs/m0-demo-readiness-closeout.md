# NativeForge M0 — Demo Readiness Closeout

Short handoff for another operator, a buyer-demo prep chat, or a teammate: what is ready, what was proven, and how to run it safely.

## Current git head

`72f004f` — fix: accept NativeForge M0 fixture org IDs

## What M0 can do

M0 delivers an end-to-end **demo slice** of the tribal grant pursuit workflow: tribal profile context, grant spark, NOFO-related extraction **stub**, structured requirements, deterministic scoring, opening and viewing a pursuit, form package with **SF-424 preview**, trust manifest surface, audit events, review summary, and **tenant-owned org data export** — all runnable from the local stack and the browser “Run M0 sequence” flow.

## What was proven locally

The following were verified on this head:

| Area | Result |
|------|--------|
| **Stack** | `nf-up` works; `nf-status` works |
| **Backend** | Starts on `127.0.0.1:8000` |
| **Frontend** | Starts on `127.0.0.1:5173` |
| **Health** | `GET /health` returns **200** |
| **Trust** | Trust manifest returns **`m0_trust_v1`** |
| **Browser live runner** | All **12** M0 steps completed successfully (see sequence below) |

**Browser M0 sequence (12 steps):**

1. Tribal profile  
2. Grant Spark  
3. NOFO extract stub  
4. Structured requirements  
5. Deterministic score  
6. Open pursuit  
7. Pursuit detail  
8. Form package / SF-424 preview  
9. Trust manifest  
10. Audit events  
11. Review summary  
12. Org data export  

## How to run the demo

1. From the repo root, start the stack: **`nf-up`**
2. Open **`http://127.0.0.1:5173/`**
3. Use demo org ID: **`bbbbbbbb-cccc-dddd-eeee-ffffffffffff`**
4. Click **`Run M0 sequence`**
5. Check status: **`nf-status`**
6. When finished: **`nf-down`**

For deeper operator steps (env, DB, checklist), see [`m0-demo-operator-checklist.md`](m0-demo-operator-checklist.md).

## Buyer-safe framing

Use this language with prospects and auditors:

- **No auto-submit** — nothing is sent to Grants.gov or external submission endpoints automatically.
- **Deterministic NOFO stub** — extraction behavior is scoped for demo consistency, not live crawl fidelity.
- **Rule-based scoring** — scores follow explicit rules; not a black-box ML score in M0.
- **SF-424 preview only** — review packaged forms as preview; not a claim of agency-valid output.
- **Human review required** — downstream submission and compliance remain human-gated.
- **Tenant-owned export** — export is under the tenant/org context for their records, not a vendor data grab.

## Known M0 limits

Be explicit about what M0 is **not**:

- **No auth / RBAC** — do not present as multi-tenant production security.
- **No live Grants.gov ingestion** — no continuous or production-grade grant feed.
- **No live AI extraction** — no production LLM pipeline for NOFO parsing in this slice.
- **No actual SF-424 PDF generation or submission** — preview and packaging only as implemented.
- **No billing** — no commercial metering or plans.
- **No production deployment claims** — M0 is local/demo readiness, not a GA production assertion.

## Recommended next engineering options

Ordered for typical post-demo follow-through:

1. **Buyer-demo polish** — UX copy, empty states, and anything that makes the 12-step story crisp in a live screen share.
2. **Add screenshots / demo script** — one PDF or doc buyers can skim without running the stack.
3. **Add frontend reset-demo-data control** — optional convenience for repeat demos (design-only until implemented).
4. **Begin Sprint 8 planning only after demo polish** — keep scope sequencing honest: demo hardening before the next build phase.

---

*This document reflects demo readiness at the git head above; re-verify after major merges.*
