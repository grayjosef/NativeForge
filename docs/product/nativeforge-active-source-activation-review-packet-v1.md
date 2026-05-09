# NativeForge active source activation review packet (v1)

## Sprint 65 purpose

Sprint 65 adds deterministic, side-effect-free Python services that **scaffold** an activation review packet for the governed runtime row in `nf_active_opportunity_sources`. The packet enumerates legal/TOS, public access, provenance, duplicates, rate limits, failure modes, rollback, and operator confirmation as **review artifacts**, not as completed approvals.

## What this sprint does

- Builds artifact types `nf_active_source_*_v1` including the umbrella `nf_active_source_activation_review_packet_v1`.
- Consumes Sprint 64 **post-runtime verification** and **activation readiness gate** artifacts as inputs when supplied.
- Produces a top-level readiness of `ready_for_future_activation_command_package_review` only when both inputs validate and all sub-artifacts are scaffolded internally.

## What this sprint does not do

- **Does not activate** the source or change `source_status`.
- **Does not scrape, ingest,** or call **external APIs** or **LLMs**.
- **Does not create operator ledger actions.**
- **Does not open its own database sessions**, write to the database, or mutate schema.
- **Does not create Alembic revisions** or run migrations.
- **Does not insert, update, or delete** rows in `nf_active_opportunity_sources`.

## Relationship to Sprint 64

Sprint 64’s activation readiness gate required future activation review artifacts (legal/TOS, public access, provenance, duplicate, rate limit/cadence, failure/backoff, rollback, operator confirmation). Sprint 65’s `active_source_activation_review_packet_service` materializes those concerns as structured, JSON-serializable dicts with explicit “scaffolded, not approved” posture.

Optionally, the Sprint 64 gate accepts a valid Sprint 65 activation review packet and moves to `ready_for_future_activation_review_packet`—still **not** activation-ready and **not** permission to run live commands.

## Next sprint

The intended follow-on is an **activation command package preview** sprint, not live activation execution.
