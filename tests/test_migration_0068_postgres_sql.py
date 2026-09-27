"""What migration 0068 actually sends to PostgreSQL.

The tenant boundary for these two tables is row-level security, and row-level
security is invisible on SQLite - the migration's PostgreSQL branch is skipped
entirely there, so a local `alembic upgrade head` proves the tables exist and
proves nothing at all about whether they are protected.

Alembic's offline mode renders the migration through the real PostgreSQL
dialect without a server, which is the strongest check available on a machine
with no PostgreSQL to run. It compiles the DDL for real: a column type the
dialect cannot render, a malformed constraint or a policy statement that was
never emitted all fail here.

## What this does not prove

That the statements execute. A policy naming a column that does not exist
compiles as text and fails on arrival, and nothing here would catch it.
Cross-tenant denial at runtime is proven by
`scripts/check_postgres_tenant_isolation.py` against a real database, which is
the gate that has to run before this is trusted in production.

It is a guard rather than a proof, and its value is that it fails when
somebody later drops `WITH CHECK`, forgets `FORCE`, or adds a third tenant
table to this migration without a policy - none of which any SQLite run can
notice.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Offline mode needs a URL to pick a dialect and never connects, so these are
#: placeholders, not credentials.
OFFLINE_URL = "postgresql+psycopg://placeholder:placeholder@localhost:5432/placeholder"

TABLES = ("nf_opportunity_contacts", "nf_opportunity_submission_paths")

#: The predicate both policies must carry, on both halves. Whitespace is
#: normalised before comparison because the renderer's line breaks are not
#: part of the contract.
PREDICATE = (
    "organization_id = current_setting('app.current_org_id', true)::uuid "
    "AND is_demo = current_setting('app.current_org_is_demo', true)::boolean"
)


def _render(revisions: str) -> str:
    """The SQL alembic would send, for one revision range."""
    completed = subprocess.run(
        [str(REPO_ROOT / ".venv/bin/alembic"), "upgrade", revisions, "--sql"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "DATABASE_URL": OFFLINE_URL,
            "HOME": str(Path.home()),
        },
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"alembic --sql failed for {revisions}:\n{completed.stderr[-3000:]}"
        )
    return completed.stdout


@pytest.fixture(scope="module")
def upgrade_sql() -> str:
    return _render("0067:0068")


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_both_tables_are_created(upgrade_sql: str) -> None:
    for table in TABLES:
        assert f"CREATE TABLE {table}" in upgrade_sql, table


def test_uuid_columns_render_as_native_postgres_uuid(upgrade_sql: str) -> None:
    """Not VARCHAR(32).

    SQLite stores a UUID as hex text, and a migration that rendered the same
    on PostgreSQL would still work while making every join and index worse and
    breaking the `::uuid` cast the policies depend on.
    """
    assert "organization_id UUID NOT NULL" in upgrade_sql
    assert "grant_spark_id UUID NOT NULL" in upgrade_sql


def test_timestamps_keep_their_timezone(upgrade_sql: str) -> None:
    """A submission deadline without a zone is a deadline in no particular
    place, which is the one thing it must never be."""
    assert "deadline_at TIMESTAMP WITH TIME ZONE" in upgrade_sql


def test_row_level_security_is_enabled_and_forced(upgrade_sql: str) -> None:
    """FORCE matters as much as ENABLE.

    Without `FORCE ROW LEVEL SECURITY` the table's owner bypasses its own
    policies, and the owner is the role migrations run as.
    """
    for table in TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in upgrade_sql, table
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in upgrade_sql, table


def test_each_policy_carries_using_and_with_check(upgrade_sql: str) -> None:
    """`USING` filters reads. `WITH CHECK` constrains writes.

    With `USING` alone a tenant can INSERT a row stamped with another
    organization's id - visible to nobody, owned by somebody else, and a
    silent cross-tenant write. Five tables in this codebase shipped that way
    before migration 0066 repaired them.
    """
    squashed = _squash(upgrade_sql)
    for table in TABLES:
        policy = f"CREATE POLICY {table}_org_isolation ON {table} FOR ALL"
        assert policy in squashed, table
        statement = squashed.split(policy, 1)[1].split(";", 1)[0]
        assert f"USING ({PREDICATE})" in statement, table
        assert f"WITH CHECK ({PREDICATE})" in statement, table


def test_the_policy_checks_both_gucs_not_just_the_organization(
    upgrade_sql: str,
) -> None:
    """The demo/real separation is the second half of the tenant boundary."""
    assert upgrade_sql.count("app.current_org_is_demo") == 4  # two halves, two tables


def test_foreign_keys_cascade_from_both_parents(upgrade_sql: str) -> None:
    squashed = _squash(upgrade_sql)
    assert (
        squashed.count(
            "FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE"
        )
        == 2
    )
    assert (
        squashed.count(
            "FOREIGN KEY(grant_spark_id) REFERENCES nf_grant_sparks (id) ON DELETE CASCADE"
        )
        == 2
    )


def test_tenant_columns_are_indexed(upgrade_sql: str) -> None:
    """Every read is scoped by organization; an unindexed predicate on the
    hot path is a performance problem that only appears with customers."""
    for table in TABLES:
        assert f"ON {table} (organization_id)" in upgrade_sql, table
        assert f"ON {table} (grant_spark_id)" in upgrade_sql, table


def test_verified_cannot_be_stored_without_a_route_and_a_date(
    upgrade_sql: str,
) -> None:
    """The constraint that caught the service disagreeing with itself.

    `assess_completeness` called a path verified on a route plus deadline
    *text*; this refused the insert, and it was right - "11:59 PM ET" with no
    date is not a deadline.
    """
    squashed = _squash(upgrade_sql)
    assert "ck_nf_submission_paths_verified_is_complete" in squashed
    assert (
        "CHECK (completeness <> 'verified' OR ( "
        "(submission_url IS NOT NULL OR recipient_email IS NOT NULL) "
        "AND deadline_at IS NOT NULL))" in squashed
    )


def test_a_contact_must_have_some_way_to_reach_somebody(upgrade_sql: str) -> None:
    squashed = _squash(upgrade_sql)
    assert "ck_nf_opportunity_contacts_reachable" in squashed
    assert (
        "CHECK (email IS NOT NULL OR phone IS NOT NULL "
        "OR website IS NOT NULL OR office IS NOT NULL)" in squashed
    )


def test_customer_provided_is_a_storable_provenance(upgrade_sql: str) -> None:
    """The column that keeps a customer's own note from ever being promoted."""
    assert "'source_document', 'source_page', 'customer_provided'" in upgrade_sql


def test_the_renderer_is_actually_producing_this_migration(
    upgrade_sql: str,
) -> None:
    """Falsifies every assertion above.

    All of them would pass vacuously against an empty string or against the
    wrong revision range.
    """
    assert len(upgrade_sql) > 2000
    assert "UPDATE alembic_version SET version_num='0068'" in upgrade_sql
    assert "0066" not in upgrade_sql
