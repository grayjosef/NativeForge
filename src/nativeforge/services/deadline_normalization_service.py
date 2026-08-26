"""Deadline normalization (Gate 86B).

Turns a raw deadline string from a committed record into an ISO date, but only
when the raw string actually determines one. Everything else is reported as
unnormalized with a reason.

The rule this whole module exists to enforce: **a normalized date must be
derivable from the characters in the raw string.** No inferred year, no inferred
day, no month-only date rounded to the first or the last. ``fabricated`` is
always ``False`` and an invariant fails if it is ever anything else.

## Why this is not inside the freshness evaluator

``opportunity_freshness_service`` takes ISO strings and its docstring is explicit
that it avoids owning a timezone policy. A slash date needs a *locale* policy on
top of that - whether ``07/01`` is July 1 or January 7 - and pushing that
decision into the evaluator would make a module that correctly refuses to guess
start guessing. Normalization sits upstream; the evaluator is unchanged.

## Ambiguity

``07/24/2026`` proves its own format: 24 cannot be a month, so it is
``MM/DD/YYYY`` and cannot be read any other way. ``07/01/2026`` proves nothing on
its own.

The two cases are kept apart rather than flattened:

* a self-proving date normalizes at ``parse_confidence: "structural"``
* an ambiguous date normalizes **only** when the caller explicitly declares a
  convention, at ``parse_confidence: "convention_declared"``
* with no declared convention, an ambiguous date stays unnormalized and says so

A caller that does not know its source's convention therefore cannot
accidentally get a guess. It gets ``parse_status: "ambiguous"``.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

SCHEMA_VERSION = "nf_deadline_normalization_v1"

# What the caller can assert about a source's slash-date convention. "unknown"
# is the default and is the honest state for most sources.
DATE_CONVENTIONS = frozenset({"unknown", "month_first", "day_first"})

PARSE_STATUSES = frozenset(
    {
        # A normalized ISO date was produced.
        "normalized",
        # The raw value was already an ISO date; normalized_date equals it.
        "already_iso",
        # Structure understood, but the raw string does not determine a date.
        "ambiguous",
        # A real calendar date is not what these characters describe.
        "impossible",
        # Understood, but coarser than a day. Never rounded to one.
        "insufficient_precision",
        # Nothing recognisable.
        "unparseable",
        # Nothing there at all.
        "absent",
    }
)

# Only "day" ever yields a normalized date. The coarser two exist so a partial
# date can be reported accurately instead of discarded or rounded.
DATE_PRECISIONS = frozenset({"day", "month", "year", "none"})

PARSE_CONFIDENCES = frozenset(
    {
        # Unambiguous by format: an ISO date.
        "exact",
        # Unambiguous by content: a field over 12 cannot be a month.
        "structural",
        # Resolved only because the caller declared the source's convention.
        "convention_declared",
        # No date produced.
        "none",
    }
)

SOURCE_FORMATS = frozenset(
    {
        "iso_8601_date",
        "iso_8601_datetime",
        "slash_numeric",
        "partial_date",
        "unrecognised",
        "absent",
    }
)

_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_ISO_DATETIME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[T ]\d{2}:\d{2}")
_SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
# Recognised so they can be reported as too coarse rather than as unparseable.
_YEAR_MONTH = re.compile(r"^(\d{4})-(\d{1,2})$")
_MONTH_YEAR_SLASH = re.compile(r"^(\d{1,2})/(\d{4})$")
_YEAR_ONLY = re.compile(r"^(\d{4})$")
# A slash date with no year: the year must not be filled in from anywhere.
_SLASH_NO_YEAR = re.compile(r"^(\d{1,2})/(\d{1,2})$")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _result(
    *,
    raw_value: Any,
    normalized_date: str | None = None,
    date_precision: str = "none",
    parse_status: str,
    parse_confidence: str = "none",
    source_format: str = "unrecognised",
    warnings: list[str] | None = None,
    blocked_reasons: list[str] | None = None,
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "raw_value": raw_value,
            "normalized_date": normalized_date,
            "date_precision": date_precision,
            "parse_status": parse_status,
            "parse_confidence": parse_confidence,
            "source_format": source_format,
            "warnings": list(warnings or []),
            "blocked_reasons": list(blocked_reasons or []),
            # Never true. A normalized date is always a rearrangement of digits
            # that were already in raw_value.
            "fabricated": False,
        }
    )


def _valid_calendar_date(year: int, month: int, day: int) -> bool:
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


def normalize_deadline(
    *,
    raw_value: Any,
    source_convention: str = "unknown",
) -> dict[str, Any]:
    """Normalize one raw deadline string.

    ``source_convention`` is how a caller asserts what it knows about a source:
    ``"month_first"`` for a US federal feed such as Grants.gov, ``"day_first"``
    for a source that emits ``DD/MM/YYYY``, ``"unknown"`` (the default) when it
    genuinely does not know. It is only ever consulted for a slash date whose
    own digits do not settle the question.
    """
    convention = (
        source_convention if source_convention in DATE_CONVENTIONS else "unknown"
    )
    unrecognised_convention = source_convention not in DATE_CONVENTIONS

    if raw_value is None:
        return _result(
            raw_value=raw_value,
            parse_status="absent",
            source_format="absent",
            blocked_reasons=["no_value"],
        )

    if not isinstance(raw_value, str):
        return _result(
            raw_value=raw_value,
            parse_status="unparseable",
            blocked_reasons=[f"non_string_value:{type(raw_value).__name__}"],
        )

    text = raw_value.strip()
    if not text:
        return _result(
            raw_value=raw_value,
            parse_status="absent",
            source_format="absent",
            blocked_reasons=["empty_string"],
        )

    warnings: list[str] = []
    if unrecognised_convention:
        warnings.append(f"unrecognised_source_convention:{source_convention}")

    # -- already ISO -------------------------------------------------------
    match = _ISO_DATE.match(text)
    if match:
        year, month, day = (int(g) for g in match.groups())
        if not _valid_calendar_date(year, month, day):
            return _result(
                raw_value=raw_value,
                parse_status="impossible",
                source_format="iso_8601_date",
                warnings=[*warnings, f"not_a_calendar_date:{text}"],
                blocked_reasons=["impossible_date"],
            )
        return _result(
            raw_value=raw_value,
            normalized_date=f"{year:04d}-{month:02d}-{day:02d}",
            date_precision="day",
            parse_status="already_iso",
            parse_confidence="exact",
            source_format="iso_8601_date",
            warnings=warnings,
        )

    match = _ISO_DATETIME.match(text)
    if match:
        year, month, day = (int(g) for g in match.groups())
        if not _valid_calendar_date(year, month, day):
            return _result(
                raw_value=raw_value,
                parse_status="impossible",
                source_format="iso_8601_datetime",
                warnings=[*warnings, f"not_a_calendar_date:{text}"],
                blocked_reasons=["impossible_date"],
            )
        return _result(
            raw_value=raw_value,
            normalized_date=f"{year:04d}-{month:02d}-{day:02d}",
            date_precision="day",
            parse_status="normalized",
            parse_confidence="exact",
            source_format="iso_8601_datetime",
            # The time of day is dropped, which matters if a caller ever needs
            # a deadline hour. Said out loud rather than done silently.
            warnings=[*warnings, "time_component_discarded"],
        )

    # -- slash numeric -----------------------------------------------------
    match = _SLASH.match(text)
    if match:
        first, second, year = (int(g) for g in match.groups())

        first_can_be_month = 1 <= first <= 12
        second_can_be_month = 1 <= second <= 12

        if not first_can_be_month and not second_can_be_month:
            return _result(
                raw_value=raw_value,
                parse_status="impossible",
                source_format="slash_numeric",
                warnings=[*warnings, f"no_field_can_be_a_month:{text}"],
                blocked_reasons=["impossible_date"],
            )

        if first_can_be_month and not second_can_be_month:
            # Only one reading survives: the second field is too large to be a
            # month, so this is month-first.
            month, day, confidence = first, second, "structural"
        elif second_can_be_month and not first_can_be_month:
            month, day, confidence = second, first, "structural"
        else:
            # Both readings are grammatical. The digits do not settle it.
            if convention == "month_first":
                month, day, confidence = first, second, "convention_declared"
            elif convention == "day_first":
                month, day, confidence = second, first, "convention_declared"
            else:
                return _result(
                    raw_value=raw_value,
                    parse_status="ambiguous",
                    date_precision="day",
                    source_format="slash_numeric",
                    warnings=[
                        *warnings,
                        f"both_readings_valid:{first:02d}/{second:02d}",
                    ],
                    blocked_reasons=["ambiguous_without_declared_convention"],
                )

        if not _valid_calendar_date(year, month, day):
            return _result(
                raw_value=raw_value,
                parse_status="impossible",
                source_format="slash_numeric",
                warnings=[*warnings, f"not_a_calendar_date:{text}"],
                blocked_reasons=["impossible_date"],
            )

        return _result(
            raw_value=raw_value,
            normalized_date=f"{year:04d}-{month:02d}-{day:02d}",
            date_precision="day",
            parse_status="normalized",
            parse_confidence=confidence,
            source_format="slash_numeric",
            warnings=warnings,
        )

    # -- recognisable but too coarse --------------------------------------
    # These are named rather than lumped into "unparseable" because the fix is
    # different: an unparseable string may be junk, whereas "2026-07" is a real
    # answer to a question nobody can act on without a day.
    match = _YEAR_MONTH.match(text) or _MONTH_YEAR_SLASH.match(text)
    if match:
        return _result(
            raw_value=raw_value,
            date_precision="month",
            parse_status="insufficient_precision",
            source_format="partial_date",
            warnings=[*warnings, "month_precision_not_rounded_to_a_day"],
            blocked_reasons=["no_day_component"],
        )

    if _YEAR_ONLY.match(text):
        return _result(
            raw_value=raw_value,
            date_precision="year",
            parse_status="insufficient_precision",
            source_format="partial_date",
            warnings=[*warnings, "year_precision_not_rounded_to_a_day"],
            blocked_reasons=["no_month_component", "no_day_component"],
        )

    if _SLASH_NO_YEAR.match(text):
        return _result(
            raw_value=raw_value,
            parse_status="insufficient_precision",
            source_format="partial_date",
            warnings=[*warnings, "year_not_inferred"],
            blocked_reasons=["no_year_component"],
        )

    return _result(
        raw_value=raw_value,
        parse_status="unparseable",
        source_format="unrecognised",
        warnings=warnings,
        blocked_reasons=["unrecognised_format"],
    )


def normalize_deadlines(
    *,
    raw_values: list[Any],
    source_convention: str = "unknown",
) -> list[dict[str, Any]]:
    return [
        normalize_deadline(raw_value=v, source_convention=source_convention)
        for v in raw_values
    ]


def summarise_normalization(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts over a batch, for the baseline to report."""
    by_status = {status: 0 for status in sorted(PARSE_STATUSES)}
    by_confidence = {c: 0 for c in sorted(PARSE_CONFIDENCES)}
    for r in results:
        status = r.get("parse_status")
        if status in by_status:
            by_status[status] += 1
        confidence = r.get("parse_confidence")
        if confidence in by_confidence:
            by_confidence[confidence] += 1

    present = sum(1 for r in results if r.get("parse_status") != "absent")
    normalized = sum(1 for r in results if r.get("normalized_date"))

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "total": len(results),
            "with_raw_value": present,
            "normalized": normalized,
            "by_parse_status": by_status,
            "by_parse_confidence": by_confidence,
            # Share of *present* raw values that yielded a date. Absent values
            # are excluded from the denominator: a record with no deadline is
            # not a normalization failure.
            "normalization_rate": (
                round(normalized / present, 4) if present else 0.0
            ),
            "fabricated": False,
        }
    )


def normalization_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    status = result.get("parse_status")
    if status not in PARSE_STATUSES:
        fails.append(f"parse_status_out_of_vocabulary:{status}")
    if result.get("date_precision") not in DATE_PRECISIONS:
        fails.append("date_precision_out_of_vocabulary")
    if result.get("parse_confidence") not in PARSE_CONFIDENCES:
        fails.append("parse_confidence_out_of_vocabulary")
    if result.get("source_format") not in SOURCE_FORMATS:
        fails.append("source_format_out_of_vocabulary")

    normalized = result.get("normalized_date")

    if normalized is not None:
        # The core guarantee: a produced date must be day-precision, confident,
        # and made only of digits that were already in the raw value.
        if result.get("date_precision") != "day":
            fails.append("normalized_date_without_day_precision")
        if result.get("parse_confidence") == "none":
            fails.append("normalized_date_without_confidence")
        if status not in {"normalized", "already_iso"}:
            fails.append(f"normalized_date_with_status:{status}")
        if result.get("blocked_reasons"):
            fails.append("normalized_date_with_blocked_reasons")

        # The anti-fabrication check. Every component of the produced date must
        # appear as a whole number in the raw string.
        #
        # Compared as integers rather than characters because zero-padding
        # legitimately adds a digit: "7/4/2026" yields "2026-07-04", whose
        # characters are not a subset of the raw ones, but whose year, month and
        # day are all literally present. A character-level check would reject
        # correct output and, worse, would tempt someone to weaken it later.
        raw_text = str(result.get("raw_value") or "")
        raw_numbers = {int(n) for n in re.findall(r"\d+", raw_text)}
        year, month, day = (int(part) for part in normalized.split("-"))
        for label, value in (("year", year), ("month", month), ("day", day)):
            if value not in raw_numbers:
                fails.append(f"normalized_{label}_absent_from_raw_value")
    else:
        if not result.get("blocked_reasons"):
            fails.append("no_normalized_date_and_no_blocked_reason")
        if result.get("parse_confidence") != "none":
            fails.append("confidence_asserted_without_a_date")

    return fails
