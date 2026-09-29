"""Warrant-backed Grants.gov Search2 collection through corpus ingest."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa

from nativeforge.db.models import Organization
from nativeforge.db.rls import reapply_org_rls_after_commit
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.source_collection_raw_payload_repository import (
    BLOCK_DIFFERENT_BYTES,
    get_payload,
)
from nativeforge.services.grants_gov_corpus_ingest_service import (
    _canonical_batch_metrics,
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
from nativeforge.services.source_live_collection_policy_service import (
    assert_bounded_collection_permitted,
)
from nativeforge.services.source_live_warrant_service import WARRANT_SOURCE_COLLECTION
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
    refusal = assert_bounded_collection_permitted(
        connection,
        organization_id=organization_id,
        source_id=source_id,
        request_url=SEARCH2_URL,
        method="POST",
    )
    if refusal is None:
        return None
    return CollectionRefusal(reasons=list(refusal.reasons))


def stamp_active_source_success(
    session: Any,
    *,
    organization_id: uuid.UUID,
    source_id: str,
    at: dt.datetime,
) -> bool:
    updated = session.execute(
        sa.text(
            """
            UPDATE nf_active_opportunity_sources
            SET last_checked_at = :at,
                last_success_at = :at,
                consecutive_failure_count = 0,
                updated_at = :at
            WHERE organization_id = :org
              AND source_id = :source_id
            """
        ),
        {"at": at, "org": organization_id, "source_id": source_id},
    )
    session.flush()
    return int(updated.rowcount or 0) > 0


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
    reapply_org_rls_after_commit(session, organization_id, org_type)
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
    ingest_body = body
    payload_meta = persisted
    upstream_offer_sha256 = None
    if not (persisted.get("persisted") or persisted.get("deduplicated")):
        blocked = list(persisted.get("blocked_reasons") or [])
        if any(BLOCK_DIFFERENT_BYTES in str(reason) for reason in blocked):
            upstream_offer_sha256 = hashlib.sha256(body).hexdigest()
            stored = get_payload(
                connection=connection,
                organization_id=organization_id,
                attempt_id=persisted.get("attempt_id"),
                include_body=True,
            )
            if stored.get("body_bytes") and stored.get("hash_verified"):
                ingest_body = stored["body_bytes"]
                payload_meta = {
                    **persisted,
                    "payload_sha256": stored.get("readback_sha256")
                    or (stored.get("payload") or {}).get("payload_sha256"),
                    "using_stored_raw_after_upstream_change": True,
                    "upstream_offer_sha256": upstream_offer_sha256,
                }
            else:
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
                        reasons=blocked or ["payload_not_persisted"]
                    ),
                )
        else:
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
                    reasons=blocked or ["payload_not_persisted"]
                ),
            )

    # Durable raw evidence must survive canonical batch rollbacks.
    if persisted.get("persisted"):
        session.commit()
        reapply_org_rls_after_commit(session, organization_id, org_type)

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
        body_bytes=ingest_body,
        payload_sha256=str(payload_meta.get("payload_sha256") or ""),
        attempt_id=str(payload_meta.get("attempt_id") or "") or None,
        now=now,
    )
    if int(_canonical_batch_metrics(ingest.canonical).get("batch_failures") or 0) > 0:
        return LiveCollectionResult(
            permitted=True,
            dispatched=True,
            http_status=dispatched.get("status_code"),
            search_body=search_body,
            metrics=rollup_collection_metrics(ingest),
            canonical_metrics=ingest.canonical,
            payload_sha256=str(payload_meta.get("payload_sha256") or ""),
            attempt_id=str(payload_meta.get("attempt_id") or "") or None,
            refusal=CollectionRefusal(
                reasons=["canonical_batch_failed_after_raw_payload_persisted"]
            ),
        )
    stamp_active_source_success(
        session,
        organization_id=organization_id,
        source_id=source_id,
        at=now,
    )
    metrics = rollup_collection_metrics(ingest)
    if upstream_offer_sha256:
        metrics = {
            **metrics,
            "upstream_offer_sha256": upstream_offer_sha256,
            "ingested_stored_raw_after_upstream_change": True,
        }
    return LiveCollectionResult(
        permitted=True,
        dispatched=True,
        http_status=dispatched.get("status_code"),
        search_body=search_body,
        metrics=metrics,
        canonical_metrics=ingest.canonical,
        payload_sha256=str(payload_meta.get("payload_sha256") or ""),
        attempt_id=str(payload_meta.get("attempt_id") or "") or None,
        refusal=None,
    )
