"""Gate 170: change intelligence.

Hermetic. The taxonomy and materiality are pure rules over two values, which
is the point: the classifications that matter most are the severe ones, and a
severity that needs a fixture to reach is one nobody has argued with.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from nativeforge.repositories.canonical_opportunity_batch_repository import (
    deadline_shape_for,
)
from nativeforge.repositories.opportunity_change_repository import (
    CONFLICT_STATES,
    ChangeWriteRefused,
    build_change_event_id,
    resolve_conflict,
)
from nativeforge.services.opportunity_change_read_model_service import (
    CUSTOMER_FIELDS,
    EXPLANATIONS,
    FORBIDDEN_MARKERS,
    HEALTH_CONDITIONS,
    IMPORTANCE,
    change_health_invariant_failures,
    read_model_invariant_failures,
)
from nativeforge.services.opportunity_change_taxonomy_service import (
    CHANGE_TYPES,
    CRITICAL,
    INFORMATIONAL,
    MATERIAL,
    MATERIALITY_BY_TYPE,
    MATERIALITY_CLASSES,
    NON_MATERIAL,
    UNKNOWN,
    change_invariant_failures,
    classify_change,
    classify_deadline_move,
    describe_taxonomy,
    parse_date,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
MIGRATION = REPO / "alembic" / "versions" / "0055_change_intelligence.py"


# ------------------------------------------------- deadline direction


def test_a_shortened_deadline_is_critical():
    """The single most consequential classification in this gate."""
    change = classify_change(
        field_name="close_date", prior_value="10/15/2026", new_value="09/01/2026"
    )
    assert change["change_type"] == "DEADLINE_SHORTENED"
    assert change["materiality"] == CRITICAL
    assert change["materiality_rule"]


def test_an_extended_deadline_is_material_but_not_critical():
    change = classify_change(
        field_name="close_date", prior_value="10/15/2026", new_value="12/01/2026"
    )
    assert change["change_type"] == "DEADLINE_EXTENDED"
    assert change["materiality"] == MATERIAL


def test_direction_produces_different_types():
    """One DEADLINE_CHANGED type would force both into the same alert."""
    shorter = classify_change(
        field_name="close_date", prior_value="10/15/2026", new_value="09/01/2026"
    )
    longer = classify_change(
        field_name="close_date", prior_value="10/15/2026", new_value="12/01/2026"
    )
    assert shorter["change_type"] != longer["change_type"]
    assert shorter["materiality"] != longer["materiality"]


def test_an_unparseable_date_admits_ignorance():
    """A guessed direction with an alert attached is worse than no direction."""
    change_type, why = classify_deadline_move("sometime in spring", "later")
    assert change_type == "DEADLINE_CHANGED"
    assert "could_not_be_parsed" in why


def test_the_days_moved_are_named_in_the_reason():
    change = classify_change(
        field_name="close_date", prior_value="10/15/2026", new_value="10/20/2026"
    )
    assert any("5_days" in r for r in change["reasons"])


@pytest.mark.parametrize(
    "raw", ["10/15/2026", "2026-10-15", "October 15, 2026", "15 October 2026"]
)
def test_published_date_formats_parse(raw):
    assert parse_date(raw) is not None


@pytest.mark.parametrize("raw", ["", None, "rolling", "TBD", "see notice"])
def test_unparseable_dates_return_none_rather_than_guessing(raw):
    assert parse_date(raw) is None


# ------------------------------------------------- lifecycle


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        ("forecasted", "posted", "FORECAST_TO_POSTED"),
        ("posted", "closed", "POSTED_TO_CLOSED"),
        ("closed", "posted", "REOPENED"),
        ("posted", "cancelled", "CANCELLED"),
    ],
)
def test_named_status_transitions(before, after, expected):
    change = classify_change(
        field_name="status", prior_value=before, new_value=after
    )
    assert change["change_type"] == expected


def test_an_unmodelled_transition_is_a_plain_status_change_not_a_guess():
    change = classify_change(
        field_name="status", prior_value="posted", new_value="something_new"
    )
    assert change["change_type"] == "STATUS_CHANGED"


# ------------------------------------------------- materiality rules


def test_every_change_type_has_a_materiality_and_a_rule():
    described = describe_taxonomy()
    assert described["every_type_is_classified"] is True
    assert described["types_without_a_rule"] == []
    assert described["llm_used"] is False


def test_every_materiality_is_in_the_vocabulary():
    for name, (materiality, _rule) in MATERIALITY_BY_TYPE.items():
        assert materiality in MATERIALITY_CLASSES, name


def test_losing_something_outranks_gaining_it():
    """The asymmetry is deliberate and runs through the whole table."""
    assert MATERIALITY_BY_TYPE["DOCUMENT_REMOVED"][0] == CRITICAL
    assert MATERIALITY_BY_TYPE["DOCUMENT_ADDED"][0] == INFORMATIONAL


def test_a_first_sighting_is_never_an_amendment():
    change = classify_change(
        field_name="close_date", new_value="10/15/2026", is_first_observation=True
    )
    assert change["change_type"] == "FIRST_OBSERVED"
    assert change["materiality"] == NON_MATERIAL


def test_a_cosmetic_title_edit_is_not_material():
    change = classify_change(
        field_name="title",
        prior_value="Tribal Water Program",
        new_value="Tribal  Water   Program!",
    )
    assert change["materiality"] == NON_MATERIAL


def test_a_substantive_title_edit_is_informational():
    change = classify_change(
        field_name="title",
        prior_value="Tribal Water Program",
        new_value="Tribal Broadband Program",
    )
    assert change["materiality"] == INFORMATIONAL


def test_an_assistance_listing_change_is_not_a_document_removal():
    """A CFDA number is a program code, not an attachment.

    Reusing DOCUMENT_REMOVED here reported a dropped listing as CRITICAL
    because "a required document is no longer available" - the wrong reason
    for the wrong severity.
    """
    change = classify_change(
        field_name="assistance_listings",
        prior_value='["16.1", "16.2"]',
        new_value='["16.1"]',
    )
    assert change["change_type"] == "ASSISTANCE_LISTINGS_CHANGED"
    assert change["materiality"] == INFORMATIONAL


def test_an_unmodelled_field_is_unknown_rather_than_invented():
    change = classify_change(
        field_name="some_future_field", prior_value="a", new_value="b"
    )
    assert change["change_type"] == "UNKNOWN_CHANGE"
    assert change["materiality"] == UNKNOWN


def test_no_llm_decided_anything():
    change = classify_change(
        field_name="close_date", prior_value="10/15/2026", new_value="09/01/2026"
    )
    assert change["llm_used"] is False
    assert change["decided_by"] == "deterministic_rules"


# ------------------------------------------------- invariants


def test_the_invariant_catches_a_downgraded_shortened_deadline():
    change = classify_change(
        field_name="close_date", prior_value="10/15/2026", new_value="09/01/2026"
    )
    change["materiality"] = INFORMATIONAL
    assert any(
        "shortened_deadline_not_critical" in f
        for f in change_invariant_failures(change)
    )


def test_the_invariant_catches_a_downgraded_cancellation():
    change = classify_change(
        field_name="status", prior_value="posted", new_value="cancelled"
    )
    change["materiality"] = NON_MATERIAL
    assert any(
        "cancellation_not_critical" in f for f in change_invariant_failures(change)
    )


def test_the_invariant_catches_a_materiality_with_no_rule():
    change = classify_change(
        field_name="close_date", prior_value="10/15/2026", new_value="09/01/2026"
    )
    change["materiality_rule"] = None
    assert any(
        "materiality_without_a_named_rule" in f
        for f in change_invariant_failures(change)
    )


def test_the_invariant_catches_a_first_observation_treated_as_material():
    change = classify_change(
        field_name="close_date", new_value="10/15/2026", is_first_observation=True
    )
    change["materiality"] = CRITICAL
    assert any(
        "first_observation_treated_as_an_amendment" in f
        for f in change_invariant_failures(change)
    )


def test_the_invariant_catches_an_llm_decision():
    change = classify_change(field_name="title", prior_value="a", new_value="b")
    change["llm_used"] = True
    assert "an_llm_decided_a_change_classification" in (
        change_invariant_failures(change)
    )


def test_the_invariant_catches_a_reasonless_change():
    change = classify_change(field_name="title", prior_value="a", new_value="b")
    change["reasons"] = []
    assert "change_named_no_reason" in change_invariant_failures(change)


# ------------------------------------------------- deadline shapes


@pytest.mark.parametrize("shape", ["dual", "per_region", "phased"])
def test_a_multi_valued_shape_says_it_is_one_of_several(shape):
    """A regional change must never read as a national date moving."""
    change = classify_change(
        field_name="close_date",
        prior_value="10/15/2026",
        new_value="09/01/2026",
        deadline_shape=shape,
    )
    assert any("one_of_several_deadlines" in r for r in change["reasons"])
    assert change["deadline_shape"] == shape


def test_a_single_shape_is_not_flagged_as_multi_valued():
    change = classify_change(
        field_name="close_date",
        prior_value="10/15/2026",
        new_value="09/01/2026",
        deadline_shape="single",
    )
    assert not any("one_of_several" in r for r in change["reasons"])


def test_the_shape_is_derivable_from_the_fields():
    assert deadline_shape_for({"close_date": "10/15/2026"}) == "single"
    assert deadline_shape_for({}) == "unknown"


# ------------------------------------------------- event identity


def test_event_ids_are_derived_and_stable():
    first = build_change_event_id(
        canonical_id="L1:A|synopsis",
        prior_version_id="v1",
        new_version_id="v2",
        field_name="close_date",
    )
    second = build_change_event_id(
        canonical_id="L1:A|synopsis",
        prior_version_id="v1",
        new_version_id="v2",
        field_name="close_date",
    )
    assert first == second


def test_a_different_field_is_a_different_event():
    a = build_change_event_id(
        canonical_id="c", prior_version_id="v1", new_version_id="v2", field_name="x"
    )
    b = build_change_event_id(
        canonical_id="c", prior_version_id="v1", new_version_id="v2", field_name="y"
    )
    assert a != b


def test_a_first_observation_has_no_prior_version_in_its_id():
    with_none = build_change_event_id(
        canonical_id="c",
        prior_version_id=None,
        new_version_id="v1",
        field_name="title",
    )
    with_sentinel = build_change_event_id(
        canonical_id="c",
        prior_version_id="none",
        new_version_id="v1",
        field_name="title",
    )
    assert with_none != with_sentinel


# ------------------------------------------------- schema rules


def _literal_text(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(_literal_text(p) for p in node.values)
    if isinstance(node, ast.FormattedValue):
        return "<interpolated>"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _literal_text(node.left) + _literal_text(node.right)
    return ""


def _check_expressions() -> list[str]:
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", "") or getattr(node.func, "id", "")
        if name not in ("CheckConstraint", "create_check_constraint"):
            continue
        for argument in node.args:
            text = _literal_text(argument)
            if text:
                found.append(text)
    return found


def test_a_materiality_without_a_rule_is_unrepresentable():
    expressions = _check_expressions()
    assert any(
        "materiality_rule" in e and "UNKNOWN" in e for e in expressions
    ), expressions


def test_a_change_event_must_name_its_evidence():
    expressions = _check_expressions()
    assert any(
        "length(raw_payload_sha256) = 64" in e for e in expressions
    ), expressions


def test_a_conflict_resolution_needs_a_signer_and_evidence():
    expressions = _check_expressions()
    assert any(
        "RESOLVED_CONFLICT" in e
        and "resolved_by" in e
        and "resolution_evidence_json" in e
        for e in expressions
    ), expressions


def test_a_conflict_needs_two_sides():
    expressions = _check_expressions()
    assert any(
        "competing_source_count >= 2" in e for e in expressions
    ), expressions


def test_an_event_between_one_version_and_itself_is_unrepresentable():
    expressions = _check_expressions()
    assert any(
        "prior_version_id <> new_version_id" in e for e in expressions
    ), expressions


# ------------------------------------------------- write refusals


def test_an_unsigned_conflict_resolution_is_refused():
    with pytest.raises(ChangeWriteRefused) as caught:
        resolve_conflict(
            connection=None,
            canonical_id="c",
            field_name="close_date",
            resolved_by="",
            rule="",
            evidence={"a": 1},
        )
    assert any("name_who_and_by_what_rule" in r for r in caught.value.reasons)


def test_a_resolution_without_evidence_is_refused():
    with pytest.raises(ChangeWriteRefused) as caught:
        resolve_conflict(
            connection=None,
            canonical_id="c",
            field_name="close_date",
            resolved_by="MAYHEM",
            rule="federal_wins",
            evidence=None,
        )
    assert "a_resolution_must_carry_evidence" in caught.value.reasons


def test_every_conflict_state_is_in_the_vocabulary():
    assert set(CONFLICT_STATES) == {
        "NO_CONFLICT",
        "OPEN_CONFLICT",
        "RESOLVED_CONFLICT",
        "REVIEW_REQUIRED",
    }


# ------------------------------------------------- customer safety


def test_every_change_type_has_a_customer_explanation():
    for name in CHANGE_TYPES:
        assert name in EXPLANATIONS, name


def test_the_rule_name_is_not_a_customer_field():
    """Engineers argue with the rule; customers read the explanation."""
    assert "materiality_rule" not in CUSTOMER_FIELDS
    assert "materiality_rule" in FORBIDDEN_MARKERS
    assert "explanation" in CUSTOMER_FIELDS


def test_internal_identifiers_are_not_customer_fields():
    for name in ("change_event_id", "new_version_id", "raw_payload_sha256"):
        assert name not in CUSTOMER_FIELDS
        assert name in FORBIDDEN_MARKERS


def test_importance_is_customer_vocabulary_not_internal_classes():
    assert set(IMPORTANCE) == set(MATERIALITY_CLASSES)
    for value in IMPORTANCE.values():
        assert value not in MATERIALITY_CLASSES


def test_the_read_model_invariant_catches_a_leak():
    feed = {
        "changes": [],
        "customer_safe": True,
        "forbidden_markers_found": ["raw_payload_sha256"],
        "notifications_sent": 0,
    }
    failures = read_model_invariant_failures(feed)
    assert any("forbidden_marker_in_output" in f for f in failures)


def test_the_read_model_invariant_catches_a_key_outside_the_allowlist():
    feed = {
        "changes": [{"opportunity_title": "x", "internal_id": "y"}],
        "customer_safe": True,
        "forbidden_markers_found": [],
        "notifications_sent": 0,
    }
    assert any(
        "key_outside_the_allowlist" in f
        for f in read_model_invariant_failures(feed)
    )


def test_the_read_model_invariant_catches_a_sent_notification():
    feed = {
        "changes": [],
        "customer_safe": True,
        "forbidden_markers_found": [],
        "notifications_sent": 1,
    }
    assert "this_gate_sent_a_notification" in read_model_invariant_failures(feed)


# ------------------------------------------------- health


def test_all_twelve_health_conditions_are_declared():
    assert len(HEALTH_CONDITIONS) == 12
    assert len(set(HEALTH_CONDITIONS)) == 12


def test_health_refuses_readiness_with_an_unmet_condition():
    health = {
        "conditions": dict.fromkeys(HEALTH_CONDITIONS, True)
        | {"materiality_rules_named": False},
        "change_intelligence_ready": True,
        "named_gaps": [],
    }
    assert any(
        "ready_with_unmet_conditions" in f
        for f in change_health_invariant_failures(health)
    )


def test_health_refuses_readiness_while_naming_a_gap():
    health = {
        "conditions": dict.fromkeys(HEALTH_CONDITIONS, True),
        "change_intelligence_ready": True,
        "named_gaps": ["deadline_change_with_no_recorded_shape:1"],
    }
    assert any(
        "ready_with_named_gaps" in f
        for f in change_health_invariant_failures(health)
    )


def test_health_refuses_a_condition_it_did_not_measure():
    health = {
        "conditions": {"version_chain_valid": True},
        "change_intelligence_ready": False,
        "named_gaps": ["x"],
    }
    assert any(
        "condition_not_measured" in f
        for f in change_health_invariant_failures(health)
    )
