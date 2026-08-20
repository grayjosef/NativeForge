"""Build honest NOFO/synopsis intelligence packs for selected SC Monday opportunities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.nofo_showcase_field_status_service import (
    STATUS_INFERRED,
    STATUS_KNOWN,
    STATUS_MISSING,
    STATUS_NEEDS_CONFIRMATION,
    STATUS_NOT_IN_SOURCE,
    STATUS_NOT_SUPPORTED,
    assert_no_silent_fill,
    make_field,
)
from nativeforge.services.sc_monday_curated_pack_service import (
    grants_from_pack,
    load_sc_curated_opportunity_pack,
)

SCHEMA_VERSION = "nf_nofo_showcase_intelligence_pack_v1"
CAPTURE_DATE = "2026-08-20"

SHOWCASE_OPPORTUNITY_IDS: tuple[str, ...] = (
    "sc-rule-SC_FOOD_SOVEREIGNTY",
    "nf13-real-fed-012",
    "la-real-006",
)

_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "nofo_showcase"
PACK_PATH = _FIXTURES_DIR / "selected_opportunity_intelligence_pack.json"


class NofoShowcasePackError(ValueError):
    """Invalid showcase intelligence pack."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _grant_by_id() -> dict[str, dict[str, Any]]:
    return {
        str(g.get("opportunity_id") or g.get("grant_id")): g for g in grants_from_pack()
    }


def _field_from_value(
    value: Any,
    *,
    known_status: str = STATUS_KNOWN,
    evidence: str = "",
    source_ref: str = "",
    missing_status: str = STATUS_MISSING,
) -> dict[str, Any]:
    if value is None or value == "" or value == []:
        return make_field(value=None, status=missing_status, evidence_note=evidence)
    return make_field(
        value=value,
        status=known_status,
        evidence_note=evidence,
        source_ref=source_ref,
    )


def build_opportunity_intelligence(grant: dict[str, Any]) -> dict[str, Any]:
    """Derive synopsis/curated intelligence with honest field statuses."""
    oid = str(grant.get("opportunity_id") or grant.get("grant_id"))
    source_layer = str(grant.get("source_layer") or "unknown")
    source_ref = str(grant.get("source_url") or grant.get("source_reference") or "")
    evidence = str(
        grant.get("source_evidence_note") or grant.get("evidence_notes") or ""
    )

    fields: dict[str, dict[str, Any]] = {
        "title": _field_from_value(
            grant.get("title") or grant.get("opportunity_title"),
            evidence=evidence or "curated opportunity pack",
            source_ref=source_ref,
        ),
        "agency_or_source": _field_from_value(
            grant.get("source_name") or grant.get("agency"),
            evidence=evidence or "curated pack / corpus",
            source_ref=source_ref,
        ),
        "purpose": _field_from_value(
            grant.get("synopsis") or grant.get("eligibility_summary"),
            known_status=STATUS_INFERRED
            if grant.get("synopsis")
            else STATUS_NEEDS_CONFIRMATION,
            evidence=(
                evidence
                or "synopsis or eligibility text from curated pack; confirm against official notice"
            ),
            source_ref=source_ref,
            missing_status=STATUS_NEEDS_CONFIRMATION,
        ),
        "eligibility": _field_from_value(
            grant.get("eligibility_summary")
            or grant.get("eligibility_text")
            or grant.get("recognition_requirement"),
            evidence=evidence or "curated eligibility / recognition requirement",
            source_ref=source_ref,
            missing_status=STATUS_NEEDS_CONFIRMATION,
        ),
        "tribal_native_relevance": _field_from_value(
            grant.get("native_tribal_eligibility_evidence")
            or grant.get("sc_relevance_explanation")
            or grant.get("federal_relevance_explanation"),
            evidence=evidence or "curated Native/tribal relevance notes",
            source_ref=source_ref,
        ),
        "geography": _field_from_value(
            grant.get("funding_geography") or source_layer,
            evidence=evidence or "funding_geography on curated pack",
        ),
        "deadline": _field_from_value(
            grant.get("deadline_date") or grant.get("application_deadline"),
            known_status=STATUS_NEEDS_CONFIRMATION,
            evidence=evidence or "curated deadline — confirm active round",
            source_ref=source_ref,
            missing_status=STATUS_MISSING,
        ),
        "award_range": _field_from_value(
            None,
            missing_status=STATUS_NOT_IN_SOURCE,
            evidence="award floor/ceiling not present in curated pack",
        ),
        "match_cost_share": _field_from_value(
            None,
            missing_status=STATUS_NOT_IN_SOURCE,
            evidence="match/cost-share not present in curated pack",
        ),
        "required_forms": _field_from_value(
            None,
            missing_status=STATUS_NOT_IN_SOURCE,
            evidence="forms list not in curated synopsis/pack",
        ),
        "required_attachments": _field_from_value(
            None,
            missing_status=STATUS_NOT_IN_SOURCE,
            evidence="attachments list not in curated synopsis/pack",
        ),
        "required_narratives": _field_from_value(
            ["Project narrative", "Evaluation plan"],
            known_status=STATUS_INFERRED,
            evidence=(
                "Typical federal/state application sections inferred for planning only — "
                "not extracted from a live NOFO PDF"
            ),
        ),
        "reporting_burdens": _field_from_value(
            None,
            missing_status=STATUS_NOT_IN_SOURCE,
            evidence="reporting obligations not in curated pack",
        ),
        "evaluation_criteria": _field_from_value(
            None,
            missing_status=STATUS_NOT_IN_SOURCE,
            evidence="evaluation criteria not in curated pack",
        ),
        "proposal_narrative": make_field(
            value=None,
            status=STATUS_NOT_SUPPORTED,
            evidence_note="Proposal drafting not supported in this block",
        ),
        "pdf_nofo_full_text": make_field(
            value=None,
            status=STATUS_NOT_SUPPORTED,
            evidence_note="Full NOFO PDF extraction not supported in this block",
        ),
        "tribal_resolution_text": make_field(
            value=None,
            status=STATUS_NOT_SUPPORTED,
            evidence_note="Do not fabricate tribal resolutions",
        ),
    }

    silent = assert_no_silent_fill(fields)
    if silent:
        raise NofoShowcasePackError(
            f"silent fill invariants failed for {oid}: {silent}"
        )

    unresolved = [
        name
        for name, f in fields.items()
        if f["status"]
        in {
            STATUS_MISSING,
            STATUS_NEEDS_CONFIRMATION,
            STATUS_NOT_IN_SOURCE,
            STATUS_NOT_SUPPORTED,
        }
    ]
    next_checks = [
        "Confirm active funding round and official notice text",
        "Human review of eligibility evidence before pursuit decision",
    ]
    if fields["deadline"]["status"] in {STATUS_MISSING, STATUS_NEEDS_CONFIRMATION}:
        next_checks.append("Confirm deadline with official source")
    if fields["required_forms"]["status"] == STATUS_NOT_IN_SOURCE:
        next_checks.append(
            "Locate official forms list from NOFO/synopsis PDF when available"
        )

    return _json_safe(
        {
            "opportunity_id": oid,
            "source_layer": source_layer,
            "source_name": grant.get("source_name") or grant.get("agency"),
            "source_reference": source_ref,
            "captured_at": grant.get("captured_at") or CAPTURE_DATE,
            "retrieved_at": grant.get("retrieved_at") or CAPTURE_DATE,
            "data_mode": grant.get("data_mode") or "curated_current",
            "live_ingest_claimed": False,
            "nofo_document_availability": "not_supported_pdf_extraction",
            "synopsis_availability": "partial_from_curated_pack",
            "extraction_method": "deterministic_curated_synopsis_mapper_v1",
            "extraction_confidence": "low_public_inferred",
            "human_review_required": True,
            "operator_next_check": next_checks,
            "unresolved_fields": unresolved,
            "fields": fields,
            "sc_relevance_explanation": grant.get("sc_relevance_explanation"),
            "federal_relevance_explanation": grant.get("federal_relevance_explanation"),
            "demo_real_isolation_label": grant.get("demo_real_isolation_label"),
        }
    )


def build_selected_intelligence_pack(
    *,
    opportunity_ids: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    ids = tuple(opportunity_ids or SHOWCASE_OPPORTUNITY_IDS)
    by_id = _grant_by_id()
    records: list[dict[str, Any]] = []
    missing_ids: list[str] = []
    for oid in ids:
        g = by_id.get(oid)
        if not g:
            missing_ids.append(oid)
            continue
        records.append(build_opportunity_intelligence(g))
    if missing_ids:
        raise NofoShowcasePackError(
            f"showcase opportunity ids missing from curated pack: {missing_ids}"
        )
    sc = [r for r in records if r.get("source_layer") == "sc_state"]
    fed = [r for r in records if r.get("source_layer") == "federal"]
    if len(sc) < 1 or len(fed) < 1:
        raise NofoShowcasePackError(
            "showcase pack must include at least one SC and one federal opportunity"
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "pack_id": "nofo_showcase_selected_20260820",
            "title": "NOFO Showcase — Selected Opportunity Intelligence",
            "capture_date": CAPTURE_DATE,
            "live_ingest_claimed": False,
            "nofo_pdf_extraction_claimed": False,
            "proposal_drafting_claimed": False,
            "parent_curated_pack_id": load_sc_curated_opportunity_pack().get("pack_id"),
            "counts": {
                "total": len(records),
                "sc_state": len(sc),
                "federal": len(fed),
            },
            "opportunities": records,
        }
    )


def pack_invariant_failures(pack: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if pack.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    if pack.get("nofo_pdf_extraction_claimed") is True:
        fails.append("nofo_pdf_claimed")
    if pack.get("proposal_drafting_claimed") is True:
        fails.append("proposal_claimed")
    opps = pack.get("opportunities") or []
    if len(opps) < 2:
        fails.append("too_few_opportunities")
    sc = sum(1 for o in opps if o.get("source_layer") == "sc_state")
    fed = sum(1 for o in opps if o.get("source_layer") == "federal")
    if sc < 1:
        fails.append("missing_sc")
    if fed < 1:
        fails.append("missing_federal")
    for o in opps:
        if not o.get("human_review_required"):
            fails.append(f"human_review_false:{o.get('opportunity_id')}")
        silent = assert_no_silent_fill(o.get("fields") or {})
        fails.extend(silent)
        if "proposal_narrative" in (o.get("fields") or {}):
            if o["fields"]["proposal_narrative"]["status"] != STATUS_NOT_SUPPORTED:
                fails.append("proposal_not_marked_unsupported")
        if "pdf_nofo_full_text" in (o.get("fields") or {}):
            if o["fields"]["pdf_nofo_full_text"]["status"] != STATUS_NOT_SUPPORTED:
                fails.append("pdf_not_marked_unsupported")
    return fails


def write_selected_intelligence_pack(
    pack: dict[str, Any] | None = None,
    *,
    path: Path | None = None,
) -> Path:
    doc = pack if pack is not None else build_selected_intelligence_pack()
    fails = pack_invariant_failures(doc)
    if fails:
        raise NofoShowcasePackError(f"pack invariants failed: {fails}")
    out = path or PACK_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Also write layer-split convenience packs
    sc = {
        **doc,
        "pack_id": f"{doc['pack_id']}_sc",
        "opportunities": [
            o for o in doc["opportunities"] if o["source_layer"] == "sc_state"
        ],
    }
    fed = {
        **doc,
        "pack_id": f"{doc['pack_id']}_federal",
        "opportunities": [
            o for o in doc["opportunities"] if o["source_layer"] == "federal"
        ],
    }
    sc["counts"] = {
        "total": len(sc["opportunities"]),
        "sc_state": len(sc["opportunities"]),
        "federal": 0,
    }
    fed["counts"] = {
        "total": len(fed["opportunities"]),
        "sc_state": 0,
        "federal": len(fed["opportunities"]),
    }
    (_FIXTURES_DIR / "sc_selected_opportunity_intelligence_pack.json").write_text(
        json.dumps(sc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (_FIXTURES_DIR / "federal_selected_opportunity_intelligence_pack.json").write_text(
        json.dumps(fed, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return out


def load_selected_intelligence_pack(*, require_file: bool = True) -> dict[str, Any]:
    if not PACK_PATH.is_file():
        if require_file:
            raise NofoShowcasePackError(f"missing pack: {PACK_PATH}")
        return build_selected_intelligence_pack()
    return json.loads(PACK_PATH.read_text(encoding="utf-8"))
