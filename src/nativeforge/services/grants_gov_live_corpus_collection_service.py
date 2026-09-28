"""Warrant-backed Grants.gov Search2 collection through corpus ingest."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa

from nativeforge.db.models import NfActiveOpportunitySource, Organization
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.services.grants_gov_corpus_ingest_service import (
    ingest_grants_gov_search2_payload,
    rollup_collection_metrics,
)
from nativeforge.services.grants_gov_search_api_adapter_service import (
    build_grants_gov_broad_search_body,
)
from nativeforge.services.live_source_transport_service import (
    LiveTransportRefused,
    build_live_transport,
)
from nativeforge.services.source_collection_request_builder_service import (
    build_source_request,
)
from nativeforge.services.source_collection_transport_service import (
    LIVE,
    execute_request,
)
from nativeforge.services.source_live_authorization_service import (
    authorize_source_for_live_access,
)
from nativeforge.services.source_live_fetch_opt_in_service import is_live_fetch_opted_in
from nativeforge.services.source_live_warrant_service import (
    WARRANT_SOURCE_COLLECTION,
    evaluate_live_request,
)
from nativeforge.services.source_raw_payload_persistence_service import (
    persist_raw_payload,
)

SCHEMA_VERSION = "nf_grants_gov_live_corpus_collection_v1"
SEARCH2_URL = "https://api.grants.gov/v1/api/search2"
DEFAULT_BOUNDED_ROWS = 200
TIMEOUT_SECONDS = 45.0


@dataclass(frozen=True)
class CollectionRefusal:
    reasons: list[str]


@dataclass(frozen=True)
class LiveCollectionResult:
    permitted: bool
    dispatched: bool
    http_status: int | None
    search_body: dict[str, Any]
    metrics: dict[str, int]
    canonical_metrics: dict[str, Any]
    payload_sha256: str | None
    attempt_id: str | None
    refusal: CollectionRefusal | None = None


def _refuse(*reasons: str) -> LiveCollectionResult:
    return LiveCollectionResult(
        permitted=False,
        dispatched=False,
        http_status=None,
        search_body={},
        metrics={},
        canonical_metrics={},
        payload_sha256=None,
        attempt_id=None,
        refusal=CollectionRefusal(reasons=list(reasons)),
    )


def assert_collection_permitted(
    connection: Any,
    *,
    organization_id: uuid.UUID,
    source_id: str,
) -> CollectionRefusal | None:
    authorization = authorize_source_for_live_access(
        connection=connection,
        organization_id=organization_id,
        source_id=source_id,
        purpose="source_collection",
        method="POST",
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
        request_url=SEARCH2_URL,
        method="POST",
        connection=connection,
        organization_id=organization_id,
    )
    if not warrant.get("permitted"):
        return CollectionRefusal(
            reasons=list(warrant.get("refusal_reasons") or ["warrant_not_permitted"])
        )
    return None


def stamp_active_source_success(
    session: Any,
    *,
    organization_id: uuid.UUID,
    source_id: str,
    at: dt.datetime,
) -> bool:
    row = session.scalar(
        sa.select(NfActiveOpportunitySource).where(
            sa.and_(
                NfActiveOpportunitySource.organization_id == organization_id,
                NfActiveOpportunitySource.source_id == source_id,
            )
        )
    )
    if row is None:
        return False
    row.last_checked_at = at
    row.last_success_at = at
    row.consecutive_failure_count = 0
    session.flush()
    return True


def run_grants_gov_bounded_live_collection(
    connection: Any,
    session: Any,
    *,
    organization_id: uuid.UUID,
    org_type: OrgType,
    source_id: str,
    job_id: str,
    attempt_number: int,
    rows: int = DEFAULT_BOUNDED_ROWS,
    dry_run: bool = True,
) -> LiveCollectionResult:
    """One bounded Search2 POST, optional persist + ingest."""
    refusal = assert_collection_permitted(
        connection, organization_id=organization_id, source_id=source_id
    )
    search_body = build_grants_gov_broad_search_body(rows=rows)
    if refusal is not None:
        return LiveCollectionResult(
            permitted=False,
            dispatched=False,
            http_status=None,
            search_body=search_body,
            metrics={},
            canonical_metrics={},
            payload_sha256=None,
            attempt_id=None,
            refusal=refusal,
        )

    built = build_source_request(
        source_definition={
            "source_id": source_id,
            "endpoint": SEARCH2_URL,
            "method": "POST",
            "body": json.dumps(search_body, sort_keys=True),
        },
        timeout_seconds=TIMEOUT_SECONDS,
    )
    if not built.get("usable"):
        return LiveCollectionResult(
            permitted=True,
            dispatched=False,
            http_status=None,
            search_body=search_body,
            metrics={},
            canonical_metrics={},
            payload_sha256=None,
            attempt_id=None,
            refusal=CollectionRefusal(
                reasons=list(built.get("blocked_reasons") or ["request_not_usable"])
            ),
        )

    if dry_run:
        return LiveCollectionResult(
            permitted=True,
            dispatched=False,
            http_status=None,
            search_body=search_body,
            metrics={},
            canonical_metrics={},
            payload_sha256=None,
            attempt_id=None,
            refusal=None,
        )

    request = built["transport_request"]
    request.headers["content-type"] = "application/json"
    try:
        transport = build_live_transport(
            authorized_source_id=source_id,
            authorized_url=SEARCH2_URL,
            warrant_kind=WARRANT_SOURCE_COLLECTION,
            connection=connection,
            organization_id=organization_id,
            method="POST",
            timeout_seconds=TIMEOUT_SECONDS,
        )
    except LiveTransportRefused as refused:
        return LiveCollectionResult(
            permitted=True,
            dispatched=False,
            http_status=None,
            search_body=search_body,
            metrics={},
            canonical_metrics={},
            payload_sha256=None,
            attempt_id=None,
            refusal=CollectionRefusal(reasons=list(refused.reasons)),
        )

    dispatched = execute_request(
        request=request,
        transport_kind=LIVE,
        transport=transport,
        policy={
            "execution_allowed": True,
            "live_transport_allowed": True,
            "hermetic_transport_allowed": False,
            "authorized_source_id": source_id,
        },
    )
    if not dispatched.get("dispatched"):
        return LiveCollectionResult(
            permitted=True,
            dispatched=False,
            http_status=dispatched.get("status_code"),
            search_body=search_body,
            metrics={},
            canonical_metrics={},
            payload_sha256=None,
            attempt_id=None,
            refusal=CollectionRefusal(
                reasons=list(dispatched.get("blocked_reasons") or ["transport_blocked"])
            ),
        )

    body = dispatched.get("body_bytes")
    if isinstance(body, str):
        body = body.encode("utf-8")
    body = body or b""
    now = dt.datetime.now(dt.UTC)
    persisted = persist_raw_payload(
        connection=connection,
        organization_id=organization_id,
        job_id=job_id,
        source_id=source_id,
        attempt_number=attempt_number,
        body=body,
        response_headers=dispatched.get("response_headers") or {},
        response_status=dispatched.get("status_code"),
        source_url=SEARCH2_URL,
        received_at=now,
        fact_status="tenant_supplied",
        live_fetch_performed=True,
        collector_invoked=True,
        authorized_source_id=source_id,
    )
    if not persisted.get("persisted"):
        return LiveCollectionResult(
            permitted=True,
            dispatched=True,
            http_status=dispatched.get("status_code"),
            search_body=search_body,
            metrics={},
            canonical_metrics={},
            payload_sha256=persisted.get("payload_sha256"),
            attempt_id=persisted.get("attempt_id"),
            refusal=CollectionRefusal(
                reasons=list(persisted.get("blocked_reasons") or ["payload_not_persisted"])
            ),
        )

    org = session.get(Organization, organization_id)
    if org is None:
        return _refuse("organization_not_found")

    ingest = ingest_grants_gov_search2_payload(
        connection,
        session,
        organization_id=organization_id,
        org=org,
        org_type=org_type,
        source_id=source_id,
        body_bytes=body,
        payload_sha256=str(persisted.get("payload_sha256") or ""),
        attempt_id=str(persisted.get("attempt_id") or "") or None,
        now=now,
    )
    stamp_active_source_success(
        session,
        organization_id=organization_id,
        source_id=source_id,
        at=now,
    )
    metrics = rollup_collection_metrics(ingest)
    return LiveCollectionResult(
        permitted=True,
        dispatched=True,
        http_status=dispatched.get("status_code"),
        search_body=search_body,
        metrics=metrics,
        canonical_metrics=ingest.canonical,
        payload_sha256=str(persisted.get("payload_sha256") or ""),
        attempt_id=str(persisted.get("attempt_id") or "") or None,
        refusal=None,
    )
