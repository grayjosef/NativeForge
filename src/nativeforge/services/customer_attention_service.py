"""In-app attention derived from persisted pursuit and deadline state.

No invented notifications. Each item opens a real object. Read receipts are
optional and stored only when a customer marks one read.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

SCHEMA_VERSION = "nf_customer_attention_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _days_until(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        due = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None
    return (due - datetime.now(UTC).date()).days


def build_attention_items(
    *,
    pursuits: list[dict[str, Any]] | None = None,
    sparks: list[dict[str, Any]] | None = None,
    tasks: list[dict[str, Any]] | None = None,
    profile_complete: bool = True,
    membership_count: int = 1,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    if not profile_complete:
        items.append(
            {
                "id": "org-profile-incomplete",
                "kind": "organization",
                "title": "Complete the organization profile",
                "detail": "Eligibility and matching stay incomplete until identity facts are filled.",
                "href": "?view=organization",
                "severity": "warning",
            }
        )

    for spark in sparks or []:
        days = _days_until(str(spark.get("close_date") or spark.get("deadline") or ""))
        if days is not None and 0 <= days <= 21:
            sid = str(spark.get("id") or spark.get("spark_id") or "")
            items.append(
                {
                    "id": f"deadline:{sid}",
                    "kind": "deadline",
                    "title": str(spark.get("title") or "Upcoming deadline"),
                    "detail": f"{days} day{'s' if days != 1 else ''} remaining",
                    "href": "?view=opportunities",
                    "severity": "warning" if days <= 7 else "info",
                    "deadline": str(spark.get("close_date") or spark.get("deadline") or ""),
                    "funder": str(spark.get("agency") or spark.get("funder") or ""),
                }
            )

    for task in tasks or []:
        if task.get("done") or task.get("completed"):
            continue
        if task.get("blocked") or str(task.get("status") or "") == "blocked":
            items.append(
                {
                    "id": f"blocker:{task.get('id')}",
                    "kind": "blocker",
                    "title": str(task.get("title") or "Pursuit blocked"),
                    "detail": str(task.get("blocker") or "A required step is blocked."),
                    "href": "?view=pursuits",
                    "severity": "critical",
                }
            )
        elif task.get("overdue"):
            items.append(
                {
                    "id": f"overdue:{task.get('id')}",
                    "kind": "task",
                    "title": str(task.get("title") or "Overdue work"),
                    "detail": "This task is past due.",
                    "href": "?view=pursuits",
                    "severity": "warning",
                }
            )

    if membership_count < 1:
        items.append(
            {
                "id": "members-missing",
                "kind": "admin",
                "title": "No organization members",
                "detail": "Bind at least one member before inviting a team.",
                "href": "?view=organization",
                "severity": "warning",
            }
        )

    _ = pursuits
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "item_count": len(items),
            "items": items,
            "email_required": False,
            "fabricated": False,
        }
    )
