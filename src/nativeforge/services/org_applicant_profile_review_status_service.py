"""Sprint 200: org/applicant profile review status model."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_org_applicant_profile_review_status_v1"

STATUS_DRAFT = "draft"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_REVIEWED = "reviewed"
STATUS_VERIFIED_BY_USER = "verified_by_user"
STATUS_STALE = "stale"
STATUS_INCOMPLETE = "incomplete"
STATUS_ARCHIVED = "archived"

REVIEW_STATUSES: tuple[str, ...] = (
    STATUS_DRAFT,
    STATUS_NEEDS_REVIEW,
    STATUS_REVIEWED,
    STATUS_VERIFIED_BY_USER,
    STATUS_STALE,
    STATUS_INCOMPLETE,
    STATUS_ARCHIVED,
)

_TERMINAL_STATUSES = frozenset({STATUS_VERIFIED_BY_USER, STATUS_ARCHIVED})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_valid_review_status(status: str) -> bool:
    return status in REVIEW_STATUSES


def is_terminal_review_status(status: str) -> bool:
    return status in _TERMINAL_STATUSES


def build_review_status_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "review_statuses": list(REVIEW_STATUSES),
            "terminal_statuses": sorted(_TERMINAL_STATUSES),
            "preview_only": True,
        }
    )
