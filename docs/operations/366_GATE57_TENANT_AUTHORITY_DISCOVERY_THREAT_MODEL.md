# 366 — Gate 57: Tenant / authority / discovery threat model

Status: threat model recorded. Mitigations are **contract-level**; none of them
are enforced at an API or storage boundary yet, because those remain NO_GO.

Read that limitation first: a contract that denies an action is only as good as
the caller that consults it. Until the API layer enforces these, they are
design guarantees, not runtime guarantees.

| # | Threat | Mitigation now | Residual risk |
| --- | --- | --- | --- |
| 1 | **Cross-tenant access** — org A reads org B | Deny-by-default `evaluate_tenant_scoped_access`, delegating to the Block 31 primitive; two audit events on denial | Not enforced at API/DB. No row-level security in the live path. |
| 2 | **Malicious invite** — attacker invites themselves in | Invite requires an actor; unknown role denied; every invite audited | No email verification, no identity proofing, no login |
| 3 | **Seat-cap abuse** — silently exceeding 5 | 6th seat blocked; override needs explicit approver; both audited | Override approver identity is not itself verified |
| 4 | **Unauthorized representative claim** — user asserts they can sign | Only `verified` unlocks; verifier required; expiry derived; capable roles restricted to owner/admin/representative | Verification is human review; no automated registry check |
| 5 | **Stale opportunity source** presented as current | Freshness from recorded timestamps only; `unknown` never fresh; `opportunity_source_stale` emitted | Depends on timestamps being recorded accurately upstream |
| 6 | **Scraped misinformation** treated as authoritative | `authoritative_without_metadata=false`; provenance required for promotion; extraction confidence recorded | Content accuracy itself is not validated |
| 7 | **Duplicate / phantom opportunities** inflating coverage | Fingerprint dedupe; duplicates flagged not dropped; duplicate share penalises the score | Fingerprint is title+url; a re-titled repost may evade it |
| 8 | **False eligibility** | Unknown eligibility never becomes eligible; eligibility evidence required for score credit; final eligibility never claimed | Human review still required for any real determination |
| 9 | **False authority** | Gate 52 two-gate check; no external status ever asserted | SAM/UEI/AOR not machine-verified |
| 10 | **Internal operator overreach** | `operator_internal` consumes no seat, holds no authority-gated capability, invariant-enforced; access audited | Support access is still broad read; no per-record consent |
| 11 | **Feedback alert leakage** — alert carries another org's data | Feedback is a tenant-scoped object; `feedback_alert_attempted` / `feedback_alert_failed` in the vocabulary | Slack live alert NOT PROVEN; payload redaction not implemented |
| 12 | **Source promotion without review** | `approver_id` mandatory; no automatic promotion path | Approver is trusted, not authenticated |
| 13 | **Customer correction leakage** across orgs | Correction paths are tenant-scoped objects | Not enforced at API |

## Highest-residual items

Ranked by what would actually hurt a tribal customer:

1. **No API/DB enforcement (threats 1, 13).** Every isolation guarantee here is
   a function call away from being bypassed by a caller that forgets to make
   it. This is the single most important thing to close, and it needs the
   storage gate.
2. **No identity (threats 2, 3, 4, 12).** Without login, "who approved this" is
   an unverified string. Authority proof is meaningful only once the person
   asserting it is authenticated.
3. **Feedback alert payloads (threat 11).** Slack live alert is not proven; if
   it is turned on before redaction exists, a cross-org leak becomes possible
   in a channel outside the product.

## What this model deliberately does not claim

- It does not claim pen-test coverage. `pen_test_passed` remains false.
- It does not claim these mitigations are runtime-enforced.
- It does not claim the threat list is exhaustive; it covers the thirteen
  threats in the Gate 57 scope.
