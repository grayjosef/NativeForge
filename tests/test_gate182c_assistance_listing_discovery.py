"""Gate 182C — the money the applicant-type facet cannot see.

Measured live on 2026-09-25. A posted opportunity whose eligibility text reads

    "Eligible applicants are Tribes and Tribal organizations as described in
     the ICDBG regulations at 24 CFR 1003.5"

declares applicant type 25, "Others", and nothing else. Searching codes 07, 08
and 11 returns it zero times out of three. It carries $5,000,000 in estimated
funding and a $1,500,000 ceiling, and its programme's assistance listing finds
it immediately.

So eligibility discovery is necessary and is not sufficient. Those figures are
dated observations and appear in no assertion; what is asserted is that a
Tribes-only opportunity hiding behind "Others" still arrives.

Every test is offline. The transport is injected.
"""

from __future__ import annotations

import pytest

from nativeforge.services import grants_gov_search_api_adapter_service as gg

# ---- fixtures ---------------------------------------------------------

#: The real record, reduced to the fields that matter. Applicant type 25 and
#: nothing else, which is the entire problem.
HIDDEN_BY_OTHERS = {
    "id": "358716",
    "number": "FR-6900-N-74",
    "title": (
        "Application Instructions for the Indian Community Development Block "
        "Grant (ICDBG) Imminent Threat"
    ),
    "agencyCode": "HUD",
    "oppStatus": "posted",
    "closeDate": "09/30/2026",
    "eligibilities": ["25"],
    "alnist": ["14.862"],
}

#: A record that DOES declare a Tribal applicant type, so both paths find it.
DECLARED_TRIBAL = {
    "id": "362464",
    "number": "PIH-2600-DC-0034",
    "title": "Community Development Block Grant Program for Indian Tribes",
    "agencyCode": "HUD",
    "oppStatus": "forecasted",
    "eligibilities": ["07", "11"],
    "alnist": ["14.862"],
}


def response(hits, hit_count=None):
    return {
        "errorcode": 0,
        "msg": "success",
        "data": {
            "hitCount": hit_count if hit_count is not None else len(hits),
            "oppHits": list(hits),
        },
    }


def transport(payload, capture=None):
    def _post(url, body):
        if capture is not None:
            capture.append((url, body))
        return payload

    return _post


# ---- the request contract ---------------------------------------------


def test_the_body_carries_the_listing_and_no_keyword():
    """No keyword, for the same reason the eligibility body carries none."""
    body = gg.build_grants_gov_assistance_listing_search_body(
        assistance_listing="14.862"
    )
    assert body["cfda"] == "14.862"
    assert "keyword" not in body
    assert "eligibilities" not in body


def test_the_body_carries_no_eligibility_filter():
    """Adding one reinstates the exact blind spot this path exists to cover."""
    body = gg.build_grants_gov_assistance_listing_search_body(
        assistance_listing="14.867", opp_statuses="posted|forecasted"
    )
    assert "eligibilities" not in body
    assert body["oppStatuses"] == "posted|forecasted"


def test_paging_is_explicit():
    body = gg.build_grants_gov_assistance_listing_search_body(
        assistance_listing="14.862", rows=25, start_record_num=50
    )
    assert body["rows"] == 25
    assert body["startRecordNum"] == 50


@pytest.mark.parametrize(
    "good", ["14.862", "14.867", "93.933", "93.00K", "93.00E", "93.00L", "93.00p"]
)
def test_a_listing_whose_last_character_is_a_letter_is_accepted(good):
    """^\\d{2}\\.\\d{3}$ was written against one agency and refused a second.

    93.00K, 93.00E, 93.00F, 93.00G, 93.00L and 93.00P are live listings the
    publisher's own filter accepts and that carry current opportunities. The
    stricter pattern raised ValueError on every one, so those programmes could
    not even be asked about - a refusal that looks like an empty programme.
    """
    body = gg.build_grants_gov_assistance_listing_search_body(assistance_listing=good)
    assert body["cfda"] == good


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "14.86",
        "1.867",
        "14.8672",
        "NONSENSE",
        "14-862",
        "cfda",
        "  ",
        "93.0K",
        "93.00KK",
        "9.300K",
    ],
)
def test_a_malformed_listing_is_refused_rather_than_asked(bad):
    """The filter returns 0 for anything it does not recognise.

    "99.999" and "NONSENSE" both come back empty, exactly as a genuinely
    unfunded programme would. A typo must not be allowed to look like a
    finding about the programme.
    """
    with pytest.raises(ValueError):
        gg.build_grants_gov_assistance_listing_search_body(assistance_listing=bad)


def test_a_well_formed_listing_is_accepted():
    assert (
        gg.build_grants_gov_assistance_listing_search_body(assistance_listing="14.862")[
            "cfda"
        ]
        == "14.862"
    )


def test_the_listing_reaches_the_wire_unchanged():
    capture: list = []
    gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.862",
        http_post=transport(response([HIDDEN_BY_OTHERS]), capture=capture),
    )
    assert capture[0][0] == gg.SEARCH2_URL
    assert capture[0][1]["cfda"] == "14.862"


# ---- the record the eligibility facet cannot see ----------------------


def test_a_tribes_only_opportunity_declaring_others_still_arrives():
    result = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.862",
        http_post=transport(response([HIDDEN_BY_OTHERS])),
    )
    assert result["outcome"] == gg.OUTCOME_HITS
    assert result["hit_count"] == 1
    assert result["opp_hits"][0]["number"] == "FR-6900-N-74"


def test_the_declared_applicant_types_are_preserved_not_corrected():
    """25 is what the publisher said. Recording 07 because the eligibility
    prose names Tribes would be inventing the publisher's own metadata."""
    result = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.862",
        http_post=transport(response([HIDDEN_BY_OTHERS])),
    )
    evidence = result["opp_hits"][0]["nf_program_evidence"]
    assert evidence["declared_applicant_types"] == ["25"]
    assert evidence["applicant_types_present_in_response"] is True


def test_absent_applicant_types_are_unknown_not_empty():
    """The live search response carries no applicant types at all.

    Reporting [] for that reads as "declares no applicant types", which is
    indistinguishable from the real answer for the record this path exists to
    find - so the blind spot would be recreated inside the fix for it.
    """
    without = {k: v for k, v in HIDDEN_BY_OTHERS.items() if k != "eligibilities"}
    result = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.862", http_post=transport(response([without]))
    )
    evidence = result["opp_hits"][0]["nf_program_evidence"]
    assert evidence["declared_applicant_types"] is None
    assert evidence["applicant_types_present_in_response"] is False


def test_the_basis_is_programme_not_eligibility():
    """Arriving by assistance listing says the publisher filed this under a
    programme. It says nothing whatever about who may apply."""
    result = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.862",
        http_post=transport(response([HIDDEN_BY_OTHERS])),
    )
    evidence = result["opp_hits"][0]["nf_program_evidence"]
    assert evidence["native_relevance_basis"] == "PROGRAM"
    assert evidence["discovered_by"] == "assistance_listing"


def test_arrival_is_not_a_relevance_or_eligibility_verdict():
    result = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.862",
        http_post=transport(response([HIDDEN_BY_OTHERS, DECLARED_TRIBAL])),
    )
    for hit in result["opp_hits"]:
        evidence = hit["nf_program_evidence"]
        assert evidence["native_relevance_decided"] is False
        assert evidence["tenant_eligibility_decided"] is False


def test_the_search_body_is_carried_for_audit():
    result = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.867",
        http_post=transport(response([])),
    )
    assert result["search_body"]["cfda"] == "14.867"


# ---- failure never becomes emptiness -----------------------------------


def test_an_empty_programme_is_empty_not_an_error():
    result = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.867", http_post=transport(response([]))
    )
    assert result["outcome"] == gg.OUTCOME_EMPTY
    assert result["hit_count"] == 0
    assert result["search_live"] is True


def test_a_transport_failure_is_not_an_empty_programme():
    def boom(url, body):
        raise RuntimeError("connection reset")

    result = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.862", http_post=boom
    )
    assert result["outcome"] == gg.OUTCOME_FETCH_ERROR
    assert result["search_live"] is False
    assert "connection reset" in result["api_error"]


def test_an_api_error_code_is_not_an_empty_programme():
    bad = {"errorcode": 1, "msg": "bad request", "data": {}}
    result = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.862", http_post=transport(bad)
    )
    assert result["outcome"] == gg.OUTCOME_FETCH_ERROR
    assert result["hit_count"] == 0


def test_a_malformed_envelope_does_not_crash():
    result = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.862",
        http_post=transport({"errorcode": 0, "data": {"oppHits": [None, "junk"]}}),
    )
    assert result["hit_count"] == 0


def test_an_authorization_refusal_is_raised_not_returned():
    """ "Not permitted to ask" is never "this programme has no funding"."""
    from nativeforge.services.hermetic_test_guard_service import (
        LiveNetworkBlockedError,
    )

    def blocked(url, body):
        raise LiveNetworkBlockedError("hermetic guard")

    with pytest.raises(LiveNetworkBlockedError):
        gg.search_grants_gov_by_assistance_listing(
            assistance_listing="14.862", http_post=blocked
        )


def test_nothing_is_ever_synthesized():
    result = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.862",
        http_post=transport(response([HIDDEN_BY_OTHERS])),
    )
    assert result["never_synthesized"] is True


def test_the_publishers_total_is_reported_separately_from_the_page():
    result = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.862",
        http_post=transport(response([HIDDEN_BY_OTHERS], hit_count=20)),
    )
    assert result["hit_count"] == 1
    assert result["total_hit_count"] == 20


# ---- the coverage gap, measured rather than believed ------------------


def test_the_gap_names_what_eligibility_discovery_missed():
    gap = gg.eligibility_facet_coverage_gap(
        eligibility_opportunity_numbers=["PIH-ROSS-26-001", "CPD-2600-DC-0025"],
        assistance_listing_opportunity_numbers=["FR-6900-N-74"],
    )
    assert gap["missed_by_eligibility_facet"] == ["FR-6900-N-74"]
    assert gap["missed_count"] == 1
    assert gap["eligibility_facet_is_sufficient"] is False


def test_no_gap_is_reported_honestly_as_no_gap():
    gap = gg.eligibility_facet_coverage_gap(
        eligibility_opportunity_numbers=["A", "B"],
        assistance_listing_opportunity_numbers=["A"],
    )
    assert gap["missed_count"] == 0
    assert gap["eligibility_facet_is_sufficient"] is True


def test_overlap_is_counted_not_double_counted():
    gap = gg.eligibility_facet_coverage_gap(
        eligibility_opportunity_numbers=["A", "B", "B"],
        assistance_listing_opportunity_numbers=["B", "C"],
    )
    assert gap["found_by_eligibility"] == 2
    assert gap["found_by_assistance_listing"] == 2
    assert gap["found_by_both"] == 1
    assert gap["missed_by_eligibility_facet"] == ["C"]


def test_blank_identifiers_are_dropped_rather_than_counted():
    gap = gg.eligibility_facet_coverage_gap(
        eligibility_opportunity_numbers=["", None],
        assistance_listing_opportunity_numbers=["A", ""],
    )
    assert gap["found_by_eligibility"] == 0
    assert gap["missed_by_eligibility_facet"] == ["A"]


def test_the_gap_states_the_direction_that_matters():
    gap = gg.eligibility_facet_coverage_gap(
        eligibility_opportunity_numbers=[],
        assistance_listing_opportunity_numbers=[],
    )
    assert gap["a_missed_opportunity_is_invisible_to_the_customer"] is True


# ---- the two paths together -------------------------------------------


def test_the_two_discovery_paths_are_complementary_not_redundant():
    """Both find the record that declares 07. Only the listing finds the one
    that declares 25."""
    by_listing = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.862",
        http_post=transport(response([HIDDEN_BY_OTHERS, DECLARED_TRIBAL])),
    )
    listing_numbers = [h["number"] for h in by_listing["opp_hits"]]
    eligibility_numbers = [DECLARED_TRIBAL["number"]]

    gap = gg.eligibility_facet_coverage_gap(
        eligibility_opportunity_numbers=eligibility_numbers,
        assistance_listing_opportunity_numbers=listing_numbers,
    )
    assert gap["found_by_both"] == 1
    assert gap["missed_by_eligibility_facet"] == ["FR-6900-N-74"]


def test_the_tribal_eligibility_codes_are_unchanged_by_this_path():
    """This path complements those codes. It does not replace or edit them."""
    assert gg.TRIBAL_ELIGIBILITY_CODES == ("07", "08", "11")


def test_replay_is_deterministic():
    payload = response([HIDDEN_BY_OTHERS])
    first = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.862", http_post=transport(payload)
    )
    second = gg.search_grants_gov_by_assistance_listing(
        assistance_listing="14.862", http_post=transport(payload)
    )
    assert first == second
