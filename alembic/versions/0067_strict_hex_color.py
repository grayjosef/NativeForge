"""Alembic 0067: make the colour constraint mean what its name always said.

`ck_nf_organization_defaults_primary_color_is_hex` did not check that the
value was hex. 0063 wrote it as

```text
primary_color IS NULL OR
(primary_color GLOB '#[0-9a-fA-F]*' AND
 (length(primary_color) = 4 OR length(primary_color) = 7))
```

and in SQLite GLOB the `*` is a shell wildcard meaning "any sequence", not a
regex quantifier. So it required a `#`, exactly ONE hex character, and then
anything at all, at a total length of 4 or 7. `#1zzz` and `#abcxyz` both
passed a constraint named `_is_hex`.

## Why this is a separate migration

0063 was repaired for PostgreSQL portability only - GLOB does not exist there.
That was a translation and deliberately preserved the weak semantics, because
silently strengthening a constraint while porting it hides the change. This
migration makes the semantic change on its own, where it can be reviewed as
one.

## Compatibility was checked before it was written

Every `primary_color` value in the repository was scanned: the dev SQLite
databases, fixtures, tests, seeds, scripts and docs. Nine literals exist.
Seven are valid six-digit hex. The two that are not are both the string
`'red'`, and both are NEGATIVE cases asserting that unsafe branding is
refused - `test_unsafe_branding_is_refused` and a
`branding_invariant_failures` assertion. Nothing stored anywhere would fail
the strict rule, so no data migration is required.

Worth noting: the application layer already rejected `'red'`. The database
was the weaker of the two. This makes them agree.

## The rule

```text
#RGB      exactly three hex digits
#RRGGBB   exactly six hex digits
NULL      still allowed; the column is nullable and absence is meaningful
```

Case-insensitive, as CSS is. Nothing else.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0067"
down_revision: str | None = "0066"
branch_labels: str | None = None
depends_on: str | None = None

DEFAULTS = "nf_organization_defaults"
CONSTRAINT = f"ck_{DEFAULTS}_primary_color_is_hex"

#: PostgreSQL: one anchored regex with an alternation. `~` is a regex match
#: here; in SQLite it is a bitwise NOT, which is why this is dialect-split.
_PG_STRICT = (
    "primary_color IS NULL OR "
    "primary_color ~ '^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$'"
)

#: SQLite: GLOB is whole-string anchored and its character classes match
#: exactly one character each, so spelling the digits out gives exact lengths
#: without a separate length() test.
_HEX = "[0-9a-fA-F]"
_SQLITE_STRICT = (
    "primary_color IS NULL OR "
    f"primary_color GLOB '#{_HEX * 3}' OR "
    f"primary_color GLOB '#{_HEX * 6}'"
)

#: What 0063 leaves in place, for a faithful downgrade.
_PG_LOOSE = (
    "primary_color IS NULL OR "
    "(primary_color ~ '^#[0-9a-fA-F]' AND "
    "(length(primary_color) = 4 OR length(primary_color) = 7))"
)
_SQLITE_LOOSE = (
    "primary_color IS NULL OR "
    "(primary_color GLOB '#[0-9a-fA-F]*' AND "
    "(length(primary_color) = 4 OR length(primary_color) = 7))"
)


def _swap(expression: str) -> None:
    # batch_alter_table so SQLite, which cannot DROP CONSTRAINT, rebuilds the
    # table instead of failing.
    with op.batch_alter_table(DEFAULTS, schema=None) as batch:
        batch.drop_constraint(CONSTRAINT, type_="check")
        batch.create_check_constraint(CONSTRAINT, sa.text(expression))


def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"
    _swap(_PG_STRICT if is_pg else _SQLITE_STRICT)


def downgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"
    _swap(_PG_LOOSE if is_pg else _SQLITE_LOOSE)
