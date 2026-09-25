"""Gate 181G — a real publisher outside the Grants.gov path.

Denali Commission is the first instance of a generic WordPress REST adapter.
Two things this gate exists to refuse:

    a 200 with nothing parsed is not a healthy source
    Alaska is not Native

The second matters most. Most of the villages Denali serves are Alaska Native,
and it would be easy and wrong to mark the agency's whole output
Native-specific on the strength of a state name.

Offline. The live contract proof is reported separately.
"""

from __future__ import annotations

from nativeforge.services import wordpress_rest_listing_adapter_service as wp

#: Shaped exactly like the live /wp-json/wp/v2/posts payload.
TRIBAL_RECORD = {
    "id": 3601,
    "date": "2024-01-03T16:38:36",
    "modified": "2024-01-18T15:09:57",
    "slug": "funding-assistance-for-tribal-victim-services",
    "link": "https://denali.gov/funding-assistance-for-tribal-victim-services/",
    "title": {"rendered": "FUNDING ASSISTANCE FOR TRIBAL VICTIM SERVICES"},
    "excerpt": {"rendered": "<p>Support for Tribal victim service programs.</p>"},
}

#: A real Denali funding opportunity whose only locating signal is Alaska.
GEOGRAPHY_ONLY_RECORD = {
    "id": 4048,
    "date": "2024-12-06T16:45:38",
    "modified": "2025-01-17T13:52:47",
    "slug": "denali-commission-accepting-statements-of-interest",
    "link": "https://denali.gov/denali-commission-accepting-statements-of-interest/",
    "title": {"rendered": "New Closing Date for Two Funding Opportunities"},
    "excerpt": {"rendered": "<p>Rural Alaska infrastructure projects.</p>"},
}

HEADERS = {"X-WP-Total": "18", "X-WP-TotalPages": "6"}


# ---- 2/3. the real contract, and evidence preserved -------------------


def test_2_the_live_record_shape_parses():
    out = wp.parse_listing_response(records=[TRIBAL_RECORD], headers=HEADERS)
    assert out["parse_outcome"] == wp.PARSED
    assert out["listing_count"] == 1
    assert out["publisher_total"] == "18"

    listing = out["listings"][0]
    assert listing["publisher_record_id"] == "3601"
    assert listing["title"] == "FUNDING ASSISTANCE FOR TRIBAL VICTIM SERVICES"
    assert listing["source_url"].startswith("https://denali.gov/")
    # The publisher's own change marker.
    assert listing["modified_at"] == "2024-01-18T15:09:57"


def test_3_raw_evidence_is_carried_on_every_listing():
    out = wp.parse_listing_response(
        records=[TRIBAL_RECORD],
        headers=HEADERS,
        source_id="denali-commission",
        retrieved_at="2026-09-25T03:00:00Z",
        raw_payload_sha256="abc123",
    )
    listing = out["listings"][0]
    assert listing["source_id"] == "denali-commission"
    assert listing["retrieved_at"] == "2026-09-25T03:00:00Z"
    assert listing["raw_payload_sha256"] == "abc123"


def test_absent_fields_are_absent_not_invented():
    """The publisher does not state a deadline, so neither do we."""
    listing = wp.parse_listing_response(records=[TRIBAL_RECORD])["listings"][0]
    assert listing["deadline"] is None
    assert listing["funding_amount"] is None
    assert listing["eligibility_text"] is None
    assert listing["status"] is None
    assert "deadline" in listing["fields_absent"]


# ---- 4/5/16/17. zero is not one thing ---------------------------------


def test_4_an_empty_publisher_response_is_a_legitimate_zero():
    out = wp.parse_listing_response(records=[], headers=HEADERS)
    assert out["parse_outcome"] == wp.LEGITIMATE_ZERO
    assert out["source_is_behaving"] is True
    assert wp.listing_health(out)["healthy"] is True
    assert wp.listing_health(out)["zero_is_legitimate"] is True


def test_5_records_that_cannot_be_read_are_structure_drift():
    """Falsifiability: the publisher changed shape, and we must notice."""
    drifted = [{"identifier": 1, "headline": "x"}, {"identifier": 2}]
    out = wp.parse_listing_response(records=drifted, headers=HEADERS)
    assert out["parse_outcome"] == wp.STRUCTURE_DRIFT
    assert out["listing_count"] == 0
    assert out["unusable_record_count"] == 2
    # The distinction that matters: this zero is NOT legitimate.
    health = wp.listing_health(out)
    assert health["healthy"] is False
    assert health["zero_is_a_failure"] is True
    assert "required_fields_absent_from_every_record" in health["invariant_failures"]


def test_16_a_200_with_an_unreadable_body_is_not_healthy():
    out = wp.parse_listing_response(records={"error": "nope"}, headers=HEADERS)
    assert out["parse_outcome"] == wp.PARSE_FAILURE
    assert wp.listing_health(out)["healthy"] is False


def test_17_a_blocked_request_does_not_become_an_empty_source():
    out = wp.blocked_response(reason="robots_disallow")
    assert out["parse_outcome"] == wp.BLOCKED
    assert out["listing_count"] == 0
    assert out["source_is_behaving"] is False
    health = wp.listing_health(out)
    assert health["healthy"] is False
    assert health["zero_is_legitimate"] is False
    assert "access_refused_not_empty" in health["invariant_failures"]


def test_all_four_zero_states_are_distinguishable():
    outcomes = {
        wp.parse_listing_response(records=[])["parse_outcome"],
        wp.parse_listing_response(records=[{"x": 1}])["parse_outcome"],
        wp.parse_listing_response(records="not a list")["parse_outcome"],
        wp.blocked_response(reason="r")["parse_outcome"],
    }
    assert outcomes == {
        wp.LEGITIMATE_ZERO,
        wp.STRUCTURE_DRIFT,
        wp.PARSE_FAILURE,
        wp.BLOCKED,
    }


# ---- 6/7. Alaska is not Native ----------------------------------------


def test_6_geography_alone_produces_no_native_evidence():
    """THE guard. A real Denali funding notice about rural Alaska."""
    listing = wp.parse_listing_response(records=[GEOGRAPHY_ONLY_RECORD])["listings"][0]
    evidence = wp.extract_native_relevance_evidence(listing)

    assert evidence["native_evidence_terms"] == []
    assert evidence["has_native_evidence"] is False
    assert "alaska" in evidence["geography_terms"]
    assert evidence["has_geography_only_signal"] is True
    assert evidence["geography_alone_is_not_native_relevance"] is True


def test_7_explicit_tribal_wording_is_native_evidence():
    listing = wp.parse_listing_response(records=[TRIBAL_RECORD])["listings"][0]
    evidence = wp.extract_native_relevance_evidence(listing)

    assert "tribal" in evidence["native_evidence_terms"]
    assert evidence["has_native_evidence"] is True
    assert evidence["has_geography_only_signal"] is False


def test_6_the_adapter_never_decides_relevance():
    for record in (TRIBAL_RECORD, GEOGRAPHY_ONLY_RECORD):
        listing = wp.parse_listing_response(records=[record])["listings"][0]
        evidence = wp.extract_native_relevance_evidence(listing)
        assert evidence["relevance_decided"] is False
        assert evidence["relevance_is_decided_by_gate_173"] is True
        assert "relevance_class" not in evidence


def test_6_alaska_is_absent_from_the_native_evidence_vocabulary():
    """Falsifiability at the vocabulary level, not just the output."""
    terms = " ".join(wp._NATIVE_EVIDENCE_TERMS)
    assert "alaska native" in terms  # the ENTITY is evidence
    assert "alaska" in wp._GEOGRAPHY_ONLY_TERMS  # the PLACE is not


# ---- 8. eligibility stays separate ------------------------------------


def test_8_native_evidence_says_nothing_about_eligibility():
    listing = wp.parse_listing_response(records=[TRIBAL_RECORD])["listings"][0]
    evidence = wp.extract_native_relevance_evidence(listing)
    assert "eligible" not in str(evidence).lower()
    assert listing["eligibility_text"] is None


# ---- 14. replay -------------------------------------------------------


def test_14_the_same_payload_parses_identically():
    first = wp.parse_listing_response(records=[TRIBAL_RECORD], headers=HEADERS)
    second = wp.parse_listing_response(records=[TRIBAL_RECORD], headers=HEADERS)
    assert first == second


def test_14_publisher_id_is_the_stable_key():
    out = wp.parse_listing_response(records=[TRIBAL_RECORD, TRIBAL_RECORD])
    ids = [x["publisher_record_id"] for x in out["listings"]]
    assert ids == ["3601", "3601"]  # dedupe is identity's job, not the parser's


# ---- 18. a program name is not a source identity ----------------------


def test_18_the_request_is_built_from_the_publisher_not_a_program():
    request = wp.build_listing_request(base_url="https://denali.gov", search="funding")
    assert request["url"] == "https://denali.gov/wp-json/wp/v2/posts"
    # The programme name appears nowhere in the source definition.
    assert "tribal victim" not in str(request).lower()
    assert "solid waste" not in str(request).lower()


def test_18_one_publisher_many_records():
    out = wp.parse_listing_response(records=[TRIBAL_RECORD, GEOGRAPHY_ONLY_RECORD])
    assert out["listing_count"] == 2
    # Two programmes, one source. Not two sources.
    assert len({x["source_url"].split("/")[2] for x in out["listings"]}) == 1


# ---- genericity -------------------------------------------------------


def test_the_adapter_is_not_written_around_denali():
    import ast
    import inspect

    # Identifiers and imports only. The module docstring names Denali as an
    # example of a WordPress publisher, which is prose about the boundary
    # rather than a breach of it - the first version of this test failed on
    # exactly that, and the test was what was wrong.
    tree = ast.parse(inspect.getsource(wp))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
        elif isinstance(node, ast.FunctionDef):
            names.append(node.name)
    haystack = " ".join(names).lower()
    for leak in ("denali", "grants_gov", "usaspending"):
        assert leak not in haystack, f"publisher-specific identifier: {leak}"


def test_no_publisher_hostname_is_hardcoded_in_the_adapter():
    """The dependency check that actually matters: no baked-in URL."""
    import inspect

    source = inspect.getsource(wp)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"'):
            continue
        assert "denali.gov" not in stripped, f"hardcoded host: {stripped}"


def test_the_adapter_works_for_any_wordpress_publisher():
    for base in ("https://example.org", "https://arc.gov/", "https://nbrc.gov"):
        request = wp.build_listing_request(base_url=base, search="grant")
        assert request["url"].endswith("/wp-json/wp/v2/posts")
        assert "//wp-json" not in request["url"]
