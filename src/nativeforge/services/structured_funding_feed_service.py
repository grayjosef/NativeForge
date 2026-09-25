"""Turn a structured funding dataset into opportunities, carefully.

A state portal will hand you two thousand rows and it is tempting to call that
a pipeline. It is not. Measured on one real statewide feed:

    2,010 rows
      170 active
    1,838 closed
        2 forecasted

Quoting the row count would overstate the open pipeline by more than 91%, and
the overstatement would be invisible - every row is real, every row is
well-formed, and almost none of them can be applied for.

So nothing becomes an opportunity until its lifecycle is established, and the
classifier prefers what the publisher SAYS over what a date implies.

## Why the publisher's status wins

A deadline in the past does not mean closed: rolling programmes accept
applications continuously and some reopen. A deadline in the future does not
mean open: a programme can be announced, suspended, and left with a stale
date. Where the publisher states a status, that is the evidence; dates are
used to refine it, never to overrule it.

## Program identity is not opportunity identity

The same real feed carries 403 distinct programme ids across 2,010 rows, and
its programme id is sometimes null. Keying opportunities on it would fuse five
years of funding rounds into one record and lose four of them. The row id is
the opportunity; the programme id is metadata about which programme it belongs
to.

## Nothing here is California

Field names arrive as a mapping. A different state, a CKAN feed, a Socrata
dataset or a custom REST export supplies its own map and reuses the rest.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

SCHEMA_VERSION = "nf_structured_funding_feed_v1"

# ---- lifecycle -------------------------------------------------------
OPEN = "OPEN"
UPCOMING = "UPCOMING"
CLOSED = "CLOSED"
ARCHIVED = "ARCHIVED"
AWARD_INFORMATION = "AWARD_INFORMATION"
PROGRAM_INFORMATION = "PROGRAM_INFORMATION"
UNKNOWN = "UNKNOWN"

LIFECYCLES: tuple[str, ...] = (
    OPEN,
    UPCOMING,
    CLOSED,
    ARCHIVED,
    AWARD_INFORMATION,
    PROGRAM_INFORMATION,
    UNKNOWN,
)

#: Lifecycles that may reach a customer as something to act on. Everything
#: else is evidence, history or context - real, and not an opportunity.
ACTIONABLE: frozenset[str] = frozenset({OPEN, UPCOMING})

#: Publisher status strings mapped onto lifecycle. A status the publisher
#: uses that is not named here becomes UNKNOWN rather than a guess.
DEFAULT_STATUS_MAP: dict[str, str] = {
    "active": OPEN,
    "open": OPEN,
    "accepting applications": OPEN,
    "forecasted": UPCOMING,
    "upcoming": UPCOMING,
    "anticipated": UPCOMING,
    "closed": CLOSED,
    "expired": CLOSED,
    "archived": ARCHIVED,
    "awarded": AWARD_INFORMATION,
}

#: Wording that means a deadline is not the whole story.
_ROLLING_RE = re.compile(
    r"\b(rolling|continuous|ongoing|no\s+deadline|until\s+funds|open\s+until)\b",
    re.I,
)

# ---- matching funds --------------------------------------------------
MATCH_NOT_REQUIRED = "NO_MATCH"
MATCH_REQUIRED = "MATCH_REQUIRED"
MATCH_OPTIONAL = "MATCH_OPTIONAL"
MATCH_WAIVER_AVAILABLE = "WAIVER_AVAILABLE"
MATCH_UNKNOWN = "UNKNOWN"

_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")

#: Applicant-type tokens that name a Native entity class. The publisher's own
#: vocabulary, not an inference from geography.
_NATIVE_APPLICANT_TOKENS: tuple[str, ...] = (
    "tribal government",
    "tribal organization",
    "tribe",
    "native american",
    "alaska native",
    "native hawaiian",
)

#: Place words. Present so they can be EXCLUDED from Native evidence.
_GEOGRAPHY_TOKENS: tuple[str, ...] = (
    "statewide",
    "county",
    "city",
    "region",
    "rural",
    "disadvantaged",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _get(row: dict[str, Any], field_map: dict[str, str], key: str) -> str:
    return str(row.get(field_map.get(key, key)) or "").strip()


def _parse_date(raw: str) -> dict[str, Any]:
    """Parse without inventing a timezone the publisher did not supply."""
    text = str(raw or "").strip()
    if not text:
        return {"value": None, "parsed": None, "has_timezone": False}
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
        return {
            "value": text,
            "parsed": parsed.date().isoformat(),
            # The publisher gave a local wall-clock time and no zone. Saying
            # UTC would be a one-day error at the wrong end of a deadline.
            "has_timezone": False,
        }
    return {"value": text, "parsed": None, "has_timezone": False, "unparsed": True}


def classify_lifecycle(
    row: dict[str, Any],
    *,
    field_map: dict[str, str] | None = None,
    status_map: dict[str, str] | None = None,
    as_of: Any = None,
) -> dict[str, Any]:
    """What is this row, really? Publisher status first, dates second."""
    fmap = field_map or {}
    smap = status_map or DEFAULT_STATUS_MAP
    today = as_of or dt.date.today().isoformat()

    status_raw = _get(row, fmap, "status")
    deadline = _parse_date(_get(row, fmap, "deadline"))
    open_date = _parse_date(_get(row, fmap, "open_date"))
    notes = " ".join(
        _get(row, fmap, k) for k in ("deadline_notes", "description", "purpose")
    )
    rolling = bool(_ROLLING_RE.search(notes))

    reasons: list[str] = []
    lifecycle = UNKNOWN
    basis = "none"

    mapped = smap.get(status_raw.lower()) if status_raw else None
    if mapped:
        lifecycle = mapped
        basis = "publisher_status"
        reasons.append(f"publisher_status:{status_raw.lower()}")
    elif status_raw:
        reasons.append(f"publisher_status_not_recognised:{status_raw.lower()}")

    # Dates REFINE a publisher status; they never overrule one.
    if lifecycle == OPEN and open_date["parsed"] and open_date["parsed"] > today:
        lifecycle = UPCOMING
        basis = "publisher_status_refined_by_open_date"
        reasons.append("open_date_is_in_the_future")
    elif lifecycle == UNKNOWN and deadline["parsed"]:
        if rolling:
            reasons.append("rolling_wording_present_deadline_is_not_decisive")
        elif deadline["parsed"] >= today:
            lifecycle = OPEN
            basis = "deadline_only"
            reasons.append("deadline_in_future_and_no_publisher_status")
        else:
            lifecycle = CLOSED
            basis = "deadline_only"
            reasons.append("deadline_in_past_and_no_publisher_status")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "lifecycle": lifecycle,
            "classification_basis": basis,
            "publisher_status_raw": status_raw or None,
            "deadline": deadline,
            "open_date": open_date,
            "rolling_language_present": rolling,
            "is_actionable": lifecycle in ACTIONABLE,
            "as_of": today,
            "reasons": sorted(set(reasons)),
            # The whole point, restated on every row.
            "a_dataset_row_is_not_an_open_opportunity": True,
        }
    )


def build_record_identity(
    row: dict[str, Any], *, field_map: dict[str, str] | None = None
) -> dict[str, Any]:
    """The row is the opportunity. The programme is metadata about it."""
    fmap = field_map or {}
    opportunity_id = _get(row, fmap, "opportunity_id")
    program_id = _get(row, fmap, "program_id")
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_key": opportunity_id or None,
            "program_key": program_id or None,
            "has_opportunity_key": bool(opportunity_id),
            # Observed on a real feed: the programme id is nullable, and 403
            # of them cover 2,010 rows. Keying on it loses four rounds in five.
            "program_key_is_not_opportunity_identity": True,
            "keyed_on": "opportunity_id" if opportunity_id else "none",
        }
    )


def normalize_matching_funds(raw: Any, *, notes: Any = None) -> dict[str, Any]:
    """Normalize a match requirement without upgrading a maybe into a must."""
    text = str(raw or "").strip()
    note_text = str(notes or "").strip()
    combined = f"{text} {note_text}".lower()

    state = MATCH_UNKNOWN
    reasons: list[str] = []
    percent = None

    match = _PERCENT_RE.search(text)
    if match:
        percent = float(match.group(1))
        state = MATCH_NOT_REQUIRED if percent == 0 else MATCH_REQUIRED
        reasons.append(f"explicit_percentage:{match.group(1)}")
    elif text.lower() in ("not required", "none", "no match", "no"):
        state = MATCH_NOT_REQUIRED
        reasons.append("publisher_states_not_required")
    elif "required" in combined and "not required" not in combined:
        if any(w in combined for w in ("may be", "might", "could", "possibly")):
            # "A match may be required" is not a match requirement.
            state = MATCH_UNKNOWN
            reasons.append("hedged_wording_is_not_a_requirement")
        else:
            state = MATCH_REQUIRED
            reasons.append("publisher_states_required")
    elif any(w in combined for w in ("optional", "encouraged", "preferred")):
        state = MATCH_OPTIONAL
        reasons.append("publisher_states_optional")

    if "waiv" in combined:
        reasons.append("waiver_language_present")
        if state == MATCH_REQUIRED:
            state = MATCH_WAIVER_AVAILABLE

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "match_state": state,
            "match_percent": percent,
            # The publisher's words survive normalization.
            "raw_value": text or None,
            "raw_notes": note_text or None,
            "reasons": sorted(set(reasons)),
        }
    )


def extract_applicant_evidence(
    row: dict[str, Any], *, field_map: dict[str, str] | None = None
) -> dict[str, Any]:
    """Which applicant classes the publisher named. Evidence, not a verdict.

    A feed whose geography is a state is not thereby Native-relevant. What
    counts is the publisher declaring that a Tribal entity may apply.
    """
    fmap = field_map or {}
    applicant_raw = _get(row, fmap, "applicant_type")
    notes = _get(row, fmap, "applicant_type_notes")
    geography = _get(row, fmap, "geography")

    # Publishers commonly delimit these with semicolons.
    declared = [p.strip() for p in re.split(r"[;,|]", applicant_raw) if p.strip()]
    lowered = applicant_raw.lower()

    native_tokens = sorted({t for t in _NATIVE_APPLICANT_TOKENS if t in lowered})
    geo_tokens = sorted(
        {t for t in _GEOGRAPHY_TOKENS if t in f"{geography} {lowered}".lower()}
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "declared_applicant_types": declared,
            "applicant_type_raw": applicant_raw or None,
            "applicant_type_notes": notes or None,
            "native_applicant_tokens": native_tokens,
            "has_native_applicant_evidence": bool(native_tokens),
            "geography_tokens": geo_tokens,
            "has_geography_only_signal": bool(geo_tokens) and not native_tokens,
            # Two refusals, on every row.
            "geography_alone_is_not_native_relevance": True,
            "applicant_type_is_not_a_tenant_eligibility_verdict": True,
            "relevance_decided": False,
            "eligibility_decided": False,
        }
    )


def summarize_feed(
    classifications: list[dict[str, Any]],
) -> dict[str, Any]:
    """Counts by lifecycle, so nobody quotes the row count as the pipeline."""
    counts: dict[str, int] = {life: 0 for life in LIFECYCLES}
    for entry in classifications:
        life = str(entry.get("lifecycle") or UNKNOWN)
        counts[life] = counts.get(life, 0) + 1
    actionable = sum(counts.get(life, 0) for life in ACTIONABLE)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "row_count": len(classifications),
            "by_lifecycle": dict(sorted(counts.items())),
            "actionable_count": actionable,
            # Named so the difference cannot be quietly dropped.
            "row_count_is_not_opportunity_count": True,
            "inflation_if_row_count_quoted": (len(classifications) - actionable),
        }
    )
