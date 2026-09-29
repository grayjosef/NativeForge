"""Dialect-safe upserts for Gate 173–175 intelligence tables."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa


def dialect_name(connection: sa.engine.Connection) -> str:
    return str(connection.dialect.name or "default")


def sql_bool_literal(connection: sa.engine.Connection, *, value: bool) -> str:
    """SQLite stores booleans as 0/1; Postgres uses true/false."""
    if dialect_name(connection) == "sqlite":
        return "1" if value else "0"
    return "true" if value else "false"


def is_current_active_sql(
    connection: sa.engine.Connection, *, column: str = "is_current"
) -> str:
    return f"{column} = {sql_bool_literal(connection, value=True)}"


def is_current_inactive_sql(
    connection: sa.engine.Connection, *, column: str = "is_current"
) -> str:
    return f"{column} = {sql_bool_literal(connection, value=False)}"


def insert_or_replace_rows(
    connection: sa.engine.Connection,
    *,
    table: str,
    columns: tuple[str, ...],
    rows: list[dict[str, Any]],
    primary_key: str,
) -> int:
    """SQLite INSERT OR REPLACE; Postgres INSERT … ON CONFLICT DO UPDATE."""
    if not rows:
        return 0
    col_list = ", ".join(columns)
    val_list = ", ".join(f":{c}" for c in columns)
    if dialect_name(connection) == "sqlite":
        sql = f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({val_list})"
        connection.execute(sa.text(sql), rows)
        return len(rows)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != primary_key)
    sql = (
        f"INSERT INTO {table} ({col_list}) VALUES ({val_list}) "
        f"ON CONFLICT ({primary_key}) DO UPDATE SET {updates}"
    )
    connection.execute(sa.text(sql), rows)
    return len(rows)
