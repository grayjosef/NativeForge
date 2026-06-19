"""Sprint 171: funding opportunity intake status model (offline)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_funding_opportunity_intake_status_v1"

STATUS_DRAFT = "draft"
STATUS_PENDING_REVIEW = "pending_review"
STATUS_BLOCKED_FAIL_CLOSED = "blocked_fail_closed"
STATUS_DUPLICATE_PENDING_OPERATOR = "duplicate_pending_operator"
STATUS_APPROVED_PREVIEW = "approved_preview"
STATUS_REJECTED = "rejected"

INTAKE_STATUSES: tuple[str, ...] = (
    STATUS_DRAFT,
    STATUS_PENDING_REVIEW,
    STATUS_BLOCKED_FAIL_CLOSED,
    STATUS_DUPLICATE_PENDING_OPERATOR,
    STATUS_APPROVED_PREVIEW,
    STATUS_REJECTED,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def derive_intake_status(
    *,
    fail_closed_blocked: bool,
    duplicate_pending_operator: bool,
    operator_approved: bool,
    rejected: bool = False,
) -> dict[str, Any]:
    if rejected:
        status = STATUS_REJECTED
    elif fail_closed_blocked:
        status = STATUS_BLOCKED_FAIL_CLOSED
    elif duplicate_pending_operator:
        status = STATUS_DUPLICATE_PENDING_OPERATOR
    elif operator_approved:
        status = STATUS_APPROVED_PREVIEW
    else:
        status = STATUS_PENDING_REVIEW
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "intake_status": status,
            "status_reason": f"derived:{status}",
        }
    )
