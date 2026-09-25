"""Gate 181H — two thousand rows is not two thousand opportunities.

Measured on the live California statewide feed: 2,010 rows, of which 170 are
active, 1,838 closed and 2 forecasted. Quoting the row count would overstate
the open pipeline by more than 91%, and every row is real and well-formed, so
the overstatement would be invisible.

Offline. Live measurements are reported separately.
"""

from __future__ import annotations

import pytest

from nativeforge.services import structured_funding_feed_service as sf

#: The live feed's field names, supplied as configuration.
CA_MAP = {
    "status": "Status",
    "deadline": "ApplicationDeadline",
    "open_date": "OpenDate",
    "description": "Description",
    "purpose": "Purpose",
    "opportunity_id": "PortalID",
    "program_id": "GrantID",
    "applicant_type": "ApplicantType",
    "applicant_type_notes": "ApplicantTypeNotes",
    "geography": "Geography",
}

TODAY = "2026-09-25"


def row(**kw):
    base = {
        "PortalID": "191505",
        "GrantID": "",
        "Status": "active",
        "Title": "Increased Recycling of Empty Glass Beverage Containers",
        "ApplicationDeadline": "2026-10-29 23:59:00",
        "OpenDate": "2026-08-01",
        "ApplicantType": "Business; Nonprofit; Public Agency; Tribal Government",
        "MatchingFunds": "100%",
        "Geography": "Statewide",
        "Description": "",
        "Purpose": "",
    }
    base.update(kw)
    return base


def classify(**kw):
    return sf.classify_lifecycle(row(**kw), field_map=CA_MAP, as_of=TODAY)


# ---- 1/2/3/4. lifecycle from publisher status -------------------------


def test_1_a_dataset_row_is_not_an_open_opportunity():
    result = classify()
    assert result["a_dataset_row_is_not_an_open_opportunity"] is True


def test_2_active_is_open():
    result = classify(Status="active")
    assert result["lifecycle"] == sf.OPEN
    assert result["is_actionable"] is True
    assert result["classification_basis"] == "publisher_status"


def test_3_forecasted_is_upcoming_not_open():
    result = classify(Status="forecasted")
    assert result["lifecycle"] == sf.UPCOMING
    assert result["is_actionable"] is True
    assert result["lifecycle"] != sf.OPEN


def test_4_closed_is_closed_and_not_actionable():
    result = classify(Status="closed")
    assert result["lifecycle"] == sf.CLOSED
    assert result["is_actionable"] is False


def test_5_archived_is_not_actionable():
    result = classify(Status="archived")
    assert result["lifecycle"] == sf.ARCHIVED
    assert result["is_actionable"] is False


def test_6_awarded_rows_do_not_become_opportunities():
    result = classify(Status="awarded")
    assert result["lifecycle"] == sf.AWARD_INFORMATION
    assert result["is_actionable"] is False


def test_8_an_unrecognised_status_is_unknown_not_a_guess():
    result = classify(Status="under legislative review", ApplicationDeadline="")
    assert result["lifecycle"] == sf.UNKNOWN
    assert any("not_recognised" in r for r in result["reasons"])


# ---- 9/10. dates never overrule the publisher -------------------------


def test_10_a_future_deadline_does_not_reopen_a_closed_row():
    """The falsifiable half: deadline-only logic would say OPEN here."""
    result = classify(Status="closed", ApplicationDeadline="2027-12-31")
    assert result["lifecycle"] == sf.CLOSED
    assert result["classification_basis"] == "publisher_status"


def test_9_a_past_deadline_does_not_close_an_active_row():
    result = classify(Status="active", ApplicationDeadline="2020-01-01")
    assert result["lifecycle"] == sf.OPEN


def test_9_rolling_wording_stops_a_past_deadline_closing_it():
    result = classify(
        Status="",
        ApplicationDeadline="2020-01-01",
        Description="Applications are accepted on a rolling basis.",
    )
    assert result["rolling_language_present"] is True
    assert result["lifecycle"] == sf.UNKNOWN
    assert result["lifecycle"] != sf.CLOSED


def test_a_future_open_date_refines_open_to_upcoming():
    result = classify(Status="active", OpenDate="2027-01-01")
    assert result["lifecycle"] == sf.UPCOMING
    assert "open_date_is_in_the_future" in result["reasons"]


def test_deadline_only_is_labelled_as_such():
    result = classify(Status="", ApplicationDeadline="2027-01-01")
    assert result["lifecycle"] == sf.OPEN
    assert result["classification_basis"] == "deadline_only"


# ---- dates ------------------------------------------------------------


def test_a_date_without_a_timezone_does_not_gain_one():
    result = classify()
    assert result["deadline"]["parsed"] == "2026-10-29"
    assert result["deadline"]["has_timezone"] is False
    assert result["deadline"]["value"] == "2026-10-29 23:59:00"


def test_an_unparseable_date_is_unknown_with_evidence():
    result = classify(Status="", ApplicationDeadline="sometime next spring")
    assert result["deadline"]["parsed"] is None
    assert result["deadline"]["unparsed"] is True
    assert result["lifecycle"] == sf.UNKNOWN


# ---- 11/12. program identity is not opportunity identity --------------


def test_11_the_row_id_is_the_opportunity_and_the_program_id_is_not():
    identity = sf.build_record_identity(row(GrantID="CDFW-2026"), field_map=CA_MAP)
    assert identity["opportunity_key"] == "191505"
    assert identity["program_key"] == "CDFW-2026"
    assert identity["keyed_on"] == "opportunity_id"
    assert identity["program_key_is_not_opportunity_identity"] is True


def test_11_a_null_program_id_does_not_break_identity():
    """Observed live: the programme id is nullable."""
    identity = sf.build_record_identity(row(GrantID=""), field_map=CA_MAP)
    assert identity["opportunity_key"] == "191505"
    assert identity["program_key"] is None
    assert identity["has_opportunity_key"] is True


def test_12_two_rounds_of_one_program_stay_distinct():
    a = sf.build_record_identity(
        row(PortalID="191505", GrantID="P-1"), field_map=CA_MAP
    )
    b = sf.build_record_identity(
        row(PortalID="191506", GrantID="P-1"), field_map=CA_MAP
    )
    assert a["opportunity_key"] != b["opportunity_key"]
    assert a["program_key"] == b["program_key"]


# ---- 13/14. Native evidence, and the California trap ------------------


def test_13_a_declared_tribal_applicant_type_is_native_evidence():
    evidence = sf.extract_applicant_evidence(row(), field_map=CA_MAP)
    assert "tribal government" in evidence["native_applicant_tokens"]
    assert evidence["has_native_applicant_evidence"] is True
    assert "Tribal Government" in evidence["declared_applicant_types"]


def test_14_california_geography_alone_is_not_native_relevance():
    """THE trap. Statewide, rural, disadvantaged - none of it is Native."""
    evidence = sf.extract_applicant_evidence(
        row(ApplicantType="Public Agency; Nonprofit", Geography="Statewide; rural"),
        field_map=CA_MAP,
    )
    assert evidence["native_applicant_tokens"] == []
    assert evidence["has_native_applicant_evidence"] is False
    assert evidence["has_geography_only_signal"] is True
    assert evidence["geography_alone_is_not_native_relevance"] is True


def test_the_feed_layer_decides_neither_relevance_nor_eligibility():
    evidence = sf.extract_applicant_evidence(row(), field_map=CA_MAP)
    assert evidence["relevance_decided"] is False
    assert evidence["eligibility_decided"] is False
    assert evidence["applicant_type_is_not_a_tenant_eligibility_verdict"] is True


# ---- 15/16. matching funds --------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Not Required", sf.MATCH_NOT_REQUIRED),
        ("100%", sf.MATCH_REQUIRED),
        ("25%", sf.MATCH_REQUIRED),
        ("", sf.MATCH_UNKNOWN),
    ],
)
def test_15_match_normalization(raw, expected):
    assert sf.normalize_matching_funds(raw)["match_state"] == expected


def test_15_a_hedged_match_is_not_a_requirement():
    """'A match may be required' is not a match requirement."""
    result = sf.normalize_matching_funds("", notes="A match may be required.")
    assert result["match_state"] == sf.MATCH_UNKNOWN
    assert "hedged_wording_is_not_a_requirement" in result["reasons"]


def test_15_the_publishers_words_survive_normalization():
    result = sf.normalize_matching_funds("25%", notes="Cash or in-kind.")
    assert result["raw_value"] == "25%"
    assert result["raw_notes"] == "Cash or in-kind."
    assert result["match_percent"] == 25.0


def test_15_a_waiver_downgrades_a_requirement():
    result = sf.normalize_matching_funds(
        "Required", notes="A waiver is available for small entities."
    )
    assert result["match_state"] == sf.MATCH_WAIVER_AVAILABLE


def test_16_applicant_types_are_preserved_as_declared():
    evidence = sf.extract_applicant_evidence(row(), field_map=CA_MAP)
    assert evidence["declared_applicant_types"] == [
        "Business",
        "Nonprofit",
        "Public Agency",
        "Tribal Government",
    ]
    assert evidence["applicant_type_raw"].startswith("Business;")


# ---- 19. replay -------------------------------------------------------


def test_19_classification_is_deterministic():
    assert classify() == classify()


# ---- the headline: counts -------------------------------------------


def test_the_summary_refuses_to_let_row_count_pass_as_pipeline():
    classifications = (
        [classify(Status="closed")] * 1838
        + [classify(Status="active")] * 170
        + [classify(Status="forecasted")] * 2
    )
    summary = sf.summarize_feed(classifications)
    assert summary["row_count"] == 2010
    assert summary["actionable_count"] == 172
    assert summary["by_lifecycle"]["CLOSED"] == 1838
    assert summary["inflation_if_row_count_quoted"] == 1838
    assert summary["row_count_is_not_opportunity_count"] is True


# ---- genericity -------------------------------------------------------


def test_the_classifier_is_not_written_around_california():
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(sf))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, ast.FunctionDef):
            names.append(node.name)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    haystack = " ".join(names).lower()
    for leak in ("california", "portalid", "grantid", "data_ca", "ckan"):
        assert leak not in haystack, f"publisher-specific identifier: {leak}"


def test_another_states_field_names_work_unchanged():
    other_map = {
        "status": "state",
        "deadline": "due",
        "opportunity_id": "rowid",
        "applicant_type": "who_may_apply",
    }
    other_row = {
        "rowid": "ME-77",
        "state": "closed",
        "due": "2030-01-01",
        "who_may_apply": "Municipality; Tribal Government",
    }
    result = sf.classify_lifecycle(other_row, field_map=other_map, as_of=TODAY)
    assert result["lifecycle"] == sf.CLOSED
    identity = sf.build_record_identity(other_row, field_map=other_map)
    assert identity["opportunity_key"] == "ME-77"
    evidence = sf.extract_applicant_evidence(other_row, field_map=other_map)
    assert evidence["has_native_applicant_evidence"] is True
