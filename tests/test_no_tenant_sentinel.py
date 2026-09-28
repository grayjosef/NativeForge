"""Empty string is not a tenant state, and PostgreSQL agrees violently.

Every policy here reads the anchor as
`current_setting('app.current_org_id', true)::uuid`. Never-set returns NULL and
denies quietly, which is correct. But a GUC that has been set once and then
reverted - which is what `set_config(..., is_local => true)` does at the end of
every transaction - comes back as `''`, and `''::uuid` RAISES.

On a pooled connection that is enough to abort the next request's transaction
before it can establish any context of its own. Controlled-live died exactly
there: the first read of `nf_org_memberships` in the OAuth callback errored,
and the demo bootstrap downstream never ran.

The PostgreSQL cases below are the whole point of this file - the failure is a
property of the database, not of Python, and a mock cannot show it. They skip
when no local server is available rather than passing vacuously.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

from nativeforge.api import deps, deps_db
from nativeforge.db.rls import (
    IS_DEMO_GUC,
    NO_TENANT_ORG_ID,
    ORG_ID_GUC,
    apply_org_rls_gucs,
    clear_org_rls_gucs,
)

PG_BIN = Path.home() / ".pgtmp/root/usr/lib/postgresql/16/bin"


# --------------------------------------------------------- the sentinel


def test_the_sentinel_is_a_valid_uuid_and_is_nil():
    assert NO_TENANT_ORG_ID == uuid.UUID("00000000-0000-0000-0000-000000000000")
    # The property that matters: PostgreSQL can cast it.
    assert str(NO_TENANT_ORG_ID) == "00000000-0000-0000-0000-000000000000"


class RecordingSession:
    """Captures what would be sent, without a database."""

    def __init__(self, dialect: str = "postgresql"):
        self.bind = type("Bind", (), {"dialect": type("D", (), {"name": dialect})()})()
        self.calls: list[tuple[str, dict]] = []

    def execute(self, statement, params=None):  # noqa: ANN001
        self.calls.append((str(statement), params or {}))
        return None


def test_no_tenant_context_sets_the_all_zero_uuid():
    session = RecordingSession()
    clear_org_rls_gucs(session)

    values = [p.get("oid") or p.get("d") for _, p in session.calls]
    assert str(NO_TENANT_ORG_ID) in values


def test_no_tenant_context_never_sets_an_empty_string():
    """The regression, stated as an assertion about what is sent."""
    session = RecordingSession()
    clear_org_rls_gucs(session)

    for _, params in session.calls:
        for value in params.values():
            assert value != "", params


def test_the_demo_flag_is_set_false_alongside_it():
    """Never half-set. A sentinel claiming to be a demo would be stranger
    than either field alone."""
    session = RecordingSession()
    clear_org_rls_gucs(session)

    sent = {p.get("oid") or p.get("d") for _, p in session.calls}
    assert "false" in sent


def test_a_real_organization_still_sets_its_own_id():
    session = RecordingSession()
    org = uuid.uuid4()
    apply_org_rls_gucs(session, org, "demo")

    sent = [p.get("oid") or p.get("d") for _, p in session.calls]
    assert str(org) in sent
    assert "true" in sent
    assert str(NO_TENANT_ORG_ID) not in sent


def test_sqlite_is_a_no_op():
    session = RecordingSession(dialect="sqlite")
    clear_org_rls_gucs(session)
    apply_org_rls_gucs(session, uuid.uuid4(), "demo")
    assert session.calls == []


def test_both_session_dependencies_clear_the_context():
    """The two places a request gets a session. Missing one leaves the hole
    open for exactly the routes that use it - and the OAuth callback was on
    the side that had no dependency doing this at all."""
    for module in (deps, deps_db):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "clear_org_rls_gucs(db)" in source, module.__name__


# --------------------------------------- PostgreSQL: the actual behaviour


def _pg_available() -> bool:
    return (PG_BIN / "initdb").is_file()


@pytest.fixture(scope="module")
def pg_url(tmp_path_factory):
    if not _pg_available():
        pytest.skip("no local PostgreSQL server binaries")

    data = tmp_path_factory.mktemp("pg")
    sock = data / "sock"
    sock.mkdir()
    port = "54331"
    env = {
        **os.environ,
        "LD_LIBRARY_PATH": str(Path.home() / ".pgtmp/root/usr/lib/x86_64-linux-gnu"),
    }
    subprocess.run(
        [str(PG_BIN / "initdb"), "-D", str(data / "pgdata"), "-U", "postgres",
         "--auth=trust"],
        check=True, capture_output=True, env=env,
    )
    subprocess.run(
        [str(PG_BIN / "pg_ctl"), "-D", str(data / "pgdata"),
         "-o", f"-p {port} -k {sock} -c listen_addresses=", "-l", str(data / "log"),
         "start"],
        check=True, capture_output=True, env=env,
    )
    url = f"postgresql+psycopg://postgres@/postgres?host={sock}&port={port}"
    try:
        yield url
    finally:
        subprocess.run(
            [str(PG_BIN / "pg_ctl"), "-D", str(data / "pgdata"), "-m", "immediate",
             "stop"],
            capture_output=True, env=env,
        )


@pytest.fixture()
def tenant_table(pg_url):
    """One table shaped like the real schema, and a role that RLS applies to.

    The first version of this fixture connected as `postgres`. A superuser
    bypasses row-level security unconditionally - FORCE included - so the
    policy was never evaluated, nothing was ever denied, and three tests
    passed while proving nothing. The seeded row matters for the same reason:
    `count(*)` over an empty table never evaluates the policy expression, so
    the empty-string cast never gets the chance to raise.
    """
    engine = sa.create_engine(pg_url)
    seeded_org = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(sa.text("DROP TABLE IF EXISTS rls_probe"))
        conn.execute(
            sa.text(
                "CREATE TABLE rls_probe ("
                " id serial primary key,"
                " organization_id uuid not null,"
                " is_demo boolean not null)"
            )
        )
        # Seeded before RLS is switched on, so there is a row for the policy
        # to be evaluated against.
        conn.execute(
            sa.text(
                "INSERT INTO rls_probe (organization_id, is_demo) VALUES (:o, true)"
            ),
            {"o": str(seeded_org)},
        )
        conn.execute(sa.text("ALTER TABLE rls_probe ENABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text("ALTER TABLE rls_probe FORCE ROW LEVEL SECURITY"))
        conn.execute(
            sa.text(
                "CREATE POLICY rls_probe_scope ON rls_probe USING ("
                f" organization_id = current_setting('{ORG_ID_GUC}', true)::uuid"
                f" AND is_demo = current_setting('{IS_DEMO_GUC}', true)::boolean)"
                " WITH CHECK ("
                f" organization_id = current_setting('{ORG_ID_GUC}', true)::uuid"
                f" AND is_demo = current_setting('{IS_DEMO_GUC}', true)::boolean)"
            )
        )
        # Created once and reused. Dropping it between tests fails as soon as
        # it holds a grant on the schema, and the table drop above already
        # takes its table privileges with it.
        conn.execute(
            sa.text(
                "DO $$ BEGIN"
                " IF NOT EXISTS (SELECT 1 FROM pg_roles"
                "                WHERE rolname = 'rls_probe_app') THEN"
                "  CREATE ROLE rls_probe_app LOGIN NOSUPERUSER NOBYPASSRLS"
                "   PASSWORD 'probe';"
                " END IF;"
                " END $$"
            )
        )
        conn.execute(sa.text("GRANT USAGE ON SCHEMA public TO rls_probe_app"))
        conn.execute(
            sa.text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON rls_probe TO rls_probe_app"
            )
        )
        conn.execute(
            sa.text(
                "GRANT USAGE, SELECT ON SEQUENCE rls_probe_id_seq TO rls_probe_app"
            )
        )

    restricted = sa.create_engine(pg_url.replace("postgres@", "rls_probe_app:probe@"))
    with restricted.begin() as conn:
        role = conn.execute(sa.text("SELECT current_user")).scalar_one()
        props = conn.execute(
            sa.text(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"
            ),
            {"r": role},
        ).first()
        # If this is ever a superuser again, every assertion below is vacuous.
        assert props == (False, False), props

    restricted.seeded_org = seeded_org  # type: ignore[attr-defined]
    return restricted


def test_the_probe_role_is_actually_subject_to_rls(tenant_table):
    """Guards the fixture. A superuser here would make the file meaningless."""
    with tenant_table.begin() as conn:
        role = conn.execute(sa.text("SELECT current_user")).scalar_one()
        props = conn.execute(
            sa.text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"),
            {"r": role},
        ).first()
    assert props == (False, False)


def test_postgres_raises_on_an_empty_string_anchor(tenant_table):
    """The falsification. This is the production failure, reproduced.

    If this ever stops raising, the sentinel has stopped being necessary and
    this whole module can go.
    """
    with tenant_table.begin() as conn:
        conn.execute(sa.text(f"SELECT set_config('{ORG_ID_GUC}', '', true)"))
        conn.execute(sa.text(f"SELECT set_config('{IS_DEMO_GUC}', 'false', true)"))
        with pytest.raises(Exception) as caught:
            conn.execute(sa.text("SELECT count(*) FROM rls_probe")).scalar_one()

    assert "invalid input syntax for type uuid" in str(caught.value)


def test_the_sentinel_reads_without_raising_and_returns_nothing(tenant_table):
    """And the fix: the policy evaluates, denies, and the transaction lives."""
    with tenant_table.begin() as conn:
        conn.execute(
            sa.text(f"SELECT set_config('{ORG_ID_GUC}', :o, true)"),
            {"o": str(NO_TENANT_ORG_ID)},
        )
        conn.execute(sa.text(f"SELECT set_config('{IS_DEMO_GUC}', 'false', true)"))

        assert conn.execute(sa.text("SELECT count(*) FROM rls_probe")).scalar_one() == 0
        # The transaction is still usable, which is the property that was lost.
        assert conn.execute(sa.text("SELECT 1")).scalar_one() == 1


def test_a_write_under_the_sentinel_is_denied(tenant_table):
    """Read-safe must not mean write-open."""
    with tenant_table.begin() as conn:
        conn.execute(
            sa.text(f"SELECT set_config('{ORG_ID_GUC}', :o, true)"),
            {"o": str(NO_TENANT_ORG_ID)},
        )
        conn.execute(sa.text(f"SELECT set_config('{IS_DEMO_GUC}', 'false', true)"))
        with pytest.raises(Exception) as caught:
            conn.execute(
                sa.text(
                    "INSERT INTO rls_probe (organization_id, is_demo)"
                    " VALUES (:o, true)"
                ),
                {"o": str(uuid.uuid4())},
            )
    assert "row-level security" in str(caught.value).lower()


def test_a_real_tenant_still_reads_and_writes_normally(tenant_table):
    """The sentinel must not have broken the ordinary path."""
    org = uuid.uuid4()
    with tenant_table.begin() as conn:
        conn.execute(
            sa.text(f"SELECT set_config('{ORG_ID_GUC}', :o, true)"), {"o": str(org)}
        )
        conn.execute(sa.text(f"SELECT set_config('{IS_DEMO_GUC}', 'true', true)"))
        conn.execute(
            sa.text(
                "INSERT INTO rls_probe (organization_id, is_demo) VALUES (:o, true)"
            ),
            {"o": str(org)},
        )
        assert conn.execute(sa.text("SELECT count(*) FROM rls_probe")).scalar_one() == 1


def test_the_sentinel_matches_no_real_tenants_rows(tenant_table):
    """A row exists for a real tenant; under the sentinel it is invisible."""
    with tenant_table.begin() as conn:
        conn.execute(
            sa.text(f"SELECT set_config('{ORG_ID_GUC}', :o, true)"),
            {"o": str(NO_TENANT_ORG_ID)},
        )
        conn.execute(sa.text(f"SELECT set_config('{IS_DEMO_GUC}', 'false', true)"))
        assert conn.execute(sa.text("SELECT count(*) FROM rls_probe")).scalar_one() == 0

    # And that row really is there, seen from its own tenant.
    with tenant_table.begin() as conn:
        conn.execute(
            sa.text(f"SELECT set_config('{ORG_ID_GUC}', :o, true)"),
            {"o": str(tenant_table.seeded_org)},
        )
        conn.execute(sa.text(f"SELECT set_config('{IS_DEMO_GUC}', 'true', true)"))
        assert conn.execute(sa.text("SELECT count(*) FROM rls_probe")).scalar_one() == 1


def test_the_context_does_not_survive_its_transaction(tenant_table):
    """`is_local => true`, demonstrated rather than asserted about the source.

    After the transaction ends the anchor reverts - to the empty string, which
    is the behaviour this whole module exists because of.
    """
    with tenant_table.begin() as conn:
        conn.execute(
            sa.text(f"SELECT set_config('{ORG_ID_GUC}', :o, true)"),
            {"o": str(uuid.uuid4())},
        )

    with tenant_table.connect() as conn:
        after = conn.execute(
            sa.text(f"SELECT current_setting('{ORG_ID_GUC}', true)")
        ).scalar_one()
        assert after in ("", None)
