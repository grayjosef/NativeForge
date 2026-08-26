"""Opportunity deadline shapes and amendment materiality (Gate 92G).

## One date field is wrong, and the research pass says how

Five shapes were verified, each of which breaks a single-date model:

* **dual** - every DOJ opportunity has a Grants.gov deadline *and* a separate
  JustGrants deadline (11:59 p.m. ET and 8:59 p.m. ET). Two deadlines, one
  opportunity, both binding.
* **per_region** - EPA GAP publishes ten different regional deadlines inside
  one national NOFA. A national date is not a simplification of that; it is
  wrong for nine regions.
* **revised** - HUD labelled an ICDBG date "New Deadline." Deadlines are
  mutable and versioned; the superseded date is retained as evidence.
* **phased** - USDA NIFA TCRGP phase deadlines appear only in an "Upcoming
  Program Events" block on the program page.
* **multi_year** - FHWA's TTPSF operating NOFO spans 2022-2026 and is at
  Amendment No. 2. The *amendments* change, not the NOFO. Watch amendment
  numbers, not new postings.

Plus ``single``, and ``unknown`` - which is the default. A deadline pattern is
``unknown`` unless it was verified, and a historical pattern is never
synthesized into a current date. Gate 87 established that a date with no
evidence is a placeholder; this service will not manufacture one.

## forecast_lapsed

A forecast whose Estimated Synopsis Post Date has passed with no synopsis and
no archive is the common failure mode of naive trackers: it keeps looking like
a live opportunity forever. It gets its own explicit state rather than being
left in the open pool or silently deleted.

## Amendment materiality

``synopsisModifiedFields[]`` / ``forecastModifiedFields[]`` is the primary
signal - a literal list of the fields the agency changed. Nothing else in the
federal ecosystem provides it, so amendments are classified from the named
fields rather than from a whole-record diff, and users are told *what* changed.

Seven categories, four of which notify. Un-triaged amendment noise is what
makes grant alerting unusable, so contact-name churn and description typos are
classified, recorded, and suppressed - not discarded.

One documented trap is encoded as an invariant: the extract's "Last Updated
Date or Created Date" field is **polymorphic** - if an opportunity was never
updated, the created date appears there. A value in that field does not prove
an update occurred, so it can never be the sole evidence for an amendment.

This service classifies. It does not fetch, and it does not send notifications.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.deadline_normalization_service import (
    PARSE_STATUSES as NORMALIZATION_PARSE_STATUSES,
)

SCHEMA_VERSION = "nf_opportunity_deadline_and_amendment_model_v1"

DEADLINE_PATTERNS = frozenset(
    {
        "single",
        "dual",
        "per_region",
        "revised",
        "phased",
        "multi_year",
        "unknown",
    }
)

# Patterns where a single scalar deadline field cannot represent the truth.
MULTI_VALUED_PATTERNS = frozenset({"dual", "per_region", "phased"})

DEADLINE_LIFECYCLE_STATES = frozenset(
    {
        "open",
        "closed",
        "archived",
        "forecast_pending",
        "forecast_lapsed",
        "unknown",
    }
)

# Seven categories. The first four notify; the last three are suppressed.
AMENDMENT_CATEGORIES = frozenset(
    {
        "deadline_change",
        "eligibility_change",
        "funding_amount_change",
        "attachment_change",
        "contact_change",
        "descriptive_text_change",
        "uncategorized_change",
    }
)

MATERIAL_CATEGORIES = frozenset(
    {
        "deadline_change",
        "eligibility_change",
        "funding_amount_change",
        "attachment_change",
    }
)

# Field-name cues taken from documented fetchOpportunity/extract field names.
_DEADLINE_FIELDS = (
    "closedate",
    "closingdate",
    "responsedate",
    "duedate",
    "archivedate",
    "estimatedsynopsisclosedate",
)
_ELIGIBILITY_FIELDS = (
    "applicanttype",
    "eligib",
    "additionalinformationoneligibility",
)
_FUNDING_FIELDS = (
    "awardceiling",
    "awardfloor",
    "estimatedtotalprogramfunding",
    "expectednumberofawards",
    "costsharing",
)
_ATTACHMENT_FIELDS = ("attachment", "synattchangecomments", "folder", "filelobsize")
_CONTACT_FIELDS = ("contact", "agencycontact", "email", "phone")
_DESCRIPTIVE_FIELDS = ("description", "title", "summary", "additionalinformationurl")

# Documented polymorphic field: holds the created date when nothing was updated.
POLYMORPHIC_UPDATE_FIELD = "last_updated_date_or_created_date"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def categorize_modified_field(field_name: Any) -> str:
    """Map one agency-named modified field onto a category."""
    f = "".join(ch for ch in str(field_name or "").lower() if ch.isalnum())
    if not f:
        return "uncategorized_change"
    for cues, category in (
        (_DEADLINE_FIELDS, "deadline_change"),
        (_ELIGIBILITY_FIELDS, "eligibility_change"),
        (_FUNDING_FIELDS, "funding_amount_change"),
        (_ATTACHMENT_FIELDS, "attachment_change"),
        (_CONTACT_FIELDS, "contact_change"),
        (_DESCRIPTIVE_FIELDS, "descriptive_text_change"),
    ):
        if any(cue in f for cue in cues):
            return category
    # Deny by default: an unrecognised field is uncategorized, and
    # uncategorized is reviewable rather than silently dropped.
    return "uncategorized_change"


def build_deadline_model(
    *,
    pattern: Any = None,
    deadlines: list[dict[str, Any]] | None = None,
    lifecycle_state: Any = None,
    superseded_deadlines: list[dict[str, Any]] | None = None,
    amendment_number: Any = None,
    opportunity_key: Any = None,
) -> dict[str, Any]:
    """Represent one opportunity's deadline shape without inventing dates."""
    p = str(pattern).strip().lower() if pattern else "unknown"
    if p not in DEADLINE_PATTERNS:
        p = "unknown"

    state = str(lifecycle_state).strip().lower() if lifecycle_state else "unknown"
    if state not in DEADLINE_LIFECYCLE_STATES:
        state = "unknown"

    entries = list(deadlines or [])
    superseded = list(superseded_deadlines or [])

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_key": opportunity_key,
            "deadline_pattern": p,
            "pattern_verified": p != "unknown",
            "deadline_count": len(entries),
            "deadlines": entries,
            # Revisions keep their history; the old date is evidence.
            "superseded_deadlines": superseded,
            "superseded_count": len(superseded),
            "deadlines_are_versioned": True,
            "lifecycle_state": state,
            "forecast_lapsed": state == "forecast_lapsed",
            # Multi-year NOFOs: the amendment number is the change signal.
            "amendment_number": amendment_number,
            "watch_amendment_number": p == "multi_year",
            # Constants for this gate.
            "dates_synthesized": 0,
            "dates_inferred_from_pattern": 0,
            "fabricated": False,
        }
    )


def classify_amendment(
    *,
    modified_fields: list[Any] | None = None,
    revision: Any = None,
    previous_revision: Any = None,
    last_updated_or_created_only: bool = False,
    opportunity_key: Any = None,
) -> dict[str, Any]:
    """Classify one amendment from the fields the agency says it changed."""
    fields = [str(f) for f in (modified_fields or []) if str(f).strip()]
    categories = sorted({categorize_modified_field(f) for f in fields})

    per_field = [
        {"field": f, "category": categorize_modified_field(f)} for f in fields
    ]

    material = sorted(c for c in categories if c in MATERIAL_CATEGORIES)
    suppressed = sorted(c for c in categories if c not in MATERIAL_CATEGORIES)

    revision_changed = (
        revision is not None
        and previous_revision is not None
        and revision != previous_revision
    )

    # The polymorphic field alone proves nothing.
    evidence_is_only_polymorphic_field = bool(
        last_updated_or_created_only and not fields and not revision_changed
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_key": opportunity_key,
            "modified_fields": fields,
            "modified_field_count": len(fields),
            "field_categories": per_field,
            "categories": categories,
            "material_categories": material,
            "suppressed_categories": suppressed,
            "is_material": bool(material),
            "should_notify": bool(material),
            "revision": revision,
            "previous_revision": previous_revision,
            "revision_changed": revision_changed,
            # The trap, named.
            "polymorphic_update_field": POLYMORPHIC_UPDATE_FIELD,
            "evidence_is_only_polymorphic_field": evidence_is_only_polymorphic_field,
            "amendment_confirmed": bool(fields or revision_changed),
            # Constants for this gate.
            "notifications_sent": 0,
            "fabricated": False,
        }
    )


def deadline_model_invariant_failures(model: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if model.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if model.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    for counter in ("dates_synthesized", "dates_inferred_from_pattern"):
        if model.get(counter):
            fails.append(f"model_reported_nonzero:{counter}")

    pattern = model.get("deadline_pattern")
    if pattern not in DEADLINE_PATTERNS:
        fails.append("deadline_pattern_out_of_vocabulary")
    if pattern == "unknown" and model.get("pattern_verified") is not False:
        fails.append("unknown_pattern_marked_verified")

    state = model.get("lifecycle_state")
    if state not in DEADLINE_LIFECYCLE_STATES:
        fails.append("lifecycle_state_out_of_vocabulary")
    # forecast_lapsed must be an explicit state, never an open-looking record.
    if model.get("forecast_lapsed") and state != "forecast_lapsed":
        fails.append("forecast_lapsed_flag_without_state")
    if state == "forecast_lapsed" and model.get("forecast_lapsed") is not True:
        fails.append("forecast_lapsed_state_without_flag")

    # A multi-valued pattern that carries one or zero deadlines has collapsed.
    if pattern in MULTI_VALUED_PATTERNS and model.get("deadline_count", 0) < 2:
        fails.append(f"multi_valued_pattern_collapsed_to_scalar:{pattern}")

    if model.get("deadlines_are_versioned") is not True:
        fails.append("deadlines_not_versioned")
    # A revision that discarded its predecessor destroyed the evidence.
    if pattern == "revised" and not model.get("superseded_deadlines"):
        fails.append("revised_pattern_without_superseded_deadline")
    if pattern == "multi_year" and model.get("watch_amendment_number") is not True:
        fails.append("multi_year_not_watching_amendment_number")

    return fails


def amendment_invariant_failures(amendment: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if amendment.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if amendment.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    if amendment.get("notifications_sent"):
        fails.append("amendment_reported_notifications_sent")

    for entry in amendment.get("field_categories") or []:
        if entry.get("category") not in AMENDMENT_CATEGORIES:
            fails.append(f"amendment_category_out_of_vocabulary:{entry.get('field')}")

    categories = set(amendment.get("categories") or [])
    material = set(amendment.get("material_categories") or [])
    suppressed = set(amendment.get("suppressed_categories") or [])

    # Every category is either notified or suppressed. None is dropped.
    if material | suppressed != categories:
        fails.append("amendment_category_dropped")
    if material & suppressed:
        fails.append("amendment_category_both_material_and_suppressed")
    if any(c not in MATERIAL_CATEGORIES for c in material):
        fails.append("non_material_category_marked_material")

    if amendment.get("is_material") != bool(material):
        fails.append("materiality_flag_disagrees_with_categories")
    if amendment.get("should_notify") != bool(material):
        fails.append("notification_decision_disagrees_with_materiality")

    # The polymorphic field can never be the sole evidence of an amendment.
    if (
        amendment.get("evidence_is_only_polymorphic_field")
        and amendment.get("amendment_confirmed") is not False
    ):
        fails.append("amendment_confirmed_from_polymorphic_field_alone")
    if amendment.get("polymorphic_update_field") != POLYMORPHIC_UPDATE_FIELD:
        fails.append("polymorphic_field_warning_removed")

    return fails


def bridged_parse_statuses() -> frozenset[str]:
    """Gate 86's parse statuses, imported rather than redeclared."""
    return NORMALIZATION_PARSE_STATUSES
