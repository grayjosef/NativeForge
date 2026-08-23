# 387 — Gate 61G: Storage decision checklist

**One decision, eight questions.** This unblocks membership, role mapping,
audit persistence, row-level security and the discovery baseline — everything
currently sitting behind storage.

Nothing is provisioned and no migration beyond `0022` is written until this is
answered. Full reasoning in `384`.

---

## 1. Storage provider

Recommended: **managed PostgreSQL 16+**, because `psycopg` is already a
dependency and the RLS machinery in migration `0002` is Postgres-specific.
Choosing otherwise abandons isolation code that is already written.

```text
[ ] Approved: managed PostgreSQL
[ ] Provider: ______________________  (e.g. Neon / Supabase / RDS / Cloud SQL)
[ ] Other backend instead: __________  (and accept that RLS work is discarded)
```

## 2. Environment

```text
[ ] One environment now (production only)
[ ] Two environments (staging + production)   <- recommended
[ ] Region / data residency requirement: ______________________
```

Data residency is worth a moment: this holds data about tribal organizations.
If any partner expects US-only or specific-region storage, decide now rather
than after migration.

## 3. Initial schema scope

```text
[ ] Approved as scoped in 384 §2:
      organizations (enriched), identities, org_memberships, roles,
      audit_events (extend), authority_proof_records
[ ] Approved with changes: ______________________
```

Explicitly **excluded** from the first migration (384 §3): customer documents,
proposal prose, tribal facts/resolutions/budgets, SAM/UEI/AOR status, anything
from the SC demo pack.

## 4. Migration permission

```text
[ ] Approved: write migrations 0023-0027 (384 §5)
[ ] Approved: run them against staging first
[ ] Not yet — design only
```

## 5. Backup / restore minimum

```text
[ ] Automated daily backup, >=7-day retention
[ ] Point-in-time recovery enabled
[ ] A restore actually performed and recorded as an artifact
[ ] RTO/RPO accepted: ______________________
```

An untested backup is not a backup. The repo already distinguishes "non-prod
proof is not production restore"; this is where that gets settled.

## 6. Tenant isolation posture

```text
[ ] Three layers required: app guard (live) + Postgres RLS (proven) + query scoping
[ ] App DB role must be non-owner, non-superuser   <- REQUIRED or RLS is bypassed
[ ] Cross-org read denial demonstrated before pilot
```

Note: RLS policies exist in migration `0002` but have **never executed** — no
Postgres has ever been connected. They must be proven, not assumed.

## 7. May the membership directory go live after migration?

```text
[ ] Yes — replace InMemoryMembershipDirectory with a Postgres-backed one and
    wire read routes first
[ ] Yes, but only after an invite/approval path exists, so memberships are
    created by a human decision rather than seeded   <- recommended
[ ] No — keep dry-run for now
```

The recommendation matters: without an invite/approval flow, the only way to
create a membership is an operator writing rows directly, which is the
internal-operator overreach threat in doc 366.

## 8. Production secrets out-of-band?

```text
[ ] Yes — DATABASE_URL and DB role credentials supplied out-of-band, never committed
[ ] Also supplying OIDC_* at the same time (unblocks Gate 60 live proof)
```

---

## Approval token

Paste this to approve, with any per-item changes noted above:

```text
MAYHEM_APPROVES_NATIVEFORGE_PROD_STORAGE_GATE61
```

**What that token authorises:** writing migrations `0023`–`0027`, provisioning
the approved backend, and implementing a Postgres-backed membership directory.

**What it does NOT authorise:** claiming `customer_login_live`, claiming
`controlled_customer_pilot GO`, claiming `pen_test_passed`, or storing any of
the excluded data in §3. Those remain separate gates with their own evidence
requirements.

## If the answer is "not yet"

That is a legitimate answer and does not block all work — it blocks *this*
chain. Alternatives not gated on storage: the stale active-source test cluster
(doc 371, 38 standing failures hiding real regressions), the discovery
scheduler design, or the Gate 60 live-token proof if `OIDC_*` credentials can be
supplied independently of storage.
