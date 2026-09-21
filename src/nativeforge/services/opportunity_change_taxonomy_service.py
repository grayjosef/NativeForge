"""What changed, and how much it matters (Gate 170B/170D).

Pure rules over two normalized values. No LLM, no heuristic scoring, no
threshold anybody can tune into a different answer.

## Direction is the whole point for a deadline

```text
DEADLINE_EXTENDED    more time     MATERIAL
DEADLINE_SHORTENED   LESS time     CRITICAL
```

Those are not the same event and must never share a type. A Tribe that read
the original date and planned around it needs to know *immediately* when the
window shrinks; an extension is good news that can wait for a digest. A
taxonomy with one `DEADLINE_CHANGED` type forces both into the same alert and
guarantees one of them is wrong.

Direction requires parsing the dates, and a date that cannot be parsed yields
`DEADLINE_CHANGED` with materiality `MATERIAL` - the safe middle. Guessing a
direction from unparseable text would be worse than admitting ignorance.

## Every classification carries the rule that produced it

`materiality_rule` is a name, not a sentence, and migration 0055 refuses to
store a non-UNKNOWN materiality without one. "CRITICAL" is not reviewable;
"CRITICAL because `deadline_shortened`" is, and an operator woken by an alert
can argue with the second.

## Removal is not the inverse of addition

```text
eligibility ADDED     MATERIAL        more applicants may apply
eligibility REMOVED   CRITICAL        somebody who qualified no longer does
```

The asymmetry is deliberate and it runs through the whole table: losing
something you had is worse than not gaining something you never had.

## Nothing here is scored

There is no confidence, no weight and no total. A change is in exactly one
class, decided by exactly one named rule, and the rules are ordered so the
first match wins. A scoring model would make "why did this fire" unanswerable.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

SCHEMA_VERSION = "nf_opportunity_change_taxonomy_v1"

# ------------------------------------------------------ change types

TITLE_CHANGED = "TITLE_CHANGED"
STATUS_CHANGED = "STATUS_CHANGED"
OPEN_DATE_CHANGED = "OPEN_DATE_CHANGED"
DEADLINE_CHANGED = "DEADLINE_CHANGED"
DEADLINE_EXTENDED = "DEADLINE_EXTENDED"
DEADLINE_SHORTENED = "DEADLINE_SHORTENED"
FUNDING_MIN_CHANGED = "FUNDING_MIN_CHANGED"
FUNDING_MAX_CHANGED = "FUNDING_MAX_CHANGED"
ELIGIBILITY_CHANGED = "ELIGIBILITY_CHANGED"
AGENCY_CHANGED = "AGENCY_CHANGED"
OPPORTUNITY_NUMBER_CHANGED = "OPPORTUNITY_NUMBER_CHANGED"
DOCUMENT_ADDED = "DOCUMENT_ADDED"
DOCUMENT_REMOVED = "DOCUMENT_REMOVED"
DOCUMENT_REPLACED = "DOCUMENT_REPLACED"
SOURCE_URL_CHANGED = "SOURCE_URL_CHANGED"
ASSISTANCE_LISTINGS_CHANGED = "ASSISTANCE_LISTINGS_CHANGED"
FORECAST_TO_POSTED = "FORECAST_TO_POSTED"
POSTED_TO_CLOSED = "POSTED_TO_CLOSED"
REOPENED = "REOPENED"
CANCELLED = "CANCELLED"
AMENDMENT_PUBLISHED = "AMENDMENT_PUBLISHED"
CONFLICT_INTRODUCED = "CONFLICT_INTRODUCED"
CONFLICT_RESOLVED = "CONFLICT_RESOLVED"
FIRST_OBSERVED = "FIRST_OBSERVED"
UNKNOWN_CHANGE = "UNKNOWN_CHANGE"

CHANGE_TYPES: tuple[str, ...] = (
    TITLE_CHANGED,
    STATUS_CHANGED,
    OPEN_DATE_CHANGED,
    DEADLINE_CHANGED,
    DEADLINE_EXTENDED,
    DEADLINE_SHORTENED,
    FUNDING_MIN_CHANGED,
    FUNDING_MAX_CHANGED,
    ELIGIBILITY_CHANGED,
    AGENCY_CHANGED,
    OPPORTUNITY_NUMBER_CHANGED,
    DOCUMENT_ADDED,
    DOCUMENT_REMOVED,
    DOCUMENT_REPLACED,
    SOURCE_URL_CHANGED,
    ASSISTANCE_LISTINGS_CHANGED,
    FORECAST_TO_POSTED,
    POSTED_TO_CLOSED,
    REOPENED,
    CANCELLED,
    AMENDMENT_PUBLISHED,
    CONFLICT_INTRODUCED,
    CONFLICT_RESOLVED,
    FIRST_OBSERVED,
    UNKNOWN_CHANGE,
)

# ------------------------------------------------------ materiality

CRITICAL = "CRITICAL"
MATERIAL = "MATERIAL"
INFORMATIONAL = "INFORMATIONAL"
NON_MATERIAL = "NON_MATERIAL"
UNKNOWN = "UNKNOWN"

MATERIALITY_CLASSES: tuple[str, ...] = (
    CRITICAL,
    MATERIAL,
    INFORMATIONAL,
    NON_MATERIAL,
    UNKNOWN,
)

#: change_type -> (materiality, named rule). The rule name is what makes a
#: classification arguable; migration 0055 refuses to store one without it.
#:
#: Read the asymmetries: losing time, losing eligibility and losing a document
#: outrank their opposites, because a Tribe that planned around the old value
#: has already spent effort on it.
MATERIALITY_BY_TYPE: dict[str, tuple[str, str]] = {
    DEADLINE_SHORTENED: (CRITICAL, "deadline_shortened_reduces_time_to_apply"),
    CANCELLED: (CRITICAL, "cancellation_ends_the_opportunity"),
    OPPORTUNITY_NUMBER_CHANGED: (
        CRITICAL,
        "the_identifier_an_application_cites_changed",
    ),
    DOCUMENT_REMOVED: (CRITICAL, "a_required_document_is_no_longer_available"),
    POSTED_TO_CLOSED: (CRITICAL, "the_window_to_apply_has_ended"),
    DEADLINE_EXTENDED: (MATERIAL, "deadline_extended_grants_more_time"),
    DEADLINE_CHANGED: (MATERIAL, "deadline_moved_direction_undetermined"),
    ELIGIBILITY_CHANGED: (MATERIAL, "who_may_apply_changed"),
    FUNDING_MIN_CHANGED: (MATERIAL, "award_floor_changed"),
    FUNDING_MAX_CHANGED: (MATERIAL, "award_ceiling_changed"),
    AMENDMENT_PUBLISHED: (MATERIAL, "the_agency_published_an_amendment"),
    FORECAST_TO_POSTED: (MATERIAL, "a_forecast_became_an_open_opportunity"),
    REOPENED: (MATERIAL, "a_closed_opportunity_accepts_applications_again"),
    STATUS_CHANGED: (MATERIAL, "lifecycle_status_moved"),
    AGENCY_CHANGED: (MATERIAL, "the_funding_agency_changed"),
    DOCUMENT_REPLACED: (MATERIAL, "a_document_was_superseded"),
    CONFLICT_INTRODUCED: (MATERIAL, "sources_began_disagreeing_about_this_field"),
    DOCUMENT_ADDED: (INFORMATIONAL, "a_document_was_added"),
    OPEN_DATE_CHANGED: (INFORMATIONAL, "the_opening_date_moved"),
    ASSISTANCE_LISTINGS_CHANGED: (
        INFORMATIONAL,
        "assistance_listing_numbers_changed",
    ),
    CONFLICT_RESOLVED: (INFORMATIONAL, "sources_now_agree_about_this_field"),
    SOURCE_URL_CHANGED: (INFORMATIONAL, "the_document_moved_without_a_program_change"),
    TITLE_CHANGED: (INFORMATIONAL, "free_text_title_was_edited"),
    FIRST_OBSERVED: (
        NON_MATERIAL,
        "first_sighting_is_a_discovery_not_an_amendment",
    ),
    UNKNOWN_CHANGE: (UNKNOWN, ""),
}

#: Canonical field -> the change type a plain value move produces. Deadline
#: and status are absent on purpose: both need the VALUES to decide, not just
#: the field name.
TYPE_BY_FIELD: dict[str, str] = {
    "title": TITLE_CHANGED,
    "open_date": OPEN_DATE_CHANGED,
    "funder_agency_code": AGENCY_CHANGED,
    "funder_agency_name": AGENCY_CHANGED,
    "opportunity_number": OPPORTUNITY_NUMBER_CHANGED,
    "eligibility_text": ELIGIBILITY_CHANGED,
    "funding_amount_min": FUNDING_MIN_CHANGED,
    "funding_amount_max": FUNDING_MAX_CHANGED,
    "source_url": SOURCE_URL_CHANGED,
    "assistance_listings": ASSISTANCE_LISTINGS_CHANGED,
    "doc_type": STATUS_CHANGED,
    "source_record_id": UNKNOWN_CHANGE,
}

#: Status transitions that mean something specific. Anything else is a plain
#: STATUS_CHANGED rather than a guess.
STATUS_TRANSITIONS: dict[tuple[str, str], str] = {
    ("forecasted", "posted"): FORECAST_TO_POSTED,
    ("forecast", "posted"): FORECAST_TO_POSTED,
    ("posted", "closed"): POSTED_TO_CLOSED,
    ("closed", "posted"): REOPENED,
    ("posted", "cancelled"): CANCELLED,
    ("forecasted", "cancelled"): CANCELLED,
    ("closed", "archived"): POSTED_TO_CLOSED,
}

_DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%d %B %Y", "%B %d, %Y")

#: A title edit that only changes punctuation, case or whitespace is not a
#: change anybody needs to read about.
_TITLE_NOISE = re.compile(r"[^0-9a-z]+")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def parse_date(raw: Any) -> dt.date | None:
    """Parse a published date, or return None. Never guesses."""
    text = str(raw or "").strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def classify_deadline_move(prior: Any, new: Any) -> tuple[str, str]:
    """Which way a deadline moved, and why we believe it.

    An unparseable date on either side yields the undirected type. That is the
    honest answer: a direction inferred from text nobody could parse would be
    a guess with an alert attached to it.
    """
    before = parse_date(prior)
    after = parse_date(new)
    if before is None or after is None:
        return DEADLINE_CHANGED, "one_or_both_dates_could_not_be_parsed"
    if after > before:
        return (
            DEADLINE_EXTENDED,
            f"deadline_moved_later_by_{(after - before).days}_days",
        )
    if after < before:
        return (
            DEADLINE_SHORTENED,
            f"deadline_moved_earlier_by_{(before - after).days}_days",
        )
    return DEADLINE_CHANGED, "dates_parsed_equal_despite_differing_text"


def _title_is_cosmetic(prior: Any, new: Any) -> bool:
    """Same words, different punctuation or spacing."""
    return _TITLE_NOISE.sub(" ", str(prior or "").casefold()).split() == (
        _TITLE_NOISE.sub(" ", str(new or "").casefold()).split()
    )


def _listing_move(prior: Any, new: Any) -> tuple[str, str] | None:
    """A list field gained or lost members."""
    try:
        before = set(json.loads(prior) if isinstance(prior, str) else (prior or []))
        after = set(json.loads(new) if isinstance(new, str) else (new or []))
    except Exception:  # noqa: BLE001
        return None
    if after > before:
        return DOCUMENT_ADDED, "entries_added_to_the_list"
    if after < before:
        return DOCUMENT_REMOVED, "entries_removed_from_the_list"
    if before and after and before != after:
        return DOCUMENT_REPLACED, "list_membership_changed_in_both_directions"
    return None


def classify_change(
    *,
    field_name: Any,
    prior_value: Any = None,
    new_value: Any = None,
    is_first_observation: bool = False,
    deadline_shape: Any = None,
) -> dict[str, Any]:
    """One field move -> a typed, rule-backed change. Pure; never raises."""
    field = str(field_name or "").strip()
    reasons: list[str] = []

    if is_first_observation:
        change_type = FIRST_OBSERVED
        reasons.append("no_prior_version_exists")
    elif field == "close_date":
        change_type, why = classify_deadline_move(prior_value, new_value)
        reasons.append(why)
        shape = str(deadline_shape or "single")
        if shape in ("dual", "per_region", "phased"):
            # A multi-valued shape means this field is ONE of several
            # deadlines. Saying so keeps a regional change from reading as a
            # national one.
            reasons.append(
                f"deadline_shape_is_{shape}_so_this_is_one_of_several_deadlines"
            )
    elif field == "status":
        before = str(prior_value or "").strip().lower()
        after = str(new_value or "").strip().lower()
        change_type = STATUS_TRANSITIONS.get((before, after), STATUS_CHANGED)
        reasons.append(
            f"status_moved_from_{before or 'unknown'}_to_{after or 'unknown'}"
        )
    elif field == "title":
        if _title_is_cosmetic(prior_value, new_value):
            change_type = TITLE_CHANGED
            reasons.append("title_differs_only_in_punctuation_or_spacing")
            return _result(
                field=field,
                change_type=change_type,
                materiality=NON_MATERIAL,
                rule="cosmetic_title_edit_is_not_a_substantive_change",
                prior_value=prior_value,
                new_value=new_value,
                reasons=reasons,
                deadline_shape=deadline_shape,
            )
        change_type = TITLE_CHANGED
        reasons.append("title_text_changed")
    elif field == "assistance_listings":
        # Deliberately NOT the DOCUMENT_* types. An assistance listing is a
        # program classification code, not an attachment - the first version
        # of this reused DOCUMENT_REMOVED and so reported a dropped CFDA
        # number as CRITICAL because "a required document is no longer
        # available", which is the wrong reason for the wrong severity.
        #
        # The direction is still recorded, because losing a listing can narrow
        # who the program serves and a reader may want to look.
        change_type = ASSISTANCE_LISTINGS_CHANGED
        move = _listing_move(prior_value, new_value)
        if move is not None:
            reasons.append(f"listing_membership_{move[1]}")
        else:
            reasons.append("assistance_listing_membership_changed")
    else:
        change_type = TYPE_BY_FIELD.get(field, UNKNOWN_CHANGE)
        if change_type == UNKNOWN_CHANGE:
            reasons.append(f"no_taxonomy_entry_for_field:{field or 'missing'}")
        else:
            reasons.append(f"field_{field}_maps_to_{change_type}")

    materiality, rule = MATERIALITY_BY_TYPE.get(change_type, (UNKNOWN, ""))
    return _result(
        field=field,
        change_type=change_type,
        materiality=materiality,
        rule=rule,
        prior_value=prior_value,
        new_value=new_value,
        reasons=reasons,
        deadline_shape=deadline_shape,
    )


def _result(
    *,
    field: str,
    change_type: str,
    materiality: str,
    rule: str,
    prior_value: Any,
    new_value: Any,
    reasons: list[str],
    deadline_shape: Any,
) -> dict[str, Any]:
    effective = None
    if change_type in (DEADLINE_CHANGED, DEADLINE_EXTENDED, DEADLINE_SHORTENED):
        effective = str(new_value) if new_value is not None else None
    elif change_type == OPEN_DATE_CHANGED:
        effective = str(new_value) if new_value is not None else None

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "field_name": field or None,
            "change_type": change_type,
            "materiality": materiality,
            "materiality_rule": rule or None,
            "prior_value": prior_value,
            "new_value": new_value,
            "reasons": sorted(set(reasons)),
            "deadline_shape": str(deadline_shape) if deadline_shape else None,
            "effective_date": effective,
            "decided_by": "deterministic_rules",
            "llm_used": False,
        }
    )


def change_invariant_failures(change: dict[str, Any]) -> list[str]:
    """Refuse a classification that cannot be argued with."""
    fails: list[str] = []

    change_type = change.get("change_type")
    if change_type not in CHANGE_TYPES:
        fails.append(f"change_type_outside_the_taxonomy:{change_type}")

    materiality = change.get("materiality")
    if materiality not in MATERIALITY_CLASSES:
        fails.append(f"materiality_outside_the_vocabulary:{materiality}")

    # THE rule: a classification must carry the rule that produced it.
    if materiality != UNKNOWN and not change.get("materiality_rule"):
        fails.append(f"materiality_without_a_named_rule:{materiality}")

    if not change.get("reasons"):
        fails.append("change_named_no_reason")

    if change.get("llm_used"):
        fails.append("an_llm_decided_a_change_classification")

    # A shortened deadline may never be less than CRITICAL, whatever else
    # happens - it is the one change that costs a Tribe time it already spent.
    if change_type == DEADLINE_SHORTENED and materiality != CRITICAL:
        fails.append(f"shortened_deadline_not_critical:{materiality}")

    if change_type == CANCELLED and materiality != CRITICAL:
        fails.append(f"cancellation_not_critical:{materiality}")

    # And a first sighting may never be material: it is a discovery, and
    # firing an amendment alert on it is the wrong signal to the wrong people.
    if change_type == FIRST_OBSERVED and materiality in (CRITICAL, MATERIAL):
        fails.append(f"first_observation_treated_as_an_amendment:{materiality}")

    return sorted(set(fails))


def describe_taxonomy() -> dict[str, Any]:
    """The whole table, as data. Every type has a class and a named rule."""
    unruled = [
        name
        for name in CHANGE_TYPES
        if MATERIALITY_BY_TYPE.get(name, (UNKNOWN, ""))[0] != UNKNOWN
        and not MATERIALITY_BY_TYPE.get(name, (UNKNOWN, ""))[1]
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "change_types": list(CHANGE_TYPES),
            "materiality_classes": list(MATERIALITY_CLASSES),
            "materiality_by_type": {
                name: {"materiality": value[0], "rule": value[1] or None}
                for name, value in sorted(MATERIALITY_BY_TYPE.items())
            },
            "types_without_a_rule": sorted(unruled),
            "every_type_is_classified": sorted(MATERIALITY_BY_TYPE) == sorted(
                CHANGE_TYPES
            ),
            "status_transitions": {
                f"{a}->{b}": name for (a, b), name in sorted(STATUS_TRANSITIONS.items())
            },
            "llm_used": False,
            "decided_by": "deterministic_rules",
        }
    )
