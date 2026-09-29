"""Classify the source seed into an adapter-family backlog.

The seed is candidate inventory. A row is not a collector, and a resolver
label of "healthy" is not verification. Counts come from the loaded CSV.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from nativeforge.services.source_ingestion_seed_loader_service import (
    load_source_seed_rows,
)

SCHEMA_VERSION = "nf_source_seed_backlog_v1"

BACKLOG_CLASSES: tuple[str, ...] = (
    "VERIFIED",
    "DUPLICATE",
    "STALE",
    "INVALID",
    "NEEDS_RESEARCH",
    "ADAPTER_SUPPORTED",
    "NEW_ADAPTER_REQUIRED",
    "AUTHORIZATION_REQUIRED",
)

# adapter_key -> (backlog class, family). Families name code that exists
# or a scaffold that does not. state_portal_generic is not the tribal-affairs
# HTML adapter; those rows stay research.
ADAPTER_CLASS: dict[str, tuple[str, str]] = {
    "grants_gov_search2": ("ADAPTER_SUPPORTED", "structured_federal_api"),
    "grants_gov_federal": ("ADAPTER_SUPPORTED", "structured_federal_api"),
    "foundation_org_page": ("ADAPTER_SUPPORTED", "html_listing"),
    "state_portal_generic": ("NEEDS_RESEARCH", "html_listing_unconfirmed"),
    "bia_program_page_html": ("NEW_ADAPTER_REQUIRED", "html_detail_scaffold"),
    "federal_register_documents_json": (
        "ADAPTER_SUPPORTED",
        "structured_federal_api",
    ),
}

LOGIN_BUCKETS = frozenset({"blocked_login_portal", "members_gated", "login_gated"})
LOGIN_ACCESS = frozenset({"login", "members"})


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _url_key(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/").lower()
    return f"{host}{path}"


def classify_seed_row(
    row: dict[str, str],
    *,
    seen_ids: set[str],
    seen_urls: set[str],
) -> dict[str, Any]:
    seed_id = str(row.get("seed_id") or "").strip()
    canonical = str(row.get("canonical_source_id") or "").strip()
    url = str(row.get("source_url") or "").strip()
    adapter = str(row.get("adapter_key") or "").strip()
    url_key = _url_key(url) if url else ""

    if (canonical and canonical in seen_ids) or (url_key and url_key in seen_urls):
        backlog_class = "DUPLICATE"
        family = "duplicate"
    elif (
        str(row.get("resolver_url_status") or "") == "dead"
        or str(row.get("catalog_accounting_bucket") or "") == "dead_url"
        or not url.startswith(("http://", "https://"))
    ):
        backlog_class = "INVALID"
        family = "invalid"
    elif (
        str(row.get("access_posture_hint") or "") in LOGIN_ACCESS
        or str(row.get("catalog_accounting_bucket") or "") in LOGIN_BUCKETS
    ):
        backlog_class = "AUTHORIZATION_REQUIRED"
        family = ADAPTER_CLASS.get(adapter, ("AUTHORIZATION_REQUIRED", "unknown"))[1]
    else:
        backlog_class, family = ADAPTER_CLASS.get(
            adapter, ("NEEDS_RESEARCH", "unknown")
        )

    if canonical:
        seen_ids.add(canonical)
    if url_key:
        seen_urls.add(url_key)

    return {
        "seed_id": seed_id,
        "source_name": str(row.get("source_name") or ""),
        "adapter_key": adapter,
        "adapter_family": family,
        "backlog_class": backlog_class,
        "verified": False,
        "enabled": False,
    }


def classify_source_seed(
    rows: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    loaded = list(rows) if rows is not None else load_source_seed_rows()
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    classified = [
        classify_seed_row(row, seen_ids=seen_ids, seen_urls=seen_urls) for row in loaded
    ]
    by_class = Counter(item["backlog_class"] for item in classified)
    by_family = Counter(item["adapter_family"] for item in classified)
    for name in BACKLOG_CLASSES:
        by_class.setdefault(name, 0)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "candidate_count": len(classified),
            "verified": by_class["VERIFIED"],
            "duplicate": by_class["DUPLICATE"],
            "stale": by_class["STALE"],
            "invalid": by_class["INVALID"],
            "needs_research": by_class["NEEDS_RESEARCH"],
            "adapter_supported": by_class["ADAPTER_SUPPORTED"],
            "new_adapter_required": by_class["NEW_ADAPTER_REQUIRED"],
            "authorization_required": by_class["AUTHORIZATION_REQUIRED"],
            "by_class": dict(sorted(by_class.items())),
            "by_family": dict(sorted(by_family.items())),
            "rows": classified,
            "fabricated": False,
        }
    )
