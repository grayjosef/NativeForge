"""Dialect-safe upserts for Gate 173–175 intelligence tables."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa


def dialect_name(connection: sa.engine.Connection) -> str:
    return str(connection.dialect.name or "default")


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
