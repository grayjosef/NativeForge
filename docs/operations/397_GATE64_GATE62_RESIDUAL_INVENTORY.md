# 397 — Gate 64A: Gate 62 residual inventory

Gate 62 was interrupted partway through. It left behind a real proof and no
repeatable way to re-run it. This is the inventory of what survived, what did
not, and what Gate 64 closes.

## What Gate 62 actually achieved

All of this happened and is recorded in doc 389:

| Proof | Status |
| --- | --- |
| Rootless PostgreSQL 16.2 via `pgserver`, no sudo, no Docker | achieved |
| Migrations 0023–0027 applied against real Postgres | achieved |
| Migration 0002's RLS executed for the first time | achieved |
| Cross-org read returns zero rows under a non-owner, non-superuser role | achieved |
| Unscoped read (no GUC) fails closed | achieved |
| Membership cross-org read returns zero rows | achieved |
| Membership cross-org **write** refused by `WITH CHECK` | achieved |

The proof was genuine. Its weakness was that it lived in a terminal session:
`scripts/verify_nativeforge_rls_isolation.sh` targets an admin URL supplied by
hand, and nothing in the repo could re-run the proof against a *managed*
instance later. A proof you cannot repeat is a memory, not a control.

## What was missing

| Artifact | Status before Gate 64 |
| --- | --- |
| `scripts/verify_nativeforge_postgres_rls.sh` | absent |
| `src/nativeforge/services/postgres_membership_directory_service.py` | absent |
| `docs/operations/391_GATE62_AUDIT_PERSISTENCE_WIRING_PLAN.md` | absent |
| `docs/operations/392_GATE62_PRODUCTION_READINESS_DELTA.md` | absent |
| `tests/test_gate62_storage_membership_rls_path.py` | absent |

The last one had a second cost: Gate 63's validation block referenced it, so
that gate could not fully satisfy its own instructions and had to report the
absence rather than a result.

## What Gate 64 completes

| Artifact | Status after Gate 64 |
| --- | --- |
| `scripts/verify_nativeforge_postgres_rls.sh` | created — `--dry-run` / `--check-config` / `--verify-rls` / `--strict` |
| `postgres_membership_directory_service.py` | created — production-path adapter, fails closed without a database |
| doc 391 | created — audit persistence wiring plan |
| doc 392 | created — Gate 62 readiness delta |
| doc 398 | created — Gate 64 readiness delta |
| `tests/test_gate62_storage_membership_rls_path.py` | created |

## Which proof still needs a live environment

The harness can be run today in `--dry-run`, and against the rootless pgserver
environment for `--verify-rls`. What it cannot do is prove anything about a
*managed* instance, because none is provisioned. Specifically still unproven:

- TLS enforcement on a real connection (`connection_ssl` needs a real server)
- an app role that is genuinely non-owner in a production schema
- backup / PITR configuration
- a restore drill with a recorded artifact

Those are owner-blocked on provisioning, not engineering-blocked.

## What must remain NO_GO

Nothing in this gate moves any of these:

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
Customer persistence:      NO
Pen-test passed:           NO
Slack live alert:          NOT PROVEN
```

The adapter created here is production-*path* code. It is real enough to be
wrong in a provisioned environment, which is the prerequisite for ever being
right in one — but in every environment that exists today it fails closed and
reports `production_storage_live=false`.
