"""A boolean column must be bound a bool, and SQLite will never tell us.

`is_demo` is `boolean` in PostgreSQL. psycopg binds a Python `int` as
`smallint`, so

    {"demo": 1 if is_demo else 0}

raises `DatatypeMismatch: column "is_demo" is of type boolean but expression
is of type smallint` on an INSERT, and fails the operator lookup on a
comparison. SQLite accepts the integer silently and stores it, so the whole
suite passes and the failure appears only in production.

That is exactly what happened: the first substantive demo write to reach the
database after the M0 entitlement bypass was switched on returned 500, and the
cause was this bind in `customer_decision_repository_service`. A sweep then
found ten more of the same shape - in onboarding, entitlement persistence,
provisioning and the early-signal queue - every one of them on the Customer #1
path and every one of them a production 500 waiting for its first real call.

This test is the detector that SQLite cannot be. It is deliberately a source
scan rather than a database test: a PostgreSQL fixture would only cover the
statements a test happens to execute, and the whole problem is that these
statements had never been executed against PostgreSQL at all.

Counts are not booleans. `deliverable_count`, `text_chars` and `rows_read` are
integers and `1 if ... else 0` is correct for them, so the rule is scoped to
parameter names that a migration declares boolean rather than to the idiom.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "nativeforge"
MIGRATIONS = ROOT / "alembic" / "versions"

#: Parameter names used in this codebase for columns declared boolean.
#: Keyed by bind name because that is what the scan can see; the value names
#: the column it lands in, so a reader can check the claim.
BOOLEAN_BINDS: dict[str, str] = {
    "demo": "is_demo",
    "review": "review_required",
    "ei": "establishes_identity",
    "ea": "establishes_affiliation",
    "eauth": "establishes_authority",
    "forgiven": "maintenance_forgiven",
    "real_only": "counts_toward_real_metrics",
}


def _boolean_columns() -> set[str]:
    """Read the boolean columns out of the migrations, not out of a list."""
    found: set[str] = set()
    pattern = re.compile(r"sa\.Column\(\s*\"([a-z_]+)\"\s*,\s*sa\.Boolean")
    for path in MIGRATIONS.glob("*.py"):
        found.update(pattern.findall(path.read_text(encoding="utf-8")))
    return found


def test_the_columns_this_test_protects_are_really_boolean():
    """Falsifies the mapping above against the migrations.

    Without this, BOOLEAN_BINDS could drift into naming columns that are not
    boolean and the rule below would be enforcing a superstition.
    """
    declared = _boolean_columns()
    assert declared, "no boolean columns found - the migration scan is broken"
    for bind, column in BOOLEAN_BINDS.items():
        assert column in declared, f"{bind} -> {column} is not a boolean column"


def _int_bool_binds(tree: ast.AST) -> list[tuple[str, int]]:
    """Dict entries of the form `"name": 1 if x else 0` for a boolean name."""
    offenders: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                continue
            if key.value not in BOOLEAN_BINDS:
                continue
            if not isinstance(value, ast.IfExp):
                continue
            branches = (value.body, value.orelse)
            if all(
                isinstance(b, ast.Constant) and isinstance(b.value, int)
                and not isinstance(b.value, bool)
                for b in branches
            ):
                offenders.append((key.value, key.lineno))
    return offenders


def test_no_boolean_column_is_bound_an_integer():
    """The rule. Fix the bind, do not widen BOOLEAN_BINDS to silence it."""
    bad: list[str] = []
    for path in SRC.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a syntax error is its own test
            continue
        for name, line in _int_bool_binds(tree):
            bad.append(
                f"{path.relative_to(ROOT)}:{line} binds "
                f"{BOOLEAN_BINDS[name]!r} as an int via {name!r}"
            )
    assert bad == [], "integer bound to a boolean column:\n" + "\n".join(sorted(bad))


def test_the_detector_can_still_fire():
    """Falsifies the scan itself.

    Every assertion above is worthless if `_int_bool_binds` quietly matches
    nothing - which is the failure mode of a detector written against code
    that has already been fixed.
    """
    offending = ast.parse('params = {"demo": 1 if x else 0}')
    assert _int_bool_binds(offending) == [("demo", 1)]

    corrected = ast.parse('params = {"demo": bool(x)}')
    assert _int_bool_binds(corrected) == []

    a_count = ast.parse('params = {"rows_read": 1 if row else 0}')
    assert _int_bool_binds(a_count) == [], "counts are not booleans"
