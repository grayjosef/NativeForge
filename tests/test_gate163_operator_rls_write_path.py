"""Gate 163 operator writes must set demo tenant RLS context on PostgreSQL."""

from __future__ import annotations

import re
from pathlib import Path

from nativeforge.repositories.source_authorization_decision_repository import (
    describe_write_failure,
)

REPO = Path(__file__).resolve().parents[1]

OPERATOR_SCRIPTS = (
    "scripts/record_gate163_grants_gov_decisions.py",
    "scripts/record_gate163_live_fetch_opt_in.py",
    "scripts/run_gate163_robots_preflight.py",
)


def test_describe_write_failure_surfaces_sqlstate_without_connection_secrets() -> None:
    class Orig:
        sqlstate = "42501"

    class Wrapped(Exception):
        pass

    exc = Wrapped("ignored")
    exc.orig = Orig()  # type: ignore[attr-defined]
    exc.orig.args = (  # type: ignore[attr-defined]
        'new row violates row-level security policy for table "nf_source_authorization_decisions"',
    )

    described = describe_write_failure(exc)
    assert "42501" in described
    assert "row-level security" in described
    assert "://" not in described
    assert "password" not in described.lower()


def test_operator_scripts_apply_demo_rls_before_database_work() -> None:
    pattern = re.compile(
        r"session = SessionLocal\(\)\s*(?:#.*\n\s*)*apply_org_rls_gucs\(session",
        re.MULTILINE,
    )
    for relative in OPERATOR_SCRIPTS:
        source = (REPO / relative).read_text(encoding="utf-8")
        assert "apply_org_rls_gucs" in source
        assert '"demo"' in source or "'demo'" in source
        assert pattern.search(source), relative
