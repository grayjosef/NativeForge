"""Normalize strings before persistence to PostgreSQL text-compatible values."""

from __future__ import annotations


def sanitize_postgres_text(value: str | None) -> str | None:
    """
    Remove NUL bytes (0x00). PostgreSQL ``text`` fields reject embedded NUL.

    Preserves ``None`` and ordinary UTF-8 content unchanged otherwise.
    """
    if value is None:
        return None
    return value.replace("\x00", "")
