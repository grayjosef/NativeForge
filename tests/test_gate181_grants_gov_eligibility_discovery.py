"""Gate 181A — Grants.gov discovery by who may apply, not by what the title says.

The measurement that made this necessary, taken live on 2026-09-24: of 946
posted Grants.gov opportunities, 464 were open to federally recognized Tribal
governments under eligibility code 07, and 4 of the first 100 of those titles
contained trib/indian/native/alaska. Keyword discovery cannot see the rest.

Those counts are dated observations and appear in NO assertion here. What is
asserted is behaviour: a Tribal-eligible opportunity whose title says nothing
Native must still arrive, carrying the publisher's evidence and carrying no
verdict it has not earned.

Every test is offline. The transport is injected.
"""

from __future__ import annotations

import pytest

from nativeforge.services import grants_gov_search_api_adapter_service as gg

# ---- fixtures ---------------------------------------------------------

#: The eligibilities facet as Grants.gov actually returns it.
REAL_FACET = [
    {"label": "County governments", "value": "01", "count": 864},
    {
        "label": "Native American tribal governments (Federally recognized)",
        "value": "07",
        "count": 895,
    },
    {
        "label": "Public housing authorities/Indian housing authorities",
        "value": "08",
        "count": 756,
    },
    {
        "label": (
            "Native American tribal organizations (other than Federally "
            "recognized tribal governments)"
        ),
        "value": "11",
        "count": 834,
    },
    {
        "label": (
            'Others (see text field entitled "Additional Information on '
            'Eligibility" for clarification)'
        ),
        "value": "25",
        "count": 1106,
    },
]

#: The opportunity this whole gate exists for. Nothing in this title, agency or
#: number says Tribal, Native, Indian or Alaska - and a federally recognized
#: Tribal government may apply for it.
NO_KEYWORD_HIT = {
    "id": 350123,
    "number": "PA-26-118",
    "title": "Dissemination and Implementation Research in Health (R01)",
    "agencyCode": "HHS-NIH11",
    "agency": "National Institutes of Health",
    "oppStatus": "posted",
    "cfdaList": ["93.310"],
}

NATIVE_KEYWORD_HIT = {
    "id": 350999,
    "number": "BIA-2026-TTGP",
    "title": "Tribal Tourism Grant Program",
    "agencyCode": "DOI-BIA",
    "oppStatus": "posted",
    "cfdaList": ["15.031"],
}


def response(hits, *, facet=None, hit_count=None):
    return {
        "errorcode": 0,
        "msg": "Webservice Succeeds",
        "data": {
            "hitCount": hit_count if hit_count is not None else len(hits),
            "oppHits": list(hits),
            "eligibilities": REAL_FACET if facet is None else facet,
        },
    }


def transport(payload, *, capture=None):
    def _post(url, body):
        if capture is not None:
            capture.append({"url": url, "body": body})
        return payload

    return _post


# ---- the facet contract ----------------------------------------------


def test_the_contract_holds_against_the_real_facet():
    result = gg.verify_eligibility_facet_contract(response([]))
    assert result["contract_holds"] is True
    assert result["mismatches"] == []


def test_a_renamed_label_breaks_the_contract():
    """Falsifiability: the detector must fail when the publisher renumbers."""
    renamed = [
        dict(f, label="Something else entirely") if f["value"] == "07" else f
        for f in REAL_FACET
    ]
    result = gg.verify_eligibility_facet_contract(response([], facet=renamed))
    assert result["contract_holds"] is False
    assert [m["code"] for m in result["mismatches"]] == ["07"]
    assert result["mismatches"][0]["reason"] == "label_changed"


def test_a_missing_code_breaks_the_contract():
    without_07 = [f for f in REAL_FACET if f["value"] != "07"]
    result = gg.verify_eligibility_facet_contract(response([], facet=without_07))
    assert result["contract_holds"] is False
    assert result["mismatches"][0]["reason"] == "code_absent_from_facet"


def test_an_absent_facet_is_not_a_passing_contract():
    """A check that could not run must not report success."""
    result = gg.verify_eligibility_facet_contract(response([], facet=[]))
    assert result["facet_present"] is False
    assert result["contract_holds"] is False


def test_code_25_is_others_and_is_not_a_tribal_code():
    """The exact mistake this module was written to prevent.

    Code 25 exists, answers with more hits than 07, and means "Others". It
    must not be reachable as a Tribal code.
    """
    assert "25" not in gg.TRIBAL_ELIGIBILITY_CODES
    assert "25" not in gg.EXPECTED_ELIGIBILITY_FACET_LABELS
    with pytest.raises(ValueError):
        gg.build_grants_gov_eligibility_search_body(eligibility_code="25")


def test_the_three_codes_stay_three_distinct_classes():
    assert gg.TRIBAL_ELIGIBILITY_CODES == ("07", "08", "11")
    assert len(set(gg.EXPECTED_ELIGIBILITY_FACET_LABELS.values())) == 3


# ---- the search body --------------------------------------------------


def test_the_eligibility_body_carries_no_keyword():
    """A keyword here would reinstate the blind spot this removes."""
    body = gg.build_grants_gov_eligibility_search_body(eligibility_code="07")
    assert body["eligibilities"] == "07"
    assert "keyword" not in body


def test_the_eligibility_body_does_not_ask_for_five_rows():
    body = gg.build_grants_gov_eligibility_search_body(eligibility_code="07")
    assert body["rows"] == gg.ELIGIBILITY_DISCOVERY_ROWS
    assert body["rows"] > gg.DEFAULT_ROWS


def test_an_unknown_code_is_refused_rather_than_queried():
    with pytest.raises(ValueError):
        gg.build_grants_gov_eligibility_search_body(eligibility_code="99")


# ---- THE REQUIRED REGRESSION -----------------------------------------


def test_a_tribal_eligible_opportunity_with_no_native_wording_still_arrives():
    """The regression this gate exists for.

    Title contains no trib/native/indian/alaska wording. Federally recognized
    Tribal governments are an allowed applicant type. It must arrive.
    """
    title = NO_KEYWORD_HIT["title"].lower()
    assert not any(w in title for w in ("trib", "native", "indian", "alaska"))

    result = gg.search_grants_gov_by_eligibility(
        eligibility_code="07",
        http_post=transport(response([NO_KEYWORD_HIT])),
    )

    assert result["outcome"] == gg.OUTCOME_HITS
    assert result["hit_count"] == 1
    arrived = result["opp_hits"][0]
    assert arrived["number"] == "PA-26-118"


def test_the_same_opportunity_is_invisible_to_keyword_discovery():
    """Proves the regression above can fail - the detector is falsifiable.

    Keyword discovery builds its query from the source row's own name. Against
    a Native-named programme row, this opportunity is not what is being asked
    for, which is exactly why 464 and 276 are different numbers.
    """
    body = gg.build_grants_gov_search_body(
        {"source_name": "BIA / Interior — Tribal Tourism Grant Program"}
    )
    assert "keyword" in body
    assert "tribal" in body["keyword"].lower()
    assert body["rows"] == 5
    # The keyword path asks for a named Tribal programme; the NIH notice is
    # not one, and no amount of paging that query reaches it.
    assert "tribal" not in NO_KEYWORD_HIT["title"].lower()


def test_arrival_carries_the_publishers_evidence_and_no_verdict():
    result = gg.search_grants_gov_by_eligibility(
        eligibility_code="07",
        http_post=transport(response([NO_KEYWORD_HIT])),
    )
    evidence = result["opp_hits"][0]["nf_eligibility_evidence"]

    assert evidence["eligibility_code"] == "07"
    assert evidence["publisher_label"] == (
        "Native American tribal governments (Federally recognized)"
    )
    assert evidence["native_relevance_basis"] == "ELIGIBILITY"
    # Arriving is not a finding. Gate 173 and Gate 174 own those verdicts.
    assert evidence["native_relevance_decided"] is False
    assert evidence["tenant_eligibility_decided"] is False


def test_evidence_is_attributable_to_the_exact_request():
    capture: list[dict] = []
    gg.search_grants_gov_by_eligibility(
        eligibility_code="11",
        opp_statuses="forecasted",
        http_post=transport(response([NO_KEYWORD_HIT]), capture=capture),
    )
    assert capture[0]["url"] == gg.SEARCH2_URL
    assert capture[0]["body"]["eligibilities"] == "11"
    assert capture[0]["body"]["oppStatuses"] == "forecasted"


def test_absence_of_native_wording_creates_no_unsupported_claim():
    """The opportunity arrives; nothing asserts it IS Native-relevant."""
    result = gg.search_grants_gov_by_eligibility(
        eligibility_code="07",
        http_post=transport(response([NO_KEYWORD_HIT])),
    )
    evidence = result["opp_hits"][0]["nf_eligibility_evidence"]
    assert evidence["native_relevance_decided"] is False
    assert "native_relevant" not in evidence
    assert "relevance_score" not in evidence


# ---- the negative case -----------------------------------------------


def test_an_unrelated_facet_does_not_trigger_the_tribal_path():
    """Required negative: 'Others' must not reach the Tribal code path."""
    assert "25" not in gg.TRIBAL_ELIGIBILITY_CODES
    assert "01" not in gg.TRIBAL_ELIGIBILITY_CODES
    for code in ("01", "25", "99", "", None):
        with pytest.raises(ValueError):
            gg.build_grants_gov_eligibility_search_body(eligibility_code=code)


def test_hits_are_refused_when_the_contract_has_broken():
    """Importing rows under a code of unestablished meaning is the 24/25
    mistake committed deliberately. Refuse them."""
    renamed = [
        dict(f, label="Renamed by the publisher") if f["value"] == "07" else f
        for f in REAL_FACET
    ]
    result = gg.search_grants_gov_by_eligibility(
        eligibility_code="07",
        http_post=transport(response([NO_KEYWORD_HIT], facet=renamed)),
    )
    assert result["outcome"] == gg.OUTCOME_FACET_CONTRACT_CHANGED
    assert result["hit_count"] == 0
    assert result["opp_hits"] == []
    # And it is distinguishable from "there were none".
    assert result["outcome"] != gg.OUTCOME_EMPTY
    assert result["facet_contract"]["contract_holds"] is False


# ---- outcomes stay distinguishable ------------------------------------


def test_empty_is_not_an_error_and_an_error_is_not_empty():
    empty = gg.search_grants_gov_by_eligibility(
        eligibility_code="07", http_post=transport(response([]))
    )
    assert empty["outcome"] == gg.OUTCOME_EMPTY

    def boom(url, body):
        raise RuntimeError("transport died")

    failed = gg.search_grants_gov_by_eligibility(eligibility_code="07", http_post=boom)
    assert failed["outcome"] == gg.OUTCOME_FETCH_ERROR
    assert failed["api_error"] == "transport died"


# ---- DEFECT FOUND IN WAVE 1: a refusal type that resolved to nothing --
#
# `_authorization_refusals` resolves its types by NAME. The hermetic guard
# entry read "LiveNetworkRefused"; the class is called LiveNetworkBlockedError.
# The lookup skipped it silently, so a blocked call reached the generic handler
# and came back `outcome=fetch_error, hit_count=0` - the exact collapse of "we
# were not allowed to ask" into "there are none" that this module's own comment
# says must never happen.
#
# Root cause: a name lookup whose miss is indistinguishable from success,
# because the tuple simply gets shorter. Fixed by naming the real class AND by
# making the miss observable.


def test_every_named_refusal_type_actually_resolves():
    """The regression for the defect. Fails loudly if a class is renamed."""
    assert gg.unresolved_authorization_refusals() == []


def test_the_miss_detector_fails_for_the_intended_reason(monkeypatch):
    """Falsifiability: plant a bad name and prove it is reported."""
    monkeypatch.setattr(
        gg,
        "_REFUSAL_TYPE_NAMES",
        gg._REFUSAL_TYPE_NAMES
        + (("nativeforge.services.hermetic_test_guard_service", "NoSuchClass"),),
    )
    missing = gg.unresolved_authorization_refusals()
    assert missing == ["nativeforge.services.hermetic_test_guard_service.NoSuchClass"]


def test_the_hermetic_guard_refusal_is_in_the_refusal_tuple():
    from nativeforge.services.hermetic_test_guard_service import (
        LiveNetworkBlockedError,
    )

    assert LiveNetworkBlockedError in gg._authorization_refusals()


def _refusal_instances():
    """Each refusal type, constructed the way it actually wants to be.

    These signatures differ, and getting one wrong is not a harmless test bug:
    a TypeError raised while BUILDING the exception is caught by the generic
    handler and comes back as `outcome=fetch_error`, which looks exactly like
    the defect above. A test that fails for the wrong reason proves nothing,
    so each type is constructed correctly and named.
    """
    from nativeforge.services.hermetic_test_guard_service import (
        LiveNetworkBlockedError,
    )
    from nativeforge.services.live_source_transport_service import (
        LiveTransportRefused,
    )
    from nativeforge.services.source_live_warrant_service import LiveRequestRefused

    return [
        pytest.param(
            LiveTransportRefused(["transport refused"]),
            id="LiveTransportRefused",
        ),
        pytest.param(
            LiveRequestRefused(["no warrant"], warrant={"source_id": "x"}),
            id="LiveRequestRefused",
        ),
        pytest.param(
            LiveNetworkBlockedError("hermetic guard says no"),
            id="LiveNetworkBlockedError",
        ),
    ]


@pytest.mark.parametrize("refusal", _refusal_instances())
def test_an_authorization_refusal_is_not_zero_results(refusal):
    """'Not permitted to ask' must never read as 'no Tribal grants exist'.

    Every refusal type, not just the ones that happened to resolve.
    """

    def refuse(url, body):
        raise refusal

    with pytest.raises(type(refusal)):
        gg.search_grants_gov_by_eligibility(eligibility_code="07", http_post=refuse)


def test_a_blocked_call_does_not_look_like_an_empty_search():
    """What the defect produced, asserted to be impossible now."""
    from nativeforge.services.hermetic_test_guard_service import (
        LiveNetworkBlockedError,
    )

    def blocked(url, body):
        raise LiveNetworkBlockedError("hermetic guard says no")

    with pytest.raises(LiveNetworkBlockedError):
        gg.search_grants_gov_by_eligibility(eligibility_code="07", http_post=blocked)


def test_the_publishers_total_is_reported_without_being_asserted():
    """hitCount is the publisher's number, carried as evidence only."""
    result = gg.search_grants_gov_by_eligibility(
        eligibility_code="07",
        http_post=transport(response([NO_KEYWORD_HIT], hit_count=464)),
    )
    assert result["total_hit_count"] == 464
    assert result["hit_count"] == 1  # what we actually received


def test_a_native_named_opportunity_still_arrives_through_eligibility():
    """Eligibility discovery is a superset, not a replacement."""
    result = gg.search_grants_gov_by_eligibility(
        eligibility_code="07",
        http_post=transport(response([NATIVE_KEYWORD_HIT, NO_KEYWORD_HIT])),
    )
    numbers = {h["number"] for h in result["opp_hits"]}
    assert numbers == {"BIA-2026-TTGP", "PA-26-118"}
