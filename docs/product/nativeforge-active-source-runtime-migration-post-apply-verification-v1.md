# NativeForge active source runtime migration — post-apply verification (v1)

## Sprint 53 purpose

Sprint 53 produces **`nf_active_source_runtime_migration_post_apply_verification_v1`**, a deterministic evidence artifact that describes **runtime database state after** migration **0019** has already been applied under operator control (Sprint 52). It answers: “Given read-only observations (revision, table presence, row count, columns, indexes, constraints, unrelated-table preservation, rollback readiness preview, and boundary flags), does the environment match the governed empty-table baseline?”

## Relationship to Sprint 52

- Sprint **52** executed `uv run alembic upgrade 0019` (or verified already-at-0019) and captured **`nf_active_source_runtime_migration_apply_execution_v1`**.
- Sprint **53** does **not** repeat apply. It **verifies** post-apply shape using observations collected elsewhere (CLI inspection, SQL metadata queries, etc.).

## Explicit non-actions (Sprint 53)

The verification service and Sprint 53 workflow:

- Do **not** apply Alembic migrations or re-run upgrades.
- Do **not** downgrade or rollback (rollback stays a **future explicit operator action** only; the artifact may record that a downgrade command exists as **readiness**, not as an executed step).
- Do **not** create rows in `nf_active_opportunity_sources` or seed sources.
- Do **not** activate sources or open activation paths.
- Do **not** scrape, ingest, call external HTTP APIs, call LLMs, or create operator ledger actions.

## Expected success baseline

After a correct Sprint 52 apply to **0019**:

- **Alembic current** normalizes to **`0019`**.
- **`nf_active_opportunity_sources`** exists.
- **Row count is 0** (empty governed table until later operator/product flows).
- **Columns, indexes, and constraints** match **`alembic/versions/0019_nf_active_opportunity_sources.py`** (names taken from that migration, not guessed).
- **Unrelated tables** such as **`organizations`** and **`nf_opportunity_sources`** remain present when your observation bundle expects them.
- **Rollback readiness** is recorded only as **preview** (`alembic downgrade 0018` is available in principle; execution is out of scope here).

## Next sprint alignment

Successful verification **sets up Sprint 54**: **ORM and read-model alignment** for **`nf_active_opportunity_sources`** in the **empty-table** state—mapping the physical schema to application models and read paths without introducing activation or ingestion side effects.
