"""The role the first-sign-in bootstrap asks for must be one the database keeps.

`api/auth.py` passed `role="owner"`. Migration 0024's CHECK allows
`org_owner`, `org_admin`, `authorized_representative`, `grant_lead`,
`reviewer` and `viewer` - not `owner` - so `insert_membership` refused it as
`membership_role_not_storable:owner` and the bootstrap could never write a
row. On any deployment. With or without tenant context.

Nothing caught it because the fixtures that create memberships pass their own
role, and the one caller that passes a literal is the one nobody exercised
against a real database.

So this reads the literal out of the source rather than re-stating it, which
is the only version of this test that can fail when someone edits the caller.
"""

from __future__ import annotations

import ast
from pathlib import Path

from nativeforge.services.dev_org_membership_bootstrap_service import (
    STORABLE_ROLES,
    STORABLE_STATES,
    TRUSTED_MEMBERSHIP_SOURCES,
)

AUTH_SOURCE = Path(__file__).resolve().parents[1] / "src/nativeforge/api/auth.py"


def bootstrap_call_keywords() -> dict[str, object]:
    """The literal keywords `auth.py` passes to `insert_membership`."""
    tree = ast.parse(AUTH_SOURCE.read_text(encoding="utf-8"), filename=str(AUTH_SOURCE))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name != "insert_membership":
            continue
        found: dict[str, object] = {}
        for kw in node.keywords:
            if kw.arg and isinstance(kw.value, ast.Constant):
                found[kw.arg] = kw.value.value
        return found
    raise AssertionError("no insert_membership call found in api/auth.py")


def test_the_call_is_found_at_all():
    """A parser that matched nothing would make every assertion below vacuous."""
    keywords = bootstrap_call_keywords()
    assert {"state", "role", "membership_source"} <= set(keywords)


def test_the_bootstrap_role_is_storable():
    """The regression. `owner` is not a role this database has ever accepted."""
    role = bootstrap_call_keywords()["role"]
    assert role in STORABLE_ROLES, (
        f"api/auth.py asks insert_membership for role={role!r}, which migration "
        f"0024 refuses. Storable roles are {sorted(STORABLE_ROLES)}."
    )


def test_the_bootstrap_role_is_the_owner_role_specifically():
    """A first sign-in bootstraps the organization's owner, not a viewer.

    Pinned separately from storability: `viewer` would satisfy the check above
    and silently give the first customer no authority over their own tenant.
    """
    assert bootstrap_call_keywords()["role"] == "org_owner"


def test_the_bootstrap_state_and_source_are_storable_too():
    """The same class of bug, one field over."""
    keywords = bootstrap_call_keywords()
    assert keywords["state"] in STORABLE_STATES
    assert keywords["membership_source"] in TRUSTED_MEMBERSHIP_SOURCES


def test_owner_is_still_not_a_storable_role():
    """Guards the guard.

    If `owner` were ever added to the vocabulary, the test above would pass
    for the wrong reason and this file would stop meaning anything.
    """
    assert "owner" not in STORABLE_ROLES
