"""An operator route must not commit a transaction something else already did.

canonical_opportunity_batch_repository.persist_observations commits the
connection it was handed, after each chunk SAVEPOINT. That is deliberate --
the batch is its unit of atomicity -- but it means a caller that also commits
is committing a transaction that no longer exists:

    sqlalchemy.exc.InvalidRequestError: This transaction is inactive

In production that turned a successful bounded funding enrichment into a 500.
The enrichment had run; the response said it had failed. A caller reading that
500 would reasonably retry work that already happened.

Two things worth recording, because both cost a deploy.

The first fix was an `if session.in_transaction()` guard. It does not work.
That reports the ORM session's own state, which still reads True after the
underlying connection was committed out from under it, so production 500ed
again with an identical traceback. The working condition is the exact error,
matched narrowly, with anything else re-raised.

Second, this is a source-level invariant because the suite cannot reach the
seam. On SQLite the routes are never driven through chunked
persist_observations work, so a behavioural test passes while the defect
ships -- which is exactly what happened.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "src" / "nativeforge" / "api"

MODULE = "opportunity_value_routes.py"
HELPER = "_commit_if_still_ours"


def _raw_session_commits(source: str) -> list[int]:
    """Lines calling session.commit() outside the shared helper.

    The helper itself is allowed to call it -- that is where the narrow
    handler lives. Every route must delegate rather than commit directly.
    """
    tree = ast.parse(source)

    helper_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == HELPER:
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call):
                    helper_lines.add(inner.lineno)

    offences: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "commit":
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "session":
            continue
        if node.lineno in helper_lines:
            continue
        offences.append(node.lineno)
    return sorted(offences)


def test_every_route_delegates_its_commit():
    source = (API / MODULE).read_text(encoding="utf-8")
    offences = _raw_session_commits(source)
    assert offences == [], (
        f"session.commit() called directly in {MODULE} at lines {offences}; "
        f"route commits must go through {HELPER}"
    )


def test_the_helper_matches_only_the_inactive_transaction_error():
    """A handler written for one problem must not swallow every other.

    Checked on the source because the behaviour that matters is the re-raise,
    and a test that only exercised the happy path would pass against a bare
    `except Exception: pass`.
    """
    source = (API / MODULE).read_text(encoding="utf-8")
    helper = source.split(f"def {HELPER}", 1)[1].split("\n@", 1)[0]
    assert "InvalidRequestError" in helper
    assert "transaction is inactive" in helper
    assert "raise" in helper
    assert "except Exception" not in helper


def test_the_detector_can_still_fire():
    """Falsifies the rule above."""
    bad = "def r(session):\n    session.commit()\n"
    assert _raw_session_commits(bad) == [2]

    delegated = "def r(session):\n    _commit_if_still_ours(session)\n"
    assert _raw_session_commits(delegated) == []

    # The repository is entitled to commit its own connection.
    other = "def r(connection):\n    connection.commit()\n"
    assert _raw_session_commits(other) == []


def test_the_repository_still_commits_its_own_connection():
    """Pins the behaviour the helper exists to tolerate.

    If persist_observations ever stops committing, the helper is unnecessary
    and this file should be revisited rather than left asserting a hazard
    that no longer exists.
    """
    repo = (
        ROOT
        / "src"
        / "nativeforge"
        / "repositories"
        / "canonical_opportunity_batch_repository.py"
    ).read_text(encoding="utf-8")
    assert "connection.commit()" in repo
    assert "begin_nested()" in repo
