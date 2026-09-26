"""Make the database say no, in CI, on every commit.

SQLite is the development lane and it has no row-level security at all, so the
entire tenant boundary is invisible to the default test suite. Every isolation
claim this repository makes is a claim about PostgreSQL, and until this gate
existed nothing checked it outside a developer's machine.

Two things are checked, and they are different:

1. COVERAGE - every table carrying an `organization_id` has RLS enabled, has
   FORCE (so the owner is not exempt), has at least one policy, and no
   permissive `FOR ALL` policy is missing its `WITH CHECK`. A `USING` clause
   filters reads; without `WITH CHECK` the same policy lets a tenant write a
   row belonging to someone else.

2. REFUSAL - an adversarial matrix run as a role that is NOSUPERUSER and
   NOBYPASSRLS and owns nothing. A superuser bypasses RLS unconditionally
   regardless of FORCE, so a matrix run as the owner proves nothing. Positive
   controls are included deliberately: a test that only ever asserts zero rows
   passes just as well against an empty table, which is why "A reads its own
   row" is checked alongside "A cannot read B".

Exits non-zero on any failure. Requires DATABASE_URL to name a PostgreSQL
database already migrated to head.
"""

from __future__ import annotations

import os
import sys

import psycopg

#: The role the matrix runs as. Created here, never a superuser.
APP_ROLE = "nf_ci_app"

#: The representative table. Its predicate is the text-typed one, written
#: because PostgreSQL rejects a uuid cast against a text column, so it is the
#: one most likely to be subtly wrong. It is also the most tenant-private
#: table in the system: one row per organisation per opportunity.
TABLE = "nf_customer_opportunity_decisions"

#: Every canonical_id this gate creates, so cleanup and the aggregation checks
#: can name them exactly. A LIKE wildcard survives neither Python formatting
#: nor psycopg parameter interpolation intact, and a mangled pattern silently
#: matches nothing - which looks exactly like the isolation working.
SEEDED = ["adv_a", "adv_b", "adv_own", "adv_forged"]

ORG_A = "aaaaaaa1-0000-4000-8000-00000000000a"
ORG_B = "bbbbbbb2-0000-4000-8000-00000000000b"

results: list[tuple[str, bool]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    verdict = "PASS" if ok else "FAIL"
    results.append((name, ok))
    print(f"  {name:<58} {verdict} {detail}")


TENANT_TABLES_SQL = """
    SELECT c.relname,
           c.relrowsecurity,
           c.relforcerowsecurity,
           (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid),
           (SELECT count(*) FROM pg_policy p
              WHERE p.polrelid = c.oid
                AND p.polcmd = '*'
                AND p.polwithcheck IS NULL)
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relkind = 'r'
       AND EXISTS (SELECT 1 FROM information_schema.columns col
                    WHERE col.table_schema = 'public'
                      AND col.table_name = c.relname
                      AND col.column_name = 'organization_id')
     ORDER BY c.relname
"""


def main() -> int:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL is not set")
        return 2
    # psql/libpq cannot parse SQLAlchemy's driver suffix.
    libpq = url.replace("postgresql+psycopg://", "postgresql://")
    if not libpq.startswith("postgresql://"):
        scheme = libpq.split("://")[0]
        print(f"DATABASE_URL is not PostgreSQL: {scheme}")
        return 2

    admin = psycopg.connect(libpq, autocommit=True)

    print("=== COVERAGE: every organization_id table is actually protected ===")
    with admin.cursor() as cur:
        cur.execute(TENANT_TABLES_SQL)
        rows = cur.fetchall()

    if not rows:
        print("  no tenant tables found - the schema is not migrated")
        return 2

    gaps: list[str] = []
    for name, rls, force, policies, vacuous in rows:
        problems = []
        if not rls:
            problems.append("no_rls")
        if not force:
            problems.append("no_force")
        if not policies:
            problems.append("no_policy")
        if vacuous:
            problems.append(f"for_all_policy_without_with_check={vacuous}")
        if problems:
            gaps.append(f"{name}: {','.join(problems)}")

    print(f"  tenant tables: {len(rows)}")
    record("every tenant table has RLS, FORCE, a policy and a WITH CHECK", not gaps)
    for gap in gaps:
        print(f"     {gap}")

    print()
    print("=== ROLE UNDER TEST ===")
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
        if not cur.fetchone():
            cur.execute(
                f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD 'ci' "
                "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
            )
        cur.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
        cur.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
            f"IN SCHEMA public TO {APP_ROLE}"
        )
        cur.execute(f"GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
        cur.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s",
            (APP_ROLE,),
        )
        is_super, bypasses = cur.fetchone()

    print(f"  {APP_ROLE} rolsuper={is_super} rolbypassrls={bypasses}")
    record("the matrix runs as a non-superuser", is_super is False)
    record("the matrix runs as a role that cannot bypass RLS", bypasses is False)
    if is_super or bypasses:
        print("\nthe role can bypass the thing under test; refusing to continue")
        return 1

    # Seed as the owner, which RLS does not stop.
    with admin.cursor() as cur:
        for org in (ORG_A, ORG_B):
            cur.execute(
                "INSERT INTO organizations (id, org_type, display_name) "
                "VALUES (%s, 'real', 'ci-isolation') ON CONFLICT (id) DO NOTHING",
                (org,),
            )
        cur.execute(f"DELETE FROM {TABLE} WHERE canonical_id = ANY(%s)", (SEEDED,))
        for org, tag in ((ORG_A, "a"), (ORG_B, "b")):
            cur.execute(
                f"INSERT INTO {TABLE} (organization_id, canonical_id, "
                "decision_state, is_demo, model_version, actor_id, decided_at) "
                "VALUES (%s, %s, 'WATCHED', false, 'v1', 'actor-1', now())",
                (org, f"adv_{tag}"),
            )

    app = psycopg.connect(_as_role(libpq, APP_ROLE), autocommit=False)

    def scoped(org: str, demo: str = "false"):
        cur = app.cursor()
        cur.execute("SELECT set_config('app.current_org_id', %s, true)", (str(org),))
        cur.execute("SELECT set_config('app.current_org_is_demo', %s, true)", (demo,))
        return cur

    def safe(cur, sql: str, args: tuple = ()):
        try:
            cur.execute(sql, args)
            return cur.fetchone()[0] if cur.description else cur.rowcount
        except psycopg.Error as exc:
            return type(exc).__name__

    listed = f"SELECT count(*) FROM {TABLE} WHERE canonical_id = ANY(%s)"
    one = f"SELECT count(*) FROM {TABLE} WHERE canonical_id = %s"

    print()
    print("=== SELECT ===")
    app.rollback()
    cur = scoped(ORG_A)
    record("positive control: A reads its own row", safe(cur, one, ("adv_a",)) == 1)
    record("A cannot read B", safe(cur, one, ("adv_b",)) == 0)
    app.rollback()
    cur = scoped(ORG_B)
    record("positive control: B reads its own row", safe(cur, one, ("adv_b",)) == 1)
    record("B cannot read A", safe(cur, one, ("adv_a",)) == 0)

    print()
    print("=== AGGREGATION ===")
    app.rollback()
    cur = scoped(ORG_A)
    record("A's total row count excludes B", safe(cur, listed, (SEEDED,)) == 1)
    record(
        "aggregation cannot see B",
        safe(
            cur,
            f"SELECT count(DISTINCT organization_id) FROM {TABLE} "
            "WHERE canonical_id = ANY(%s)",
            (SEEDED,),
        )
        == 1,
    )

    print()
    print("=== NO / INVALID CONTEXT ===")
    for label, setup in (
        ("no context fails closed", None),
        ("unknown org fails closed", "cccccccc-0000-4000-8000-00000000000c"),
        ("malformed org fails closed", "not-a-uuid"),
    ):
        app.rollback()
        cur = app.cursor() if setup is None else scoped(setup)
        result = safe(cur, listed, (SEEDED,))
        record(label, result == 0 or isinstance(result, str), f"result={result}")

    app.rollback()
    cur = scoped(ORG_A, demo="true")
    result = safe(cur, one, ("adv_a",))
    record("right org, wrong demo flag sees nothing", result == 0, f"result={result}")

    print()
    print("=== INSERT (WITH CHECK) ===")
    insert = (
        f"INSERT INTO {TABLE} (organization_id, canonical_id, decision_state, "
        "is_demo, model_version, actor_id, decided_at) "
        "VALUES (%s, %s, 'WATCHED', false, 'v1', 'actor-1', now())"
    )
    app.rollback()
    cur = scoped(ORG_A)
    result = safe(cur, insert, (ORG_A, "adv_own"))
    record("positive control: A inserts as A", not isinstance(result, str), str(result))
    app.rollback()
    cur = scoped(ORG_A)
    result = safe(cur, insert, (ORG_B, "adv_forged"))
    record("A cannot insert a row owned by B", isinstance(result, str), str(result))

    print()
    print("=== UPDATE / DELETE ===")
    app.rollback()
    cur = scoped(ORG_A)
    result = safe(
        cur,
        f"UPDATE {TABLE} SET decision_state='DISMISSED' WHERE canonical_id=%s",
        ("adv_b",),
    )
    record("A cannot update B's row", result == 0, f"rowcount={result}")
    app.rollback()
    cur = scoped(ORG_A)
    result = safe(cur, f"DELETE FROM {TABLE} WHERE canonical_id=%s", ("adv_b",))
    record("A cannot delete B's row", result == 0, f"rowcount={result}")

    print()
    print("=== TRANSACTION SCOPE ===")
    app.rollback()
    cur = scoped(ORG_A)
    cur.execute(one, ("adv_a",))
    app.commit()
    cur = app.cursor()
    cur.execute("SELECT current_setting('app.current_org_id', true)")
    after = cur.fetchone()[0]
    result = safe(cur, one, ("adv_a",))
    record(
        "context does not survive commit",
        after in (None, "") and (result == 0 or isinstance(result, str)),
        f"setting={after!r} after={result}",
    )
    app.rollback()

    failed = [name for name, ok in results if not ok]
    print()
    print(
        f"checks={len(results)} passed={len(results) - len(failed)} "
        f"failed={len(failed)}"
    )
    for name in failed:
        print(f"  FAILED: {name}")
    return 1 if failed else 0


def _as_role(libpq_url: str, role: str) -> str:
    """Swap the user in a libpq URL, leaving everything else alone."""
    scheme, rest = libpq_url.split("://", 1)
    if "@" in rest:
        rest = rest.split("@", 1)[1]
    return f"{scheme}://{role}:ci@{rest}"


if __name__ == "__main__":
    sys.exit(main())
