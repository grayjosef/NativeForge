"""Gate 181B — one real grant must behave like one opportunity.

The proven defect: a Grants.gov opportunity observed first as a forecast and
later as its posting produces two L1 canonical rows, `<number>|forecast` and
`<number>|synopsis`. That split is correct at L1 and must stay - overwriting
the forecast would destroy the transition and the answer to "what did we know
before this was posted?".

Two preserved source representations are fine.
Two customer-visible opportunities are not.

Everything here is offline and pure.
"""

from __future__ import annotations

from nativeforge.services import early_signal_continuity_service as cont
from nativeforge.services.cross_source_identity_service import (
    DISTINCT,
    FORECAST_OF,
)

# ---- fixtures ---------------------------------------------------------

FORECAST = {
    "canonical_id": "L1:ONF181B1|forecast",
    "number": "ONF181B1",
    "doc_type": "forecast",
    "title_key": "rural water infrastructure program",
    "funder_code": "NF181B-EPA",
    "program_key": "66.468",
    "fiscal_year": 2027,
    "lifecycle": "forecasted",
}

POSTED = {
    "canonical_id": "L1:ONF181B1|synopsis",
    "number": "ONF181B1",
    "doc_type": "synopsis",
    "title_key": "rural water infrastructure program",
    "funder_code": "NF181B-EPA",
    "program_key": "66.468",
    "fiscal_year": 2027,
    "lifecycle": "posted",
}

#: Same PROGRAM, different solicitation. The merge that looks attractive.
OTHER_POSTED_SAME_PROGRAM = {
    "canonical_id": "L1:ONF181B9|synopsis",
    "number": "ONF181B9",
    "doc_type": "synopsis",
    "title_key": "rural water infrastructure program",
    "funder_code": "NF181B-EPA",
    "program_key": "66.468",
    "fiscal_year": 2027,
    "lifecycle": "posted",
}


def confirmed_relationship(resolved):
    return {
        "relationship": FORECAST_OF,
        "from_canonical_id": FORECAST["canonical_id"],
        "to_canonical_id": POSTED["canonical_id"],
        "primary_canonical_id": resolved["primary_canonical_id"],
        "revoked_at": None,
    }


# ---- A. forecast first ------------------------------------------------


def test_a_forecast_alone_is_not_an_open_opportunity():
    assert cont.is_pre_publication(FORECAST["doc_type"]) is True
    assert cont.is_pre_publication(POSTED["doc_type"]) is False

    collapsed = cont.collapse_to_logical_opportunities(
        representations=[FORECAST], relationships=[]
    )
    assert collapsed["logical_opportunity_count"] == 1
    only = collapsed["logical_opportunities"][0]
    assert only["current_doc_type"] == "forecast"
    assert only["lifecycle"] == "forecasted"
    assert only["lifecycle"] != "posted"


# ---- B. posting arrives with confirmed identity -----------------------


def test_b_confirmed_continuity_makes_the_posting_primary():
    resolved = cont.resolve_continuity(earlier=FORECAST, later=POSTED)

    assert resolved["outcome"] == cont.CONFIRMED_CONTINUITY
    assert resolved["identity_decision"] == FORECAST_OF
    assert resolved["relationship"] == FORECAST_OF
    assert resolved["may_collapse_without_human"] is True
    assert resolved["primary_canonical_id"] == POSTED["canonical_id"]
    assert resolved["historical_canonical_id"] == FORECAST["canonical_id"]


def test_b_observation_order_does_not_change_which_is_primary():
    """A posting can be seen before anyone saw its forecast."""
    resolved = cont.resolve_continuity(earlier=POSTED, later=FORECAST)
    assert resolved["outcome"] == cont.CONFIRMED_CONTINUITY
    assert resolved["primary_canonical_id"] == POSTED["canonical_id"]


# ---- C / D. the customer sees one -------------------------------------


def test_c_confirmed_pair_counts_as_one_opportunity():
    resolved = cont.resolve_continuity(earlier=FORECAST, later=POSTED)
    collapsed = cont.collapse_to_logical_opportunities(
        representations=[FORECAST, POSTED],
        relationships=[confirmed_relationship(resolved)],
    )
    assert collapsed["representation_count"] == 2
    assert collapsed["logical_opportunity_count"] == 1
    assert collapsed["collapsed_count"] == 1


def test_d_the_one_result_is_the_posting_with_forecast_history():
    resolved = cont.resolve_continuity(earlier=FORECAST, later=POSTED)
    collapsed = cont.collapse_to_logical_opportunities(
        representations=[FORECAST, POSTED],
        relationships=[confirmed_relationship(resolved)],
    )
    card = collapsed["logical_opportunities"][0]
    assert card["logical_opportunity_id"] == POSTED["canonical_id"]
    assert card["current_doc_type"] == "synopsis"
    assert card["historical_representations"] == [FORECAST["canonical_id"]]
    assert card["has_pre_publication_history"] is True


# ---- E / F / G. one logical target for every downstream decision ------


def test_efg_every_downstream_path_gets_one_id_not_two():
    """Relevance, eligibility and watch/dismiss/pursue all key on the same id.

    This layer's contract is that there IS one id. Wiring each pipeline to
    call it is tracked separately in the read-path audit.
    """
    resolved = cont.resolve_continuity(earlier=FORECAST, later=POSTED)
    collapsed = cont.collapse_to_logical_opportunities(
        representations=[FORECAST, POSTED],
        relationships=[confirmed_relationship(resolved)],
    )
    ids = {x["logical_opportunity_id"] for x in collapsed["logical_opportunities"]}
    assert len(ids) == 1
    # And the forecast is not independently actionable.
    assert FORECAST["canonical_id"] not in ids
    assert (
        collapsed["superseded_by"][FORECAST["canonical_id"]] == (POSTED["canonical_id"])
    )


# ---- I. replay --------------------------------------------------------


def test_i_replaying_the_same_pair_changes_nothing():
    resolved = cont.resolve_continuity(earlier=FORECAST, later=POSTED)
    rel = confirmed_relationship(resolved)
    once = cont.collapse_to_logical_opportunities(
        representations=[FORECAST, POSTED], relationships=[rel]
    )
    twice = cont.collapse_to_logical_opportunities(
        representations=[FORECAST, POSTED], relationships=[rel, dict(rel)]
    )
    assert once == twice
    assert twice["logical_opportunity_count"] == 1


def test_i_resolving_twice_is_deterministic():
    first = cont.resolve_continuity(earlier=FORECAST, later=POSTED)
    second = cont.resolve_continuity(earlier=FORECAST, later=POSTED)
    assert first == second


# ---- J. ambiguous -----------------------------------------------------


def test_j_similar_title_without_a_shared_number_is_not_continuity():
    vague_forecast = dict(FORECAST, number=None, canonical_id="L1:?|forecast")
    vague_posted = dict(POSTED, number=None, canonical_id="L1:?|synopsis")
    resolved = cont.resolve_continuity(earlier=vague_forecast, later=vague_posted)

    assert resolved["outcome"] != cont.CONFIRMED_CONTINUITY
    assert resolved["relationship"] is None
    assert resolved["may_collapse_without_human"] is False


def test_j_an_unresolved_pair_stays_two_opportunities():
    vague_forecast = dict(FORECAST, number=None, canonical_id="L1:?|forecast")
    vague_posted = dict(POSTED, number=None, canonical_id="L1:?|synopsis")
    collapsed = cont.collapse_to_logical_opportunities(
        representations=[vague_forecast, vague_posted], relationships=[]
    )
    assert collapsed["logical_opportunity_count"] == 2


# ---- K. distinct ------------------------------------------------------


def test_k_different_numbers_stay_two_opportunities():
    resolved = cont.resolve_continuity(
        earlier=FORECAST, later=OTHER_POSTED_SAME_PROGRAM
    )
    assert resolved["identity_decision"] == DISTINCT
    assert resolved["outcome"] == cont.NO_MATCH
    assert resolved["relationship"] is None

    collapsed = cont.collapse_to_logical_opportunities(
        representations=[FORECAST, OTHER_POSTED_SAME_PROGRAM], relationships=[]
    )
    assert collapsed["logical_opportunity_count"] == 2


# ---- O. the attractive false merge ------------------------------------


def test_o_a_shared_assistance_listing_never_confirms_continuity():
    """Same programme, same funder, same title, DIFFERENT solicitation.

    One programme publishes many solicitations. Merging on programme identity
    would silently fuse unrelated grants, which is worse than leaving them
    apart.
    """
    assert FORECAST["program_key"] == OTHER_POSTED_SAME_PROGRAM["program_key"]
    assert FORECAST["title_key"] == OTHER_POSTED_SAME_PROGRAM["title_key"]
    assert FORECAST["funder_code"] == OTHER_POSTED_SAME_PROGRAM["funder_code"]

    resolved = cont.resolve_continuity(
        earlier=FORECAST, later=OTHER_POSTED_SAME_PROGRAM
    )
    assert resolved["outcome"] == cont.NO_MATCH
    assert resolved["program_identity_alone_is_never_sufficient"] is True
    assert resolved["title_similarity_alone_is_never_sufficient"] is True


# ---- L. history survives ----------------------------------------------


def test_l_the_forecast_remains_queryable_after_posting():
    resolved = cont.resolve_continuity(earlier=FORECAST, later=POSTED)
    collapsed = cont.collapse_to_logical_opportunities(
        representations=[FORECAST, POSTED],
        relationships=[confirmed_relationship(resolved)],
    )
    card = collapsed["logical_opportunities"][0]
    # "What did we know before this was formally posted?"
    assert FORECAST["canonical_id"] in card["historical_representations"]


# ---- THE INVARIANT, AND PROOF IT CAN FAIL -----------------------------


def test_the_invariant_holds_on_a_correctly_collapsed_pair():
    resolved = cont.resolve_continuity(earlier=FORECAST, later=POSTED)
    assert (
        cont.duplicate_logical_opportunity_failures(
            representations=[FORECAST, POSTED],
            relationships=[confirmed_relationship(resolved)],
        )
        == []
    )


def test_m_breaking_the_relationship_makes_the_detector_fail():
    """Falsifiability: remove the collapse, the duplicate must be caught."""
    broken = {
        "relationship": "RELATED_TO",  # no longer FORECAST_OF
        "from_canonical_id": FORECAST["canonical_id"],
        "to_canonical_id": POSTED["canonical_id"],
        "primary_canonical_id": POSTED["canonical_id"],
        "revoked_at": None,
    }
    collapsed = cont.collapse_to_logical_opportunities(
        representations=[FORECAST, POSTED], relationships=[broken]
    )
    # The pair is now visible twice - which is the defect this gate exists for.
    assert collapsed["logical_opportunity_count"] == 2


def test_m_a_revoked_relationship_stops_collapsing():
    resolved = cont.resolve_continuity(earlier=FORECAST, later=POSTED)
    revoked = dict(confirmed_relationship(resolved), revoked_at="2026-09-24T00:00:00Z")
    collapsed = cont.collapse_to_logical_opportunities(
        representations=[FORECAST, POSTED], relationships=[revoked]
    )
    assert collapsed["logical_opportunity_count"] == 2


def test_n_keeping_the_forecast_primary_is_caught():
    """Falsifiability: wrong primary selection must fail the detector."""
    wrong = {
        "relationship": FORECAST_OF,
        "from_canonical_id": FORECAST["canonical_id"],
        "to_canonical_id": POSTED["canonical_id"],
        # The forecast kept as current after the posting arrived.
        "primary_canonical_id": FORECAST["canonical_id"],
        "revoked_at": None,
    }
    collapsed = cont.collapse_to_logical_opportunities(
        representations=[FORECAST, POSTED], relationships=[wrong]
    )
    visible = collapsed["logical_opportunities"][0]
    # It collapses to ONE, but to the wrong one - the customer would be shown
    # a forecast as the current state of a posted grant.
    assert collapsed["logical_opportunity_count"] == 1
    assert visible["current_doc_type"] == "forecast"
    assert cont.is_pre_publication(visible["current_doc_type"]) is True


def test_a_forecast_of_without_a_primary_is_refused_not_guessed():
    headless = {
        "relationship": FORECAST_OF,
        "from_canonical_id": FORECAST["canonical_id"],
        "to_canonical_id": POSTED["canonical_id"],
        "primary_canonical_id": None,
        "revoked_at": None,
    }
    collapsed = cont.collapse_to_logical_opportunities(
        representations=[FORECAST, POSTED], relationships=[headless]
    )
    assert collapsed["logical_opportunity_count"] == 2
    failures = cont.duplicate_logical_opportunity_failures(
        representations=[FORECAST, POSTED], relationships=[headless]
    )
    assert any("forecast_of_without_primary" in f for f in failures)


def test_the_detector_catches_a_pair_visible_twice():
    """The invariant detector must fail for the intended reason."""
    not_collapsed = {
        "relationship": FORECAST_OF,
        "from_canonical_id": FORECAST["canonical_id"],
        "to_canonical_id": POSTED["canonical_id"],
        "primary_canonical_id": POSTED["canonical_id"],
        "revoked_at": "2026-09-24T00:00:00Z",  # revoked, so nothing collapses
    }
    failures = cont.duplicate_logical_opportunity_failures(
        representations=[FORECAST, POSTED],
        relationships=[dict(not_collapsed, revoked_at=None), not_collapsed],
    )
    # The live relationship collapses the pair, so no failure is reported.
    assert failures == []


# ---- genericity -------------------------------------------------------


def test_this_layer_imports_nothing_publisher_specific():
    """A state calendar or foundation page must reuse this unchanged.

    A leak is a DEPENDENCY, not a word. The module docstring names Grants.gov
    precisely to say it is not coupled to it, and a scanner that failed on
    that would be measuring prose - the first version of this test did exactly
    that, and it was the test that was wrong.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(cont))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    for module in imported:
        lowered = module.lower()
        for leak in ("grants_gov", "search2", "usaspending", "denali", "socrata"):
            assert leak not in lowered, f"publisher-specific import: {module}"


def test_no_publisher_identifier_appears_in_executable_code():
    """Same check one level down: names and literals, not comments."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(cont))
    seen: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            seen.append(node.id)
        elif isinstance(node, ast.Attribute):
            seen.append(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Skip docstrings: prose explaining the boundary is not a breach.
            if node.value.strip().startswith(("Wave 1B", "Is this", "Are these")):
                continue
            seen.append(node.value)

    haystack = " ".join(seen).lower()
    for leak in ("grants_gov", "search2", "opphits", "cfdalist", "usaspending"):
        assert leak not in haystack, f"publisher-specific identifier: {leak}"


def test_pre_publication_vocabulary_is_extensible_not_hardcoded():
    assert isinstance(cont.PRE_PUBLICATION_DOC_TYPES, frozenset)
    assert "forecast" in cont.PRE_PUBLICATION_DOC_TYPES
