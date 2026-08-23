# 367 — Gate 57: Production readiness delta

What this sprint moved, what it did not, and what still stands between here and
a controlled customer pilot.

## Status unchanged by this sprint

| Gate | Status |
| --- | --- |
| Controlled customer pilot | **NO_GO** |
| Production rollout | **NO_GO** |
| Customer login live | **NO** |
| Production storage | **NO** |
| Customer persistence | **NO** |
| Pen-test passed | **NO** |
| Slack live alert | **NOT PROVEN** |

None of these moved, and nothing in this sprint should be read as moving them.
The sprint added contracts; contracts are not infrastructure.

## What did move

| Area | Before | After |
| --- | --- | --- |
| Tenant model | cross-org denial primitive (Block 31) | organization tenant with seat ledger, membership states, invite decisions, extended scoped-object set |
| Seats | not modeled | 5-seat default cap, blocked 6th, audited override, internal role excluded from seats |
| Authority | per-opportunity record (Block 28) | org-level proof lifecycle with 9 states, 8 proof types, derived expiry, verifier requirement, two-gate action check |
| RBAC | 8 older roles, action list (Block 35) | 7-role Gate 51 vocabulary, 18 capabilities, authority-gated subset, permanently blocked production capabilities |
| Audit | scattered | 21-event vocabulary, every event `persisted: false` |
| Discovery quality | not measurable | 6-component weighted score, duplicate/stale/provenance penalties |
| Source discovery | freshness + probe services | candidate lifecycle, promotion gate requiring human review, terms/robots handling, dedupe with flagging |
| 65% target | aspiration | arithmetic contract with four anti-gaming constraints; currently `achieved=false, measured=false` |

## Demo integration — what was and was not done

The SC demo route already surfaces this posture through existing sections. All
were verified present in the rendered DOM after this sprint:

`sc-demo-rbac-enforcement`, `sc-demo-session-tenant`,
`sc-demo-applicant-authority`, `sc-demo-multi-org-pilot`,
`sc-demo-source-freshness`, `sc-demo-gate32-source-freshness`,
`sc-demo-customer-data-policy`, `sc-demo-evidence-lifecycle`,
`sc-demo-collaboration-dark-launch`, `sc-demo-live-authority-execution`.

Rendered claim boundary confirmed intact: `final_eligibility_claimed=false`,
`submission_ready_claimed=false`, `CONTROLLED_CUSTOMER_GO` (as a forbidden
claim), `PRODUCTION_ROLLOUT_NO_GO`, `login_live=false`, `rbac_enforced=true`,
`multi_tenant=false`, "human review required". 95 sections still render.

**No new demo UI was added, deliberately.** The demo carries a Playwright
contract pinning ~90 sections and ~86 exact flag strings, and the editorial
design pass landed two commits ago. Adding sections describing contracts that
are not runtime-enforced would put *more* claims on a buyer surface while the
underlying enforcement is still NO_GO — the opposite of what the claim boundary
is for. The posture is already represented; this sprint strengthened what sits
behind it.

## Remaining gates to controlled customer pilot

In dependency order:

1. **Storage approval + provisioning.** Everything else waits on this. Until
   there is a real store, tenant isolation cannot be enforced at the data
   layer and audit events cannot be persisted.
2. **Auth0 / OIDC live (Mode B).** Requires real OIDC_* inputs out-of-band.
   Without identity, authority proof and seat approval rest on unverified
   strings.
3. **API-layer enforcement.** Wire `evaluate_tenant_scoped_access` and
   `evaluate_capability` into request handling so isolation is enforced rather
   than merely available. This is the largest engineering item in this list.
4. **Row-level security** in the production store, so a bug in step 3 is not a
   cross-tenant breach.
5. **Independent pen test** against the above.
6. **Feedback alert redaction** before any live Slack path.
7. **Baseline measurement** for Gate 56, which needs steps 1–3 to produce real
   source and opportunity data.

Steps 1 and 2 are owner-blocked, not engineering-blocked: they need real
OIDC_* credentials out-of-band, a storage approval decision, and a pen-test
engagement.

## Honest summary

This sprint made the product architecturally serious about tenancy, authority
and discovery quality, and made several claims *structurally impossible to
fake* — improvement without measurement, authority without verification,
promotion without review, eligibility from unknown. It did not make the product
production-ready, and every artifact it emits says so in a machine-checkable
field.
