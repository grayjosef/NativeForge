"""Shared live collection permit checks (warrant + authorization + opt-in)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from nativeforge.services.source_live_authorization_service import (
    authorize_source_for_live_access,
)
from nativeforge.services.source_live_fetch_opt_in_service import is_live_fetch_opted_in
from nativeforge.services.source_live_warrant_service import (
    WARRANT_SOURCE_COLLECTION,
    evaluate_live_request,
)


@dataclass(frozen=True)
class CollectionRefusal:
    reasons: list[str]


def assert_bounded_collection_permitted(
    connection: Any,
    *,
    organization_id: uuid.UUID,
    source_id: str,
    request_url: str,
    method: str,
) -> CollectionRefusal | None:
    authorization = authorize_source_for_live_access(
        connection=connection,
        organization_id=organization_id,
        source_id=source_id,
        purpose="source_collection",
        method=method,
        exercise_runtime=True,
    )
    if str(authorization.get("authorization_status") or "") != "approved":
        return CollectionRefusal(
            reasons=[
                f"authorization:{authorization.get('authorization_status')}",
                *(authorization.get("refusal_reasons") or []),
            ]
        )
    if not is_live_fetch_opted_in(
        connection=connection, organization_id=organization_id, source_id=source_id
    ):
        return CollectionRefusal(reasons=["live_fetch_not_opted_in"])
    warrant = evaluate_live_request(
        warrant_kind=WARRANT_SOURCE_COLLECTION,
        authorized_source_id=source_id,
        request_url=request_url,
        method=method,
        connection=connection,
        organization_id=organization_id,
    )
    if not warrant.get("permitted"):
        return CollectionRefusal(
            reasons=list(warrant.get("refusal_reasons") or ["warrant_not_permitted"])
        )
    return None
