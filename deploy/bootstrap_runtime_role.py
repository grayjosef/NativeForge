"""Create the non-superuser role the application should actually connect as.

## Why this exists

A managed PostgreSQL service hands out one credential, and it is a superuser.
Connecting the application as that role silently disables every row-level
security policy in the schema: a superuser bypasses RLS unconditionally,
regardless of `FORCE ROW LEVEL SECURITY`.

That is not a theoretical concern here. The managed runtime verifier reported
exactly this - 18 of 18 adversarial checks passing while
`rolsuper=True, rolbypassrls=True` for the connecting role - because the
matrix creates its own restricted role to test with. The policies were
correct and the application was exempt from them.

## What it does

Creates `nf_app`, NOSUPERUSER and NOBYPASSRLS, with DML on the existing
tables and nothing else. It is idempotent: re-running alters the password and
re-grants rather than failing, so it is safe in a boot path.

## What it deliberately does not do

It does not own anything. Ownership is left with the migration role, so
`nf_app` cannot DROP, ALTER or disable a policy on a table it does not own -
and FORCE RLS is what stops the owner's exemption applying to the
application. It is granted no DDL, no CREATE, and nothing on future tables
beyond the default privileges set here, so a new table arrives unreachable
until a migration grants it explicitly. That is the safer failure direction:
a missing grant is an error, an accidental grant is a silent hole.

Run with the MIGRATION (owner) credential. The password comes from the
environment and is never logged.
"""

from __future__ import annotations

import os
import sys

RUNTIME_ROLE = "nf_app"


def main() -> int:
    owner_url = os.environ.get("NF_MIGRATION_DATABASE_URL") or os.environ.get(
        "DATABASE_URL", ""
    )
    password = os.environ.get("NF_APP_DB_PASSWORD", "")

    if not owner_url:
        print("[bootstrap] FATAL: no migration/owner DATABASE_URL")
        return 2
    if not password:
        print("[bootstrap] FATAL: NF_APP_DB_PASSWORD is not set")
        return 2

    libpq = owner_url.replace("postgresql+psycopg://", "postgresql://")

    import psycopg
    from psycopg import sql

    with psycopg.connect(libpq, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (RUNTIME_ROLE,))
        exists = cur.fetchone() is not None

        role = sql.Identifier(RUNTIME_ROLE)
        secret = sql.Literal(password)
        if exists:
            print(
                f"[bootstrap] role {RUNTIME_ROLE} exists; re-applying password and limits"
            )
            cur.execute(
                sql.SQL(
                    "ALTER ROLE {} WITH LOGIN PASSWORD {} "
                    "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT"
                ).format(role, secret)
            )
        else:
            print(f"[bootstrap] creating role {RUNTIME_ROLE}")
            cur.execute(
                sql.SQL(
                    "CREATE ROLE {} WITH LOGIN PASSWORD {} "
                    "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT"
                ).format(role, secret)
            )

        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
        cur.execute(
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}"
            ).format(role)
        )
        cur.execute(
            sql.SQL(
                "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}"
            ).format(role)
        )
        # Tables created by future migrations, which run as the owner.
        cur.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
            ).format(role)
        )
        cur.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT USAGE, SELECT ON SEQUENCES TO {}"
            ).format(role)
        )

        cur.execute(
            "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole "
            "FROM pg_roles WHERE rolname = %s",
            (RUNTIME_ROLE,),
        )
        is_super, bypasses, createdb, createrole = cur.fetchone()
        cur.execute(
            """
            SELECT count(*) FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind = 'r'
               AND pg_get_userbyid(c.relowner) = %s
            """,
            (RUNTIME_ROLE,),
        )
        owned = cur.fetchone()[0]

    print(f"[bootstrap] {RUNTIME_ROLE}: rolsuper={is_super} rolbypassrls={bypasses}")
    print(f"[bootstrap] {RUNTIME_ROLE}: createdb={createdb} createrole={createrole}")
    print(f"[bootstrap] {RUNTIME_ROLE}: tables owned={owned}")

    ok = is_super is False and bypasses is False and owned == 0
    print("[bootstrap] RUNTIME_ROLE_SAFE=" + ("YES" if ok else "NO"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
