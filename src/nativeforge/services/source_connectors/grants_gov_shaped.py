"""Maps Grants.gov-like dicts to connector rows (offline, no network)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from nativeforge.domain.enums import (
    FundingInstrument,
    GrantAwardType,
    OpportunitySourceType,
)
from nativeforge.services.source_connectors.base import (
    ConnectorDryRunResult,
    ConnectorRunContext,
    ConnectorSourceConfig,
    NormalizedOpportunityCandidate,
)
from nativeforge.services.source_connectors.normalization import normalize_raw_dict

# Provenance / connector identity
GRANTS_GOV_SHAPED_CONNECTOR_KEY = "grants_gov_shaped"

# --- Grants.gov / SAM-style alias groups (first hit wins per group) ---

_TITLE_KEYS = (
    "opportunity_title",
    "title",
    "Title",
    "OpportunityTitle",
    "opportunityTitle",
)
_AGENCY_KEYS = ("agency", "agencyName", "Agency", "agency_name", "AgencyName")
_AGENCY_CODE_KEYS = ("agency_code", "agencyCode", "AgencyCode")
_NUMBER_KEYS = (
    "opportunity_number",
    "OpportunityNumber",
    "opportunityNumber",
    "OpportunityId",
    "opportunity_id",
)
_URL_KEYS = (
    "source_url",
    "OpportunityURL",
    "opportunityUrl",
    "url",
    "OpportunityUrl",
)
_CFDA_KEYS = (
    "cfda_assistance_listing",
    "CFDA",
    "cfdanumber",
    "cfdaNumber",
    "AssistanceListingNumber",
    "assistanceListingNumber",
)
_POSTED_KEYS = ("posted_date", "PostedDate", "postedDate", "createTimeStamp")
_DEADLINE_KEYS = (
    "application_deadline",
    "CloseDate",
    "closeDate",
    "SubmissionDeadline",
    "submissionDeadline",
    "ArchiveDate",
)
_SYNOPSIS_KEYS = (
    "synopsis",
    "Synopsis",
    "description",
    "Description",
    "OpportunityDescription",
    "opportunityDescription",
)
_ELIGIBILITY_TEXT_KEYS = (
    "eligibilityDesc",
    "EligibilityInformation",
    "eligibilityInformation",
    "eligibility_text",
    "eligibilityText",
    "AdditionalInformationEligibility",
)
_CATEGORY_KEYS = ("category", "Category", "FundingCategory", "fundingCategory")
_INSTRUMENT_KEYS = (
    "FundingInstrumentType",
    "funding_instrument_type",
    "instrument_type",
)
_AWARD_CEILING_KEYS = ("AwardCeiling", "award_ceiling", "awardCeiling")
_AWARD_FLOOR_KEYS = ("AwardFloor", "award_floor", "awardFloor")

_NUMBER_CLEAN_RE = re.compile(r"[^\d.+-]")


def _first_str(d: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for k in keys:
        if k not in d:
            continue
        v = d.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def _first_any(d: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _parse_optional_amount(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return None
    s = _NUMBER_CLEAN_RE.sub("", s)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _map_funding_instrument_to_award_type(raw_type: str) -> str:
    low = raw_type.lower()
    if "cooperative" in low:
        return GrantAwardType.cooperative_agreement.value
    if "formula" in low:
        return GrantAwardType.formula.value
    if "competitive" in low or "discretionary" in low:
        return GrantAwardType.competitive.value
    if "grant" in low or "g/o" in low:
        return GrantAwardType.grant.value
    return GrantAwardType.grant.value


def _map_funding_instrument_enum(raw_type: str) -> str | None:
    low = raw_type.lower()
    if "cooperative" in low:
        return FundingInstrument.cooperative_agreement.value
    if "formula" in low:
        return FundingInstrument.formula.value
    if "loan" in low:
        return FundingInstrument.loan.value
    if "prize" in low:
        return FundingInstrument.prize.value
    if "grant" in low:
        return FundingInstrument.grant.value
    return FundingInstrument.other.value


def _infer_tribal_signals_from_eligibility_body(body: str) -> tuple[bool, list[str]]:
    """
    Deterministic tribal pathways from synopsis / eligibility text only (not title).

    Narrative tags alone never imply confirmation without phrase-level structured cues.
    """
    low = body.lower()
    tags: list[str] = []
    tribal_eligible = False

    def add(tag: str) -> None:
        if tag not in tags:
            tags.append(tag)

    if (
        "federally recognized tribe" in low
        or "federally recognized tribes" in low
        or "federally recognized indian tribe" in low
    ):
        tribal_eligible = True
        add("federally_recognized_tribe")

    if "tribal government" in low or "tribal governments" in low:
        tribal_eligible = True
        add("tribal_government")

    if "alaska native" in low or "alaska native village" in low:
        tribal_eligible = True
        add("alaska_native")

    if "native hawaiian organization" in low:
        tribal_eligible = True
        add("native_hawaiian")

    if "indian tribe" in low and "non-indian" not in low:
        tribal_eligible = True

    return tribal_eligible, tags


def grants_gov_like_to_fixture_row(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Map Grants.gov-like export keys onto internal connector fixture rows.

    Preserves Sprint 25 corpus compatibility (Title, agencyName, OpportunityNumber, …).
    Optionally infers ``tribal_eligible`` / ``eligibility_tags`` from synopsis +
    eligibility narrative fields when ``tribal_eligible`` is unset.
    """
    out = dict(raw)

    title = _first_str(out, _TITLE_KEYS)
    if title is not None:
        out["opportunity_title"] = title

    agency = _first_str(out, _AGENCY_KEYS)
    if agency is not None:
        out["agency"] = agency

    agency_code = _first_str(out, _AGENCY_CODE_KEYS)
    if agency_code is not None:
        out["agency_code"] = agency_code

    num = _first_str(out, _NUMBER_KEYS)
    if num is not None:
        out["opportunity_number"] = num

    url = _first_str(out, _URL_KEYS)
    if url is not None:
        out["source_url"] = url

    cfda = _first_str(out, _CFDA_KEYS)
    if cfda is not None:
        out["cfda_assistance_listing"] = cfda

    posted = _first_any(out, _POSTED_KEYS)
    if posted is not None:
        out["posted_date"] = posted

    dl = _first_any(out, _DEADLINE_KEYS)
    if dl is not None:
        out["application_deadline"] = dl

    synopsis = _first_str(out, _SYNOPSIS_KEYS)
    if synopsis is not None:
        out.setdefault("description", synopsis)
        out.setdefault("raw_nofo_text", synopsis.strip())

    elig_chunks: list[str] = []
    for k in _ELIGIBILITY_TEXT_KEYS:
        v = out.get(k)
        if isinstance(v, str) and v.strip():
            elig_chunks.append(v.strip())
    eligibility_blob = "\n".join(elig_chunks)

    synopsis_body = synopsis or ""
    inference_body = "\n".join(x for x in (synopsis_body, eligibility_blob) if x)

    fi_raw = _first_str(out, _INSTRUMENT_KEYS)
    if fi_raw:
        out.setdefault("award_type", _map_funding_instrument_to_award_type(fi_raw))
        inv = _map_funding_instrument_enum(fi_raw)
        if inv:
            out.setdefault("funding_instrument", inv)

    ost = out.get("opportunity_source_type")
    if ost is None:
        out.setdefault("opportunity_source_type", OpportunitySourceType.federal.value)

    if fi_raw and out.get("award_type") is None:
        cat = fi_raw.lower()
        if "grant" in cat:
            out.setdefault("award_type", GrantAwardType.grant.value)

    ceiling = _parse_optional_amount(_first_any(out, _AWARD_CEILING_KEYS))
    if ceiling is not None:
        out["award_ceiling"] = ceiling

    floor_amt = _parse_optional_amount(_first_any(out, _AWARD_FLOOR_KEYS))
    if floor_amt is not None:
        out["award_floor"] = floor_amt

    cat_val = _first_str(out, _CATEGORY_KEYS)
    if cat_val is not None:
        out["program_category"] = cat_val

    existing_tags = out.get("eligibility_tags")
    tag_list: list[str]
    if isinstance(existing_tags, list):
        tag_list = [str(x) for x in existing_tags]
    else:
        tag_list = []

    explicit_te = out.get("tribal_eligible")
    if explicit_te is True:
        out["tribal_eligible"] = True
    elif explicit_te is False:
        out["tribal_eligible"] = False
    else:
        inferred_elig, inferred_tags = _infer_tribal_signals_from_eligibility_body(
            inference_body
        )
        out["tribal_eligible"] = inferred_elig
        for t in inferred_tags:
            if t not in tag_list:
                tag_list.append(t)

    if tag_list:
        out["eligibility_tags"] = tag_list

    return out


normalize_grants_gov_payload = grants_gov_like_to_fixture_row


def dry_run_grants_gov_shaped_rows(
    rows: list[dict[str, Any]],
    *,
    config: ConnectorSourceConfig,
    ctx: ConnectorRunContext | None = None,
) -> ConnectorDryRunResult:
    """
    Normalize Grants.gov-shaped dicts into scored candidates (offline).

    Provenance sets ``fixture_connector`` to :data:`GRANTS_GOV_SHAPED_CONNECTOR_KEY`.
    """
    run_ctx = ctx or ConnectorRunContext()
    now = run_ctx.now or datetime.now(UTC)
    ctx_filled = ConnectorRunContext(
        dry_run=run_ctx.dry_run,
        run_id=run_ctx.run_id,
        now=now,
        normalization_schema_version=run_ctx.normalization_schema_version,
    )

    candidates: list[NormalizedOpportunityCandidate] = []
    errors: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        internal = grants_gov_like_to_fixture_row(dict(row))
        local_key = str(
            internal.get("fixture_key") or internal.get("opportunity_number") or idx
        )
        extra = {
            "fixture_index": idx,
            "fixture_connector": GRANTS_GOV_SHAPED_CONNECTOR_KEY,
            "connector_shape": GRANTS_GOV_SHAPED_CONNECTOR_KEY,
        }
        try:
            cand = normalize_raw_dict(
                internal,
                local_key=local_key,
                config=config,
                ctx=ctx_filled,
                extra_provenance=extra,
            )
            candidates.append(cand)
        except Exception as ex:  # noqa: BLE001 — capture per-row normalization failures
            errors.append(
                {"fixture_index": idx, "local_key": local_key, "message": str(ex)}
            )

    return ConnectorDryRunResult(
        candidates=tuple(candidates),
        errors=tuple(errors),
    )
