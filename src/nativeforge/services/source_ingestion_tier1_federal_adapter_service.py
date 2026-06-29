"""Sprint 261-262: Tier-1 federal adapter (Grants.gov / Simpler / GrantSolutions)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.source_connectors.grants_gov_shaped import (
    grants_gov_like_to_fixture_row,
)

SCHEMA_VERSION = "nf_source_ingestion_tier1_federal_adapter_v1"

TIER1_ADAPTER_KEYS: frozenset[str] = frozenset(
    {
        "grants_gov_federal",
        "simpler_grants_gov",
        "grant_solutions",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_canonical_opportunity_id(raw: dict[str, Any]) -> str:
    """Stable id for idempotent upsert (Grants.gov id preferred when present)."""
    gg_id = raw.get("grants_gov_opportunity_id")
    if gg_id is not None and str(gg_id).strip():
        return f"grants_gov:{gg_id}"
    explicit = raw.get("canonical_opportunity_id") or raw.get("opportunity_number")
    if explicit:
        return str(explicit).strip()
    title = str(raw.get("opportunity_title") or raw.get("title") or "")
    agency = str(raw.get("agency") or raw.get("agencyName") or "")
    digest = hashlib.sha256(f"{agency}|{title}".encode()).hexdigest()[:16]
    return f"nf:opp:{digest}"


def parse_tier1_federal_opportunity(
    raw: dict[str, Any],
    *,
    adapter_key: str,
) -> dict[str, Any]:
    if adapter_key not in TIER1_ADAPTER_KEYS:
        raise ValueError(f"not a tier-1 adapter: {adapter_key!r}")
    row = grants_gov_like_to_fixture_row(raw)
    canonical_id = build_canonical_opportunity_id(raw)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "adapter_key": adapter_key,
            "canonical_opportunity_id": canonical_id,
            "normalized_row": row,
            "fixture_key": row.get("fixture_key"),
            "opportunity_title": row.get("opportunity_title"),
            "source_url": row.get("source_url"),
            "preview_only": False,
            "requires_operator_activation": True,
        }
    )


def upsert_tier1_opportunities(
    payloads: list[dict[str, Any]],
    *,
    existing_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Idempotent upsert by canonical_opportunity_id."""
    seen = set(existing_ids or ())
    inserted: list[str] = []
    updated: list[str] = []
    for raw in payloads:
        adapter = str(raw.get("adapter_key") or "grants_gov_federal")
        parsed = parse_tier1_federal_opportunity(raw, adapter_key=adapter)
        cid = parsed["canonical_opportunity_id"]
        if cid in seen:
            updated.append(cid)
        else:
            inserted.append(cid)
            seen.add(cid)
    return _json_safe(
        {
            "schema_version": "nf_source_ingestion_tier1_upsert_v1",
            "inserted_count": len(inserted),
            "updated_count": len(updated),
            "inserted_ids": inserted,
            "updated_ids": updated,
            "idempotent": True,
        }
    )
