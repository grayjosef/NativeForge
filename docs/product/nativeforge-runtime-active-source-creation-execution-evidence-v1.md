# NativeForge runtime active source creation execution evidence (v1)

## Sprint 62 purpose

Sprint 62 runs the **already proven Sprint 61** controlled active source creation path against the **configured local or runtime development database**, using only a **caller-supplied SQLAlchemy session**. It produces artifact type **`nf_active_source_runtime_creation_execution_evidence_v1`** via `nativeforge.services.active_source_runtime_creation_execution_service.execute_runtime_active_source_creation_and_build_evidence`.

The sprint **creates exactly one** governed row in **`nf_active_opportunity_sources`** when runtime preflight passes, then **commits** that insert on success so operators can capture durable runtime evidence.

## What the service does

- Proves **runtime preflight**: database connectivity, **Alembic `alembic_version`** current revision normalized to **`0019`**, physical presence of **`nf_active_opportunity_sources`**, active-source **count before**, **duplicate** probe on the stable Sprint 61 identity tuple, strict **Sprint 62 operator confirmation** (including **`runtime_organization_id`** for the governed payload org scope), and explicit **no activation / no scrape-ingest-API-LLM-ledger** authorization flags set to **false**.
- Builds the deterministic **Sprint 55→60** artifact chain (request, human approval intake, execution dry-run, execution readiness gate, command package, execution plan) aligned with Sprint 61 tests.
- Calls **`execute_single_active_source_creation_and_build_evidence_packet`** (Sprint 61) with the same session and a Sprint-61-compatible **`operator_confirmation`** slice derived from the Sprint 62 confirmation object.
- On Sprint 61 success, **commits** the transaction once, then reloads counts for **post-execution** runtime evidence.
- Embeds the full **Sprint 61 evidence packet** under **`sprint_61_execution_evidence_packet`**, plus **`runtime_post_execution_evidence`**, **`runtime_rollback_contract_evidence`**, **`runtime_no_activation_evidence`**, and **`runtime_no_scrape_ingest_api_llm_ledger_evidence`**.

## What the service does not do

- It does **not** activate the source, scrape, ingest, call external HTTP APIs, call LLMs, or create operator ledger actions.
- It does **not** run Alembic CLI, create new revisions, upgrade/downgrade the database from this module, or change schema.
- It does **not** open **`SessionLocal`** or construct engines inside the runtime service module; the operator wrapper (if used) owns session lifecycle.

## Operator execution

Use **`scripts/nativeforge_execute_runtime_active_source_creation.py`** only after review. It requires **every** Sprint 62 confirmation flag and **`--runtime-organization-id`**, writes a timestamped JSON file under **`docs/product/runtime-evidence/`**, and prints a **COPY THIS SUMMARY** block. It performs **no** automatic execution unless the operator invokes the script with explicit flags.

Example (replace the organization UUID with a row that already exists in your runtime database):

```bash
uv run python scripts/nativeforge_execute_runtime_active_source_creation.py \
  --runtime-organization-id 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee' \
  --operator-confirmed-runtime-db-execution \
  --operator-confirmed-single-row-creation \
  --operator-confirmed-no-activation \
  --operator-confirmed-no-scrape-ingest-api-llm-ledger \
  --operator-confirmed-rollback-contract \
  --operator-confirmed-runtime-evidence-capture \
  --operator-confirmed-target-table nf_active_opportunity_sources \
  --operator-confirmed-target-revision-id 0019
```

## Next sprint

Sprint 62 sets up **post-runtime-creation verification** and an **activation readiness gate**: confirming the single runtime row, governance fields, and rollback contract metadata **without** activating, scraping, or opening ingestion or external intelligence paths.
