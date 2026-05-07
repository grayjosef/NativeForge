"""Normalize offline payloads into discovery-intake-shaped candidates."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from nativeforge.domain.enums import GrantAwardType, OpportunitySourceType
from nativeforge.services.opportunity_discovery_service import compute_duplicate_key
from nativeforge.services.source_connectors.base import (
    ConnectorRunContext,
    ConnectorSourceConfig,
    NormalizedOpportunityCandidate,
)
from nativeforge.services.source_connectors.native_relevance import (
    NativeRelevanceInput,
    assess_native_relevance,
)


def _str_nonempty(raw: dict[str, Any], key: str) -> str | None:
    v = raw.get(key)
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _coerce_bool(val: Any, default: bool | None = None) -> bool | None:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        lower = val.strip().lower()
        if lower in ("true", "1", "yes", "y"):
            return True
        if lower in ("false", "0", "no", "n"):
            return False
    return default


def build_native_relevance_input(raw: dict[str, Any]) -> NativeRelevanceInput:
    """Derive scoring inputs from a raw fixture / payload dict."""
    title = _str_nonempty(raw, "opportunity_title") or ""
    desc = _str_nonempty(raw, "description")
    nofo = _str_nonempty(raw, "raw_nofo_text")
    body_text = nofo if nofo is not None else desc

    tags = raw.get("eligibility_tags")
    tag_list: list[str] | None
    if isinstance(tags, list):
        tag_list = [str(x) for x in tags]
    else:
        tag_list = None

    trust = raw.get("source_trust_tier")
    st: str = "medium"
    if trust in ("low", "medium", "high"):
        st = str(trust)

    return NativeRelevanceInput(
        opportunity_title=title,
        raw_nofo_text=body_text,
        tribal_eligible=bool(raw.get("tribal_eligible", False)),
        tribal_set_aside=bool(raw.get("tribal_set_aside", False)),
        tribal_priority_points=bool(raw.get("tribal_priority_points", False)),
        eligibility_tags=tag_list,
        applicant_types_include_tribal=_coerce_bool(
            raw.get("applicant_types_include_tribal")
        ),
        source_trust_tier=st,  # type: ignore[arg-type]
    )


def _parse_ost(raw: dict[str, Any], hint: str | None) -> OpportunitySourceType:
    v = raw.get("opportunity_source_type") or hint or "federal"
    try:
        return OpportunitySourceType(str(v))
    except ValueError:
        return OpportunitySourceType.federal


def _parse_award(raw: dict[str, Any]) -> GrantAwardType:
    v = raw.get("award_type") or "grant"
    try:
        return GrantAwardType(str(v))
    except ValueError:
        return GrantAwardType.grant


def build_normalized_fields(
    raw: dict[str, Any],
    *,
    config: ConnectorSourceConfig,
) -> dict[str, Any]:
    """Shape fields for Sprint 12 structured intake."""
    agency = _str_nonempty(raw, "agency") or _str_nonempty(raw, "publisher_name")
    publisher = _str_nonempty(raw, "publisher_name") or agency
    ost = _parse_ost(raw, config.opportunity_source_type_hint)
    award = _parse_award(raw)
    title = _str_nonempty(raw, "opportunity_title")
    if not title:
        raise ValueError("missing_or_empty_opportunity_title")

    fields: dict[str, Any] = {
        "opportunity_title": title,
        "agency": agency or publisher or "Unknown publisher",
        "publisher_name": publisher or agency or "Unknown publisher",
        "award_type": award.value,
        "opportunity_source_type": ost.value,
        "opportunity_number": _str_nonempty(raw, "opportunity_number"),
        "url": _str_nonempty(raw, "url"),
        "source_url": _str_nonempty(raw, "source_url"),
        "raw_nofo_text": _str_nonempty(raw, "raw_nofo_text")
        or _str_nonempty(raw, "description"),
        "tribal_eligible": bool(raw.get("tribal_eligible", False)),
        "eligibility_tags": raw.get("eligibility_tags")
        if isinstance(raw.get("eligibility_tags"), list)
        else None,
        "tribal_set_aside": bool(raw.get("tribal_set_aside", False)),
        "tribal_priority_points": bool(raw.get("tribal_priority_points", False)),
    }
    if raw.get("application_deadline") is not None:
        fields["application_deadline"] = raw.get("application_deadline")
    cfda = _str_nonempty(raw, "cfda_assistance_listing")
    if cfda is not None:
        fields["cfda_assistance_listing"] = cfda
    if raw.get("posted_date") is not None:
        fields["posted_date"] = raw.get("posted_date")
    if raw.get("award_ceiling") is not None:
        fields["award_ceiling"] = raw.get("award_ceiling")
    if raw.get("award_floor") is not None:
        fields["award_floor"] = raw.get("award_floor")
    if _str_nonempty(raw, "program_category") is not None:
        fields["program_category"] = _str_nonempty(raw, "program_category")
    return fields


def normalize_raw_dict(
    raw: dict[str, Any],
    *,
    local_key: str,
    config: ConnectorSourceConfig,
    ctx: ConnectorRunContext,
    extra_provenance: dict[str, Any] | None = None,
) -> NormalizedOpportunityCandidate:
    """Map one raw dict into a deduped, scored `NormalizedOpportunityCandidate`."""
    norm_fields = build_normalized_fields(raw, config=config)
    ost_enum = OpportunitySourceType(str(norm_fields["opportunity_source_type"]))
    nr_in = build_native_relevance_input(raw)
    nr_out = assess_native_relevance(nr_in)

    dup_key = compute_duplicate_key(
        source_url=norm_fields.get("source_url") or norm_fields.get("url"),
        publisher_name=norm_fields.get("publisher_name"),
        opportunity_number=norm_fields.get("opportunity_number"),
        opportunity_title=norm_fields.get("opportunity_title"),
        opportunity_source_type=ost_enum,
    )

    now = ctx.now or datetime.now(UTC)
    prov = {
        "connector_id": config.connector_id,
        "normalization_schema_version": ctx.normalization_schema_version,
        "dry_run": ctx.dry_run,
        "captured_at": now.isoformat(),
        "source_lane": config.source_lane,
        "local_key": local_key,
    }
    if config.source_registry_id is not None:
        prov["source_registry_id"] = str(config.source_registry_id)
    if ctx.run_id:
        prov["connector_run_id"] = ctx.run_id
    if extra_provenance:
        prov.update(extra_provenance)
    for meta_key in ("fixture_category", "fixture_key", "corpus_schema_version"):
        mv = raw.get(meta_key)
        if mv is not None:
            prov[str(meta_key)] = mv

    return NormalizedOpportunityCandidate(
        local_key=local_key,
        duplicate_key=dup_key,
        normalized_fields=norm_fields,
        native_relevance=nr_out,
        provenance=prov,
    )


def to_discovery_intake_candidate_payload(
    normalized: NormalizedOpportunityCandidate,
) -> dict[str, Any]:
    """
    Prepare a dict suitable for `process_structured_candidates` candidate rows.

    Extra keys are preserved in `raw_candidate_json` and do not break intake.
    """
    payload = dict(normalized.normalized_fields)
    payload["connector_native_relevance_v1"] = normalized.native_relevance
    payload["connector_provenance_v1"] = normalized.provenance
    payload["connector_duplicate_key_v1"] = normalized.duplicate_key
    return payload
