# NativeForge Active Source Local Migration Verification (`nf_active_source_local_migration_verification_v1`)

## Sprint 47 purpose

Sprint 47 adds a **deterministic verification gate** for the Sprint 46-authored Alembic revision that introduces the `nf_active_opportunity_sources` table (`revision 0019`, file `alembic/versions/0019_nf_active_opportunity_sources.py`).

The gate answers: “Is the migration file internally consistent, chained correctly, and safe to exercise in a **throwaway SQLite database** (upgrade to head, downgrade back to `0018`) without touching application/runtime databases?”

## Relationship to Sprint 46

- Sprint **46** authored the migration **file** (DDL only).
- Sprint **47** verifies that file and an isolated Alembic cycle; it does **not** constitute approval to apply the revision to shared development or production databases.

## Local / test context only

- **Does not** apply migrations to runtime, production, or shared developer application databases used by the running product.
- **Does not** activate sources, create rows in product flows, seed data, scrape, ingest, call external APIs, call LLMs, or write operator ledger actions.
- Disposable SQLite verification temporarily sets `DATABASE_URL` only inside `run_sprint47_isolated_sqlite_verification()` and restores the previous environment variable afterward (for pytest and explicit local scripts).

## Embedding in discovery source quality

`build_discovery_source_quality()` includes `active_source_local_migration_verification` as a **read-only governance signal**: static inspection of the migration file plus closed-boundary counters/flags. It **does not** run the disposable-database cycle on each request (that path is opt-in via tests or explicit local verification).

## Final gate before runtime migration application

A later **human-approved runtime migration application sprint** may apply `0019` to real infrastructure. Sprint 47 is the engineering verification immediately preceding that decision; human review remains required (`required_human_review: true` in the artifact until operators authorize the next phase).
