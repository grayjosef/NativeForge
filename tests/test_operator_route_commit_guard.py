"""An operator route must not commit a transaction something else already did.

`canonical_opportunity_batch_repository.persist_observations` commits the
connection it was handed, after each chunk's SAVEPOINT. That is deliberate -
the batch is its unit of atomicity - but it means a caller that also commits
is committing a transaction that no longer exists:

    sqlalchemy.exc.InvalidRequestError: This transaction is inactive

In production that turned a successful bounded funding enrichment into a 500.
The enrichment had run; the response said it had failed. A caller reading that
500 would reasonably retry, or conclude the corpus could not be enriched.

This is a source-level invariant because the suite runs on SQLite through a
session the routes never actually commit twice in test conditions - the seam
only opens when `persist_observations` does real chunked work. A behavioural
test here would pass while the defect shipped, which is what happened.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "src" / "nativeforge" / "api"

#: Modules whose routes call enrichment paths that persist observations.
GUARDED_MODULES = ("opportunity_value_routes.py",)


def _unguarded_commits(source: str) -> list[int]:
    """Lines calling `session.commit()` not guarded by `in_transaction()`.

    Guarded means the commit is inside an `if` whose test mentions
    `in_transaction`. Checked structurally rather than by reading the previous
    line, so reformatting cannot silently defeat it.
    """
    tree = ast.parse(source)
    guarded: set[int] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if "in_transaction" not in ast.dump(node.test):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute):
                if inner.func.attr == "commit":
                    guarded.add(inner.lineno)

    unguarded: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "commit":
            continue
        if not isinstance(node.func.value, ast.Name):
            continue
        if node.func.value.id != "session":
            continue
        if node.lineno not in guarded:
            unguarded.append(node.lineno)
    return sorted(unguarded)


def test_no_operator_route_commits_unconditionally():
    """The rule. Guard the commit; do not delete the detector."""
    offences: list[str] = []
    for name in GUARDED_MODULES:
        path = API / name
        for line in _unguarded_commits(path.read_text(encoding="utf-8")):
            offences.append(f"{name}:{line}")
    assert offences == [], (
        "session.commit() not guarded by session.in_transaction(): "
        + ", ".join(offences)
    )


def test_the_detector_can_still_fire():
    """Falsifies the rule above.

    A scan that silently matches nothing is the usual way a detector written
    after the fix ends up protecting nothing.
    """
    bad = "def r(session):\n    session.commit()\n"
    assert _unguarded_commits(bad) == [2]

    good = (
        "def r(session):\n"
        "    if session.in_transaction():\n"
        "        session.commit()\n"
    )
    assert _unguarded_commits(good) == []

    # A commit on something that is not the route session is not this rule's
    # business - the repository is entitled to commit its own connection.
    other = "def r(connection):\n    connection.commit()\n"
    assert _unguarded_commits(other) == []


def test_the_repository_still_commits_its_own_connection():
    """Pins the behaviour the guard exists to tolerate.

    If `persist_observations` ever stops committing, the guard becomes
    unnecessary and this file should be revisited rather than left asserting
    a hazard that no longer exists.
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
