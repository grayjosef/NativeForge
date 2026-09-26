"""Alembic 0066: finish the tenant boundary the database was supposed to hold.

RLS stopped being applied after migration 0042. Everything built since -
source collection, documents, eligibility, tribal authority, commercial
entitlements, customer decisions - created tables with `organization_id NOT
NULL` and no row-level security at all. Measured on a real PostgreSQL 16.2
instance at head 0065:

```text
public tables          85
tenant-column tables   54
RLS enabled            31
FORCE RLS              26
```

Twenty-three tables own rows by organisation and let any role that can reach
the table read every organisation's rows. A tenant column is not a tenant
boundary.

## Two defects, not one

The second is quieter. Five tables that DO have RLS were written with the
0042-era pattern, which enables RLS and writes a policy with `USING` only:

```text
nf_digest_delivery_intents      USING, no WITH CHECK, no FORCE
nf_membership_invites           USING, no WITH CHECK, no FORCE
nf_source_watchlist_entries     USING, no WITH CHECK, no FORCE
nf_tenant_digest_records        USING, no WITH CHECK, no FORCE
nf_tenant_pursuit_suppressions  USING, no WITH CHECK, no FORCE
```

`USING` decides what a tenant can SEE. `WITH CHECK` decides what it can
WRITE. With `USING` alone a tenant can INSERT a row stamped with another
organisation's id - it simply cannot read it back afterwards. That is a
write-side hole, and it is repaired here by giving those five the same
`USING` + `WITH CHECK` + `FORCE` shape every other protected table has.

## Why FORCE, everywhere

Without `FORCE ROW LEVEL SECURITY` the table OWNER bypasses its own policies.
The migration role owns every table, so any future path that connects as the
owner would silently see everything. FORCE removes that exemption.

## The three tables that cannot use the dominant policy

The dominant policy is a two-GUC contract over `organization_id` AND
`is_demo`. Three tables carry no `is_demo` column:

```text
nf_active_opportunity_sources
nf_organization_capability_profiles
nf_tenant_eligibility_matches
```

Copying the dominant policy onto them would reference a column that does not
exist and the migration would fail. They get an organisation-only policy
instead - the honest equivalent, enforcing the tenant boundary without a demo
dimension the schema never modelled. Adding `is_demo` to them is a schema
change and belongs in its own migration, not here.

## Why the source-collection tables are included

`nf_source_collection_jobs`, `_job_leases` and `_orchestration_cycles` look
like worker coordination, and they are. They also carry `organization_id NOT
NULL`, and `nf_source_collection_raw_payloads` carries `body_bytes` with a
`fact_status` whose vocabulary includes `tenant_supplied`. Rows that can hold
one tenant's bytes are tenant data whoever reads them.

Nothing breaks today: the orchestrator unit says "NOT INSTALLED, NOT ENABLED",
its worker "refuses every job", zero sources are approved, and no job path
calls `apply_org_rls_gucs` - only the API request path does. So a worker that
does not exist cannot be broken, and when one is built it will fail closed
until it declares whose work it is doing. That is the correct direction for
that decision to fail.

## This migration adds no table, column, index or constraint

It changes who may read and write rows that already exist. Nothing here
touches SQLite, which uses the demo-trigger path instead and has no RLS.
"""

from __future__ import annotations

from alembic import op

revision: str = "0066"
down_revision: str | None = "0065"
branch_labels: str | None = None
depends_on: str | None = None


#: `organization_id` is NOT one type across this schema. Migrations up to
#: 0049 declare it `uuid`; 0060 and 0063-0065 declare it `sa.Text()`. The
#: dominant policy casts the GUC with `::uuid`, which raises
#: `operator does not exist: text = uuid` on a text column - PostgreSQL
#: caught this the first time this migration ran. So the predicate is chosen
#: per table from the column's real type rather than copied.
#:
#: uuid + is_demo: the dominant two-GUC contract, unchanged.
UUID_TWO_GUC: tuple[str, ...] = (
    "nf_activation_state",
    "nf_auto_publish_config",
    "nf_source_authorization_decisions",
    "nf_source_collection_execution_attempts",
    "nf_source_collection_job_leases",
    "nf_source_collection_jobs",
    "nf_source_collection_raw_payloads",
    "nf_source_orchestration_cycles",
    "nf_source_robots_evidence",
)

#: text + is_demo: same contract, no cast. The GUC is already text.
TEXT_TWO_GUC: tuple[str, ...] = (
    "nf_commercial_benefit_extensions",
    "nf_commercial_entitlement_state",
    "nf_commercial_ledger_events",
    "nf_customer_decision_history",
    "nf_customer_opportunity_decisions",
    "nf_organization_defaults",
    "nf_organization_invitations",
    "nf_organization_profile_versions",
    "nf_personal_dashboard_overrides",
    "nf_tribal_authority_evidence",
    "nf_tribal_authority_grants",
)

#: No is_demo column at all. Organisation-only policy; see the docstring.
UUID_ORG_ONLY: tuple[str, ...] = ("nf_active_opportunity_sources",)
TEXT_ORG_ONLY: tuple[str, ...] = (
    "nf_organization_capability_profiles",
    "nf_tenant_eligibility_matches",
)

#: Already have RLS from the 0042-era pattern, but only USING - no WITH CHECK
#: and no FORCE. All five are uuid + is_demo. Repaired in place, keeping their
#: existing policy names.
WEAK_POLICY_TABLES: dict[str, str] = {
    "nf_digest_delivery_intents": "nf_digest_delivery_intents_org_isolation",
    "nf_membership_invites": "nf_membership_invites_org_isolation",
    "nf_source_watchlist_entries": "nf_source_watchlist_entries_org_isolation",
    "nf_tenant_digest_records": "nf_tenant_digest_records_org_isolation",
    "nf_tenant_pursuit_suppressions": "nf_tenant_pursuit_suppressions_org_isolation",
}

_UUID_TWO_GUC_PREDICATE = """(
    organization_id = current_setting('app.current_org_id', true)::uuid
    AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
)"""

_TEXT_TWO_GUC_PREDICATE = """(
    organization_id = current_setting('app.current_org_id', true)
    AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
)"""

_UUID_ORG_ONLY_PREDICATE = """(
    organization_id = current_setting('app.current_org_id', true)::uuid
)"""

_TEXT_ORG_ONLY_PREDICATE = """(
    organization_id = current_setting('app.current_org_id', true)
)"""

#: Every table this migration protects, with the predicate its schema allows.
_PROTECTED: tuple[tuple[tuple[str, ...], str], ...] = (
    (UUID_TWO_GUC, _UUID_TWO_GUC_PREDICATE),
    (TEXT_TWO_GUC, _TEXT_TWO_GUC_PREDICATE),
    (UUID_ORG_ONLY, _UUID_ORG_ONLY_PREDICATE),
    (TEXT_ORG_ONLY, _TEXT_ORG_ONLY_PREDICATE),
)


def _policy_name(table: str) -> str:
    return f"{table}_org_isolation"


def _protect(table: str, predicate: str) -> None:
    policy = _policy_name(table)
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
    op.execute(
        f"CREATE POLICY {policy} ON {table} FOR ALL "
        f"USING {predicate} WITH CHECK {predicate}"
    )


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        # SQLite has no RLS. Its isolation comes from the demo-alignment
        # triggers the earlier migrations install, and this migration has
        # nothing to add there.
        return

    for tables, predicate in _PROTECTED:
        for table in tables:
            _protect(table, predicate)

    # The five weak policies: keep the existing name, add the missing half.
    for table, existing_policy in WEAK_POLICY_TABLES.items():
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"ALTER POLICY {existing_policy} ON {table} "
            f"USING {_UUID_TWO_GUC_PREDICATE} "
            f"WITH CHECK {_UUID_TWO_GUC_PREDICATE}"
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    for table, existing_policy in WEAK_POLICY_TABLES.items():
        op.execute(
            f"ALTER POLICY {existing_policy} ON {table} "
            f"USING {_UUID_TWO_GUC_PREDICATE}"
        )
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")

    for tables, _predicate in _PROTECTED:
        for table in tables:
            op.execute(f"DROP POLICY IF EXISTS {_policy_name(table)} ON {table}")
            op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
