# NativeForge active source empty-state read model (v1)

## Sprint 54 purpose

Sprint 54 adds **application-side ORM and read-model alignment** for the runtime table **`nf_active_opportunity_sources`** introduced under Alembic revision **0019** (`alembic/versions/0019_nf_active_opportunity_sources.py`). The database table already exists after the Sprint **52** apply and Sprint **53** post-apply verification work; this sprint does **not** change schema or add another migration.

## What this sprint does

- Declares the SQLAlchemy model **`NfActiveOpportunitySource`** in `nativeforge.db.models`, matching the migration-authored column names and types.
- Provides **`nativeforge.services.active_source_empty_state_read_model_service`**, which builds deterministic artifact type **`nf_active_source_empty_state_read_model_v1`** describing empty-state readiness and governance boundaries.
- Optionally embeds a **read-only, non-persisting** slice into **`build_discovery_source_quality`** under **`active_source_empty_state_read_model`**, using a **`COUNT(*)`** query only (no writes, activation, scraping, ingestion, external calls, LLM calls, or operator ledger actions).

## What this sprint does not do

- It does **not** create rows in **`nf_active_opportunity_sources`**, seed data, or activate sources.
- It does **not** scrape, ingest, call external APIs, call LLMs, or create operator ledger actions.
- It does **not** run Alembic upgrades/downgrades or author a new revision from application code.
- It preserves the **active-source empty state** when the observed count is zero (the expected baseline after Sprint 52/53).

## Next sprint

The following work is explicitly **out of scope** for Sprint 54 and is the natural successor: an **active source creation request artifact** (human-governed request to insert the first controlled rows), still subject to existing activation, approval, and command-layer gates.
