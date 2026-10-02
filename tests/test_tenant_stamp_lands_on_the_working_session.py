"""The tenant GUCs must be stamped on the connection the handler writes through.

`apply_org_rls_gucs` runs `set_config(..., is_local => true)` on one Session.
If an org-scoped route then writes through a DIFFERENT Session, the stamp is
on the wrong connection and the write meets the no-tenant sentinel instead of
its tenant:

    psycopg.errors.InsufficientPrivilege: new row violates row-level security
    policy for table "nf_customer_opportunity_decisions"

That is what controlled-live did. `get_org_context_from_session` asked for
`deps.get_db` while all 54 org-scoped route modules ask for
`deps_db.get_db_session`. The two functions are identical in body, which is
exactly why the split survived review - but FastAPI caches dependencies per
request BY CALLABLE, so asking for the other name produced a second Session
on a second connection.

It could not fail locally. SQLite does not implement row-level security, so
every one of these writes succeeds in the suite no matter which connection it
uses. Reads hid it too: the unstamped connection returns no rows rather than
raising, so a read path looks merely empty.

This is therefore a source-level invariant, not a behavioural test. There is
no database available to the suite that could express it.
"""

from __future__ import annotations

import ast
import inspect
import typing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTEXT_MODULE = (
    ROOT / "src" / "nativeforge" / "api" / "customer_org_context_dependency.py"
)

#: The one session dependency org-scoped routes use.
CANONICAL_SESSION_DEPENDENCY = "get_db_session"


def test_the_org_context_uses_the_same_session_dependency_as_the_routes():
    """The invariant. Change the routes if you must, but not only one side."""
    from nativeforge.api import customer_org_context_dependency as mod

    # `get_type_hints`, not `inspect.signature`: the module uses
    # `from __future__ import annotations`, so the signature hands back the
    # annotation as a STRING and its Annotated metadata is unreachable. The
    # first version of this test read `.default`, found nothing, and failed
    # against correct code - a detector that cannot see the thing it guards.
    hints = typing.get_type_hints(mod.get_org_context_from_session, include_extras=True)
    metadata = getattr(hints["db"], "__metadata__", ())
    dependency = next(
        (
            getattr(entry, "dependency", None)
            for entry in metadata
            if getattr(entry, "dependency", None) is not None
        ),
        None,
    )
    assert dependency is not None, "db is no longer a Depends(...) parameter"
    assert dependency.__name__ == CANONICAL_SESSION_DEPENDENCY, (
        f"org context stamps {dependency.__name__!r} but org-scoped routes "
        f"write through {CANONICAL_SESSION_DEPENDENCY!r}; the tenant GUCs "
        "would land on a connection that does no tenant work"
    )


def test_the_context_module_does_not_import_the_other_session_dependency():
    """Belt and braces: the wrong name should not be reachable here at all,
    so a future edit cannot quietly reintroduce the split."""
    source = CONTEXT_MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.asname or alias.name)
    assert "get_db" not in imported, (
        "customer_org_context_dependency imports deps.get_db again; it must "
        "share the routes' session dependency"
    )
    assert CANONICAL_SESSION_DEPENDENCY in imported


def test_the_stamp_is_still_applied_here():
    """Falsifies the two tests above.

    They only matter because this module is where the tenant is stamped. If
    `apply_org_rls_gucs` moved elsewhere, agreeing about the session
    dependency would protect nothing and this file should be rewritten rather
    than left passing.
    """
    source = CONTEXT_MODULE.read_text(encoding="utf-8")
    assert "apply_org_rls_gucs(db," in source
