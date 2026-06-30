"""Audit attachment-only recognition recoverability (Path B gate)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.grant_eligibility_conditions_service import (
    enrich_grant_with_eligibility_metadata,
)
from nativeforge.services.grants_gov_eligibility_completeness_service import (
    enrich_grant_with_grants_gov_completeness,
)
from nativeforge.services.grants_gov_eligibility_parser_service import (
    parse_grants_gov_opportunity_eligibility,
)
from nativeforge.services.grants_gov_search_api_adapter_service import (
    fetch_grants_gov_opportunity_detail,
)
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_eligibility_rules
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_mixed_tier13_corpus,
)

SCHEMA_VERSION = "nf_grants_gov_attachment_recoverable_reaudit_v1"
ATTACHMENT_ONLY_THRESHOLD = 5


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _is_attachment_only_recoverable(
    grant: dict[str, Any],
    *,
    detail: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any] | None:
    """Grant is unknown, has PDF attachment, and synopsis+forecast parse still unknown."""
    if grant.get("tier") == 3:
        return None
    before = enrich_grant_with_eligibility_metadata(grant, rules=rules)
    if before["recognition_requirement"] != "unknown":
        return None

    parsed = parse_grants_gov_opportunity_eligibility(detail)
    inv = parsed.get("grants_gov_attachment_inventory") or {}
    if inv.get("pdf_count", 0) < 1:
        return None

    syn_only = enrich_grant_with_eligibility_metadata(
        enrich_grant_with_grants_gov_completeness(grant, detail=detail),
        rules=rules,
    )
    if syn_only["recognition_requirement"] != "unknown":
        return None

    hay = " ".join(
        str(grant.get(k) or "")
        for k in ("opportunity_title", "agency")
    ).lower()
    tribal_signal = any(
        tok in hay for tok in ("tribal", "indian", "native", "ihs", "bia", "ana")
    )
    if not tribal_signal and not parsed.get("tribal_eligible"):
        return None

    return _json_safe(
        {
            "grant_id": grant.get("grant_id"),
            "grants_gov_opportunity_id": grant.get("grants_gov_opportunity_id"),
            "attachment_count": inv.get("attachment_count"),
            "pdf_count": inv.get("pdf_count"),
            "pdf_files": [a.get("file_name") for a in inv.get("attachments") or [] if "pdf" in str(a.get("mime_type", "")).lower()],
        }
    )


def run_attachment_recoverable_reaudit(
    *,
    grants: list[dict[str, Any]] | None = None,
    allow_live_fetch: bool = True,
) -> dict[str, Any]:
    rules = load_sc_eligibility_rules(require_files=False)
    corpus = grants if grants is not None else load_mixed_tier13_corpus()
    candidates: list[dict[str, Any]] = []
    skipped_no_gg_id = 0
    skipped_no_pdf = 0

    for grant in corpus:
        if grant.get("tier") == 3:
            continue
        opp_id = grant.get("grants_gov_opportunity_id")
        if not opp_id:
            skipped_no_gg_id += 1
            continue
        if not allow_live_fetch:
            inv = grant.get("grants_gov_attachment_inventory") or {}
            if inv.get("pdf_count", 0) < 1:
                skipped_no_pdf += 1
            continue
        detail, live = fetch_grants_gov_opportunity_detail(opp_id)
        if not live:
            continue
        hit = _is_attachment_only_recoverable(grant, detail=detail, rules=rules)
        if hit:
            candidates.append(hit)
        else:
            inv = parse_grants_gov_opportunity_eligibility(detail).get(
                "grants_gov_attachment_inventory"
            ) or {}
            if inv.get("pdf_count", 0) >= 1:
                skipped_no_pdf += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "attachment_only_recoverable_count": len(candidates),
            "threshold": ATTACHMENT_ONLY_THRESHOLD,
            "path_b_approved": len(candidates) >= ATTACHMENT_ONLY_THRESHOLD,
            "candidates": candidates,
            "skipped_no_gg_id": skipped_no_gg_id,
        }
    )
