# Monday Buyer Demo — Claim Matrix

| Capability | Status |
|------------|--------|
| SC customer demo route | IMPLEMENTED / DEMO-READY |
| SC + federal combined workflow | IMPLEMENTED / LOCALLY VALIDATED / DEMO-READY |
| NOFO/synopsis intelligence (selected) | IMPLEMENTED / LOCALLY VALIDATED / DEMO-READY |
| Application-plan skeleton | IMPLEMENTED / LOCALLY VALIDATED / DEMO-READY |
| Buyer story polish / trust strip | IMPLEMENTED / LOCALLY VALIDATED / DEMO-READY |
| Opening + closing lines | IMPLEMENTED / DEMO-READY |
| Allowed/forbidden claim lists | IMPLEMENTED / DEMO-READY |
| Live ingest | BLOCKED / NOT_CLAIMED |
| Full NOFO PDF extraction | BLOCKED / NOT_SUPPORTED |
| Proposal drafting | BLOCKED / NOT_SUPPORTED |
| Final eligibility without human review | BLOCKED |
| Live production validation | UNKNOWN |
| Independent penetration test | NOT_CLAIMED |
| Production-ready auth | NOT_CLAIMED |
| Auth0/OIDC validation run support | IMPLEMENTED / login_live=false until configured+validated |
| Login claim resolver | IMPLEMENTED / dry-run cannot unlock login_live |
| Storage feature-flag scaffolding | IMPLEMENTED / production_storage_enabled=false |
| Production storage readiness validator | IMPLEMENTED / claims remain false |
| Auth0 live validation execution support | IMPLEMENTED / Mode A dry-run; login_live=false |
| Storage approval / provisioning execution path | IMPLEMENTED / dry-run only; real provisioning blocked |
| Controlled customer pilot gate resolver | IMPLEMENTED / NO_GO or CONDITIONAL_INTERNAL_ONLY |
| Auth0 Mode A/B detector + Mode B path | IMPLEMENTED / Mode A this run; login_live=false |
| Pen-test evidence capture | IMPLEMENTED / no report → pen_test_passed=false |
| 2000-sprint closeout report | IMPLEMENTED / Gate 20 Mode A |
| Auth0 Mode B live unlock attempt | IMPLEMENTED / Mode A this run; login_live=false |
| Storage approval token ingest | IMPLEMENTED / prompt≠approval; absent this run |
| Production metadata adapter (flagged) | IMPLEMENTED / writes blocked without approval |
| Object storage + signed URL path (flagged) | IMPLEMENTED / production writes blocked |
| Customer data policy enforcement | IMPLEMENTED / persistence false; AI training default false |
| Retention/delete/export resolver | IMPLEMENTED / production delete/export blocked |
| Auth0 login/RBAC validation (Gate 24) | IMPLEMENTED / Mode A dry-run; login_live false |
| Session/tenant enforcement (Gate 24) | IMPLEMENTED / cross-org deny; external access false |
| Storage approval + metadata live path (Gate 25) | IMPLEMENTED / Mode A; production storage false |
| Object storage signed-URL unlock (Gate 25) | IMPLEMENTED / blocked without approval/SSE/malware |
| Security attestation / pen-test gate (Gate 26) | IMPLEMENTED / no report; pen_test_passed false |
| Controlled pilot master resolver (Gate 26) | IMPLEMENTED / CONDITIONAL_INTERNAL_ONLY; not GO |
| Full sovereignty deployment | NOT_CLAIMED |
| Automated submission | NOT_CLAIMED |
