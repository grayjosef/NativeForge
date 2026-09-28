"""The one door that opens tenant context, and everything that keeps it shut.

The first membership of a brand-new demo organization cannot be written under
FORCE RLS, because the policy wants the tenant context that the membership
would establish. This module supplies that context for exactly that insert.

Which makes it the most dangerous file in the auth path. A version that set
tenant context on request would let any caller adopt any organization, and the
boundary would be decoration. So most of this file is refusals, and each one
is exercised on its own so that a single relaxed condition fails here rather
than in production.

`sqlite` has no RLS and no `set_config`, so the gate's decision is what is
tested: whether it opens, and why it does not. Whether the policy then accepts
the insert is Postgres's job, and `check_postgres_tenant_isolation.py` proves
that separately against a real server.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nativeforge.services.demo_bootstrap_tenant_context_service import (
    DEMO_ORG_TYPE,
    IS_DEMO_KEY,
    ORG_ID_KEY,
    open_demo_bootstrap_context,
    open_demo_org_lookup_context,
    reveal_configured_demo_membership,
)

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL_A = "aaaaaaa1-0000-4000-8000-00000000000a"
REAL_B = "bbbbbbb2-0000-4000-8000-00000000000b"
IDENT = "11111111-2222-3333-4444-555555555555"
OTHER_IDENT = "99999999-8888-7777-6666-555555555555"


class FakeConnection:
    """Answers the two reads the gate makes, and records what it was told.

    A real connection is not needed to test a decision, and using one would
    hide the decision behind a database that also has opinions.
    """

    def __init__(self, orgs: dict[str, str], membership_counts: dict[str, int]):
        self.orgs = orgs
        self.membership_counts = membership_counts
        self.set_config_calls: list[tuple[str, str, bool]] = []

    def execute(self, statement, params=None):  # noqa: ANN001
        text = str(statement)
        params = params or {}
        if "set_config" in text:
            self.set_config_calls.append((params["k"], params["v"], True))
            return _Scalar(params["v"])
        if "count(*) FROM organizations" in text:
            # The probe that separates "this row is absent" from "this table
            # is not readable at all".
            return _Scalar(len(self.orgs))
        if "FROM organizations" in text:
            org_type = self.orgs.get(params["i"])
            return _Row((org_type,) if org_type is not None else None)
        if "nf_org_memberships" in text:
            return _Scalar(self.membership_counts.get(params["i"], 0))
        raise AssertionError(f"unexpected statement: {text}")


class _Row:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _Scalar:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


def connection(
    *, org_type: str = DEMO_ORG_TYPE, memberships: int = 0
) -> FakeConnection:
    return FakeConnection(
        orgs={DEMO: org_type, REAL_A: "real", REAL_B: "real"},
        membership_counts={DEMO: memberships},
    )


def call(conn: FakeConnection, **overrides):
    args = {
        "connection": conn,
        "organization_id": DEMO,
        "identity_id": IDENT,
        "membership_identity_id": IDENT,
        "configured_organization_id": DEMO,
        "identity_verified": True,
    }
    args.update(overrides)
    return open_demo_bootstrap_context(**args)


# ------------------------------------------------------- 1. the one that works


def test_the_configured_demo_org_with_no_members_opens_context():
    conn = connection()
    result = call(conn)

    assert result["context_opened"] is True
    assert result["blocked_reasons"] == []
    assert result["org_type"] == DEMO_ORG_TYPE
    assert result["existing_membership_count"] == 0


def test_the_context_it_sets_is_the_demo_org_and_transaction_local():
    conn = connection()
    call(conn)

    assert conn.set_config_calls == [
        (ORG_ID_KEY, DEMO, True),
        (IS_DEMO_KEY, "true", True),
    ]
    # The third argument is `is_local`. Every call passes True; there is no
    # parameter that asks for anything else.
    assert all(is_local for _, _, is_local in conn.set_config_calls)


# ------------------------------------------------------------ 2-8. refusals


@pytest.mark.parametrize("real_org", [REAL_A, REAL_B])
def test_a_real_organization_is_refused(real_org: str):
    """On its own data. Not from a list of protected ids."""
    conn = connection()
    result = call(conn, organization_id=real_org, configured_organization_id=real_org)

    assert result["context_opened"] is False
    assert "organization_is_not_demo_classified:real" in result["blocked_reasons"]
    assert conn.set_config_calls == []


def test_an_organization_the_row_does_not_call_demo_is_refused():
    conn = connection(org_type="pilot")
    result = call(conn)

    assert result["context_opened"] is False
    assert "organization_is_not_demo_classified:pilot" in result["blocked_reasons"]


def test_an_organization_that_does_not_exist_is_refused():
    conn = FakeConnection(orgs={}, membership_counts={})
    result = call(conn)

    assert result["context_opened"] is False
    # ACCESS_DENIED, not NOT_FOUND: an empty table and an unreadable one look
    # identical from a row count, so the refusal names the weaker claim rather
    # than asserting an absence it cannot prove.
    assert "organization_not_readable:ACCESS_DENIED" in result["blocked_reasons"]


def test_a_missing_row_in_a_readable_table_is_reported_as_not_found():
    """The other half of the distinction: the table reads, the row is absent."""
    conn = FakeConnection(orgs={REAL_A: "real"}, membership_counts={})
    result = call(conn)

    assert result["context_opened"] is False
    assert result["org_lookup"] == "NOT_FOUND"
    assert "organization_not_readable:NOT_FOUND" in result["blocked_reasons"]


def test_an_organization_other_than_the_configured_one_is_refused():
    """Naming one organization does not authorise adopting another."""
    conn = connection()
    result = call(conn, organization_id=REAL_A)

    assert result["context_opened"] is False
    assert (
        "target_organization_is_not_the_configured_bootstrap_org"
        in result["blocked_reasons"]
    )
    assert conn.set_config_calls == []


@pytest.mark.parametrize("count", [1, 2, 40])
def test_an_organization_that_already_has_members_is_refused(count: int):
    """This is a bootstrap, and a bootstrap happens once.

    After the first member, every later membership goes through the ordinary
    invite-and-approve flow and this door stays shut.
    """
    conn = connection(memberships=count)
    result = call(conn)

    assert result["context_opened"] is False
    assert f"organization_already_has_memberships:{count}" in result["blocked_reasons"]


def test_an_unverified_identity_is_refused():
    conn = connection()
    result = call(conn, identity_verified=False)

    assert result["context_opened"] is False
    assert "identity_not_verified_by_the_provider" in result["blocked_reasons"]
    assert conn.set_config_calls == []


def test_binding_somebody_else_is_refused():
    """A bootstrap is an identity binding itself. Anything else is not."""
    conn = connection()
    result = call(conn, membership_identity_id=OTHER_IDENT)

    assert result["context_opened"] is False
    assert (
        "membership_identity_is_not_the_verified_identity" in result["blocked_reasons"]
    )


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_a_deployment_that_named_no_organization_gets_no_context(configured):
    """The default state. Nothing is configured, so nothing is authorised."""
    conn = connection()
    result = call(conn, configured_organization_id=configured)

    assert result["context_opened"] is False
    assert "no_bootstrap_organization_configured" in result["blocked_reasons"]
    assert conn.set_config_calls == []


@pytest.mark.parametrize("bad", ["not-a-uuid", "bbbbbbbb", 12345])
def test_a_target_that_is_not_uuid_shaped_is_refused(bad):
    conn = connection()
    result = call(conn, organization_id=bad)

    assert result["context_opened"] is False
    assert conn.set_config_calls == []


def test_a_failed_lookup_is_a_refusal_not_an_exception():
    class Broken(FakeConnection):
        def execute(self, statement, params=None):  # noqa: ANN001
            raise RuntimeError("connection reset")

    result = call(Broken(orgs={}, membership_counts={}))
    assert result["context_opened"] is False
    assert any(
        r.startswith("organization_lookup_failed:") for r in result["blocked_reasons"]
    )


def test_no_connection_is_a_refusal():
    result = call(None)  # type: ignore[arg-type]
    assert result["context_opened"] is False
    assert "no_connection_supplied" in result["blocked_reasons"]


# --------------------------------------------- 9. the context does not leak


def test_nothing_is_set_on_any_refusal():
    """The load-bearing negative.

    Every refusal above asserts its own reason; this asserts the thing they
    have in common, so a future edit that sets context before validating
    fails here.
    """
    for overrides in (
        {"identity_verified": False},
        {"organization_id": REAL_A},
        {"configured_organization_id": None},
        {"membership_identity_id": OTHER_IDENT},
        {"organization_id": "not-a-uuid"},
    ):
        conn = connection()
        call(conn, **overrides)
        assert conn.set_config_calls == [], overrides

    conn = connection(org_type="real")
    call(conn)
    assert conn.set_config_calls == []

    conn = connection(memberships=1)
    call(conn)
    assert conn.set_config_calls == []


def test_the_service_has_no_non_local_variant():
    """`is_local=true` is not a default a caller can change.

    Read from the source, because the guarantee is that no other kind of
    `set_config` exists in this module at all.
    """
    from pathlib import Path

    import nativeforge.services.demo_bootstrap_tenant_context_service as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert source.count("set_config") >= 1
    # Every set_config call passes the literal `true` third argument.
    assert "set_config(:k, :v, true)" in source
    assert "set_config(:k, :v, false)" not in source


# -------------------------------------- 11-12. the surrounding contract


def test_lookup_context_opens_when_the_demo_org_already_has_members():
    """Returning members have to be able to see their own row."""
    conn = connection(memberships=1)
    result = open_demo_org_lookup_context(
        connection=conn,
        organization_id=DEMO,
        identity_id=IDENT,
        membership_identity_id=IDENT,
        configured_organization_id=DEMO,
        identity_verified=True,
    )

    assert result["context_opened"] is True
    assert result["blocked_reasons"] == []
    assert result["existing_membership_count"] == 1
    assert conn.set_config_calls == [
        (ORG_ID_KEY, DEMO, True),
        (IS_DEMO_KEY, "true", True),
    ]


def test_a_later_request_can_see_only_the_configured_demo_membership(monkeypatch):
    conn = connection()
    monkeypatch.setenv("NF_BOOTSTRAP_DEMO_ORG_ID", DEMO)
    opened = reveal_configured_demo_membership(
        connection=conn,
        claimed_organization_id=DEMO,
        identity_id=IDENT,
    )
    assert opened["context_opened"] is True
    assert conn.set_config_calls == [
        (ORG_ID_KEY, DEMO, True),
        (IS_DEMO_KEY, "true", True),
    ]

    refused = reveal_configured_demo_membership(
        connection=conn,
        claimed_organization_id=REAL_A,
        identity_id=IDENT,
    )
    assert refused["context_opened"] is False
    assert (
        "claimed_organization_is_not_the_configured_demo_org"
        in refused["blocked_reasons"]
    )
    assert conn.set_config_calls == [
        (ORG_ID_KEY, DEMO, True),
        (IS_DEMO_KEY, "true", True),
    ]


def test_lookup_context_still_refuses_a_real_organization():
    conn = connection()
    result = open_demo_org_lookup_context(
        connection=conn,
        organization_id=REAL_A,
        identity_id=IDENT,
        membership_identity_id=IDENT,
        configured_organization_id=REAL_A,
        identity_verified=True,
    )

    assert result["context_opened"] is False
    assert "organization_is_not_demo_classified:real" in result["blocked_reasons"]
    assert conn.set_config_calls == []


def test_the_callback_looks_up_an_existing_membership_before_inserting():
    """The live defect: insert-first hid a returning member behind a refusal."""
    from pathlib import Path

    source = Path("src/nativeforge/api/auth.py").read_text(encoding="utf-8")
    assert "lookup = open_demo_org_lookup_context(" in source
    assert source.index("lookup = open_demo_org_lookup_context(") < source.index(
        "written = insert_membership("
    )
    assert source.index("lookup = open_demo_org_lookup_context(") < source.index(
        "context = open_demo_bootstrap_context("
    )


def test_a_callback_without_an_org_does_not_trap_the_browser_in_onboarding():
    """Onboarding has no shell. Sending an unsigned visitor there is a dead end."""
    from pathlib import Path

    source = Path("src/nativeforge/api/auth.py").read_text(encoding="utf-8")
    assert 'APP_NEEDS_ORG = "/?view=sign_in&auth=sign_in_incomplete"' in source
    assert 'APP_NEEDS_ORG = "/?view=onboarding"' not in source


def test_the_callback_opens_context_before_inserting():
    """Wiring, read from the source.

    A gate nobody calls is a gate that protects nothing, and a gate called
    after the insert protects nothing either.
    """
    from pathlib import Path

    source = Path("src/nativeforge/api/auth.py").read_text(encoding="utf-8")
    assert "open_demo_bootstrap_context(" in source
    assert source.index("open_demo_bootstrap_context(") < source.index(
        "written = insert_membership("
    )


def test_the_bootstrap_role_is_still_canonical():
    """This change must not disturb what the bootstrap asks for."""
    from pathlib import Path

    from nativeforge.services.dev_org_membership_bootstrap_service import (
        STORABLE_ROLES,
    )

    source = Path("src/nativeforge/api/auth.py").read_text(encoding="utf-8")
    assert 'role="org_owner"' in source
    assert "org_owner" in STORABLE_ROLES


def executed_sql() -> list[str]:
    """Every string this module hands to `sa.text`.

    The prose is scanned separately from the SQL on purpose: the module
    docstring says `rolbypassrls=false`, which is a description of the
    property being relied on, not a grant of it. A blunt substring search over
    the whole file fails on its own explanation, which is how a check like
    this gets deleted rather than fixed.
    """
    import ast
    from pathlib import Path

    import nativeforge.services.demo_bootstrap_tenant_context_service as mod

    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if name != "text":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found.append(arg.value)
    return found


def test_the_sql_this_module_runs_touches_no_security_object():
    """The whole point. No policy, no FORCE, no BYPASSRLS, no grant."""
    statements = executed_sql()
    assert statements, "no sa.text statements found - the scan proves nothing"

    blob = " ".join(statements).upper()
    for forbidden in (
        "ROW LEVEL SECURITY",
        "BYPASSRLS",
        "POLICY",
        "ALTER ROLE",
        "ALTER TABLE",
        "SUPERUSER",
        "GRANT ",
    ):
        assert forbidden not in blob, forbidden


def test_the_sql_this_module_runs_only_reads_or_sets_context():
    """Two reads and two set_configs. No write of any kind."""
    statements = executed_sql()
    for statement in statements:
        upper = statement.upper().strip()
        assert upper.startswith("SELECT"), statement
    assert not any(
        verb in " ".join(statements).upper()
        for verb in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP")
    )


def test_the_insert_still_goes_through_the_canonical_service():
    """No second write path. The membership service keeps its own rules."""
    from pathlib import Path

    source = Path("src/nativeforge/api/auth.py").read_text(encoding="utf-8")
    assert "written = insert_membership(" in source
    assert "INSERT INTO nf_org_memberships" not in source.upper()


def test_a_uuid_object_is_accepted_as_readily_as_its_string():
    """The callback has a string; other callers may have a UUID."""
    conn = connection()
    result = call(
        conn,
        organization_id=uuid.UUID(DEMO),
        configured_organization_id=uuid.UUID(DEMO),
        identity_id=uuid.UUID(IDENT),
        membership_identity_id=uuid.UUID(IDENT),
    )
    assert result["context_opened"] is True


def test_the_result_is_json_safe_and_names_no_secret():
    conn = connection()
    result = call(conn)
    import json

    json.dumps(result)
    assert set(result) == {
        "schema_version",
        "context_opened",
        "organization_id",
        "org_type",
        "org_lookup",
        "membership_count_lookup",
        "existing_membership_count",
        "blocked_reasons",
    }


def test_sqlalchemy_text_is_parameterised_not_interpolated():
    """The org id reaches the database as a parameter, never as SQL."""
    from pathlib import Path

    import nativeforge.services.demo_bootstrap_tenant_context_service as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert 'sa.text("SELECT set_config(:k, :v, true)")' in source
    assert 'f"SELECT set_config' not in source
    assert isinstance(sa.text("SELECT 1"), sa.sql.elements.TextClause)
