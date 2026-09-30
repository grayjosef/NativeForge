# First controlled customer onboarding — operator checklist

Architecture is **already deployed** (`6520d04c+`). This runbook rehearses the
human/operator path without fabricating payment, licence, authority, or affiliation.

## 1. Customer identity confirmed

- Customer completes Google (or configured IdP) sign-in.
- Session shows `workspace_lane=demo` when unaffiliated.
- **Software stops** if identity cannot be verified.

## 2. Commercial entitlement confirmed (HUMAN)

- Customer may submit `POST /api/commercial-provisioning/intent` (activation UI).
- **Software state:** `entitlement_pending` — not active entitlement.
- **Operator required:** legitimate Gate 178 licence recording via
  `POST /api/commercial-provisioning/operator/fulfill` with:
  - `X-NF-Commercial-Operator-Approval: MAYHEM_APPROVES_NATIVEFORGE_COMMERCIAL_PROVISIONING`
  - `NF_COMMERCIAL_OPERATOR_APPROVAL` set in environment
- **Software must NOT:** infer payment from the activation button.

## 3. Organization match / create (OPERATOR)

- New org: unique display name; provisioning creates `organizations` row.
- Existing org: pass `existing_organization_id` on fulfill (unambiguous claim).
- Ambiguous display-name match → `blocked_ambiguous_org` (fail closed).

## 4. Membership

- Created by operator fulfill path (`operator_approved` / `grant_lead`).
- Customer must **sign in again** (or refresh session) for `workspace_lane=organization`.

## 5. Profile setup (CUSTOMER + Gate 177)

- Routes: `/v1/nf/real/orgs/{org_id}/organization-profile` (or demo plane in rehearsal).
- Complete canonical profile fields for eligibility evaluation.

## 6. Affiliation review (HUMAN — UNKNOWN owner)

- Input: reviewer decision on pending affiliation evidence.
- Software does not set `affiliation_verified` without review.

## 7. Authority review (HUMAN — UNKNOWN owner)

- Input: controlling-company or delegated Tribal authority reviewer.
- **Entitlement ≠ authority.** Membership ≠ authority.

## 8. Workspace activation

- Verify session: `workspace_lane=organization`, correct `organization_id`.
- Demo workspace API must refuse org members (`403`).

## 9. Discovery / feed check

- `GET /v1/nf/real/orgs/{org_id}/discovery/customer-opportunity-feed` (or demo plane in rehearsal).
- Wrong-org session → denied.

## 10. First pursuit check

- Record `PURSUING` decision on canonical opportunity (Gate 179).
- Full spark/pursuit pipeline may require additional seeded NOFO/spark steps.

## 11. Support / rollback verification

- See failure matrix in rehearsal evidence JSON.
- No automatic destructive rollback; ledger corrections use Gate 178 tools.

## Rehearsal commands (non-production)

```bash
python scripts/run_controlled_customer_onboarding_rehearsal.py --dry-run

NF_REHEARSAL_APPLY=MAYHEM_APPROVES_CONTROLLED_CUSTOMER_ONBOARDING_REHEARSAL \
NF_COMMERCIAL_OPERATOR_APPROVAL=MAYHEM_APPROVES_NATIVEFORGE_COMMERCIAL_PROVISIONING \
  python scripts/run_controlled_customer_onboarding_rehearsal.py --hermetic --write-evidence

pytest tests/test_controlled_customer_onboarding_rehearsal.py -q
```

## Production-safe smoke (read-only)

```bash
curl -sS https://nativeforge.mayhem-nc.dev/backend/health
curl -sS https://nativeforge.mayhem-nc.dev/backend/readiness
curl -sS https://nativeforge.mayhem-nc.dev/api/commercial-provisioning/contract
curl -sS -o /dev/null -w '%{http_code}\n' https://nativeforge.mayhem-nc.dev/api/demo-workspace/summary
```

Do **not** run `--hermetic --apply` against production.
