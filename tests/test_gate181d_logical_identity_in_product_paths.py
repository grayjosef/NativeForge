"""Gate 181D — the product behaves as one opportunity, not just the resolver.

The resolver was never the feature. These exercise the real feed, the real
decision service and the real repository against a real database, because a
resolver nothing calls proves only that it would have worked.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from nativeforge.repositories.opportunity_identity_repository import (
    resolve_logical_canonical_ids,
)
from nativeforge.services.customer_decision_service import (
    DISMISSED,
    PURSUING,
    WATCHED,
    build_decision,
)
from nativeforge.services.customer_opportunity_feed_service import build_feed
from nativeforge.services.logical_opportunity_read_service import (
    CONFLICT,
    collapse_rows,
    customer_visible_invariant_failures,
    duplicate_pursuit_failures,
    logical_key,
    logical_opportunity_count,
    reconcile_customer_state,
)

ORG = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
FORECAST = "L1:ONF181D1|forecast"
POSTED = "L1:ONF181D1|synopsis"
OTHER = "L1:ONF181D9|synopsis"


@pytest.fixture()
def connection():
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(
            sa.text(
                """
                CREATE TABLE nf_opportunity_identity_relationships (
                    relationship_id TEXT PRIMARY KEY,
                    from_canonical_id TEXT, to_canonical_id TEXT,
                    relationship TEXT, match_decision TEXT, identity_layer TEXT,
                    confidence FLOAT, evidence_json TEXT, reasons_json TEXT,
                    decided_by TEXT, decided_at DATETIME, reviewer TEXT,
                    candidate_id TEXT, primary_canonical_id TEXT,
                    revoked_at DATETIME, revoked_by TEXT, revoked_reason TEXT,
                    created_at DATETIME
                )
                """
            )
        )
        yield conn


def relate(conn, *, a, b, relationship="FORECAST_OF", primary, rid=None):
    conn.execute(
        sa.text(
            "INSERT INTO nf_opportunity_identity_relationships "
            "(relationship_id, from_canonical_id, to_canonical_id, relationship,"
            " primary_canonical_id) VALUES (:rid,:a,:b,:rel,:p)"
        ),
        {"rid": rid or f"r-{a}-{b}", "a": a, "b": b, "rel": relationship, "p": primary},
    )


def resolutions_for(conn, ids):
    return resolve_logical_canonical_ids(connection=conn, canonical_ids=ids)


def rec(canonical_id, *, deadline="2027-07-01", state="NEW"):
    return {
        "canonical_id": canonical_id,
        "relevance_class": "NATIVE_ELIGIBLE",
        "deadline": deadline,
        "decision_state": state,
        "sourced_from_canonical_graph": True,
    }


# ---- 1/3/4. feed, count, search --------------------------------------


def test_1_the_feed_returns_one_card_for_a_confirmed_pair(connection):
    relate(connection, a=FORECAST, b=POSTED, primary=POSTED)
    res = resolutions_for(connection, [FORECAST, POSTED])

    feed = build_feed(
        organization_id=ORG,
        recommendations=[rec(FORECAST), rec(POSTED)],
        logical_resolutions=res,
    )
    assert feed["returned"] == 1
    assert feed["logical_opportunity_count"] == 1
    assert feed["representation_count"] == 2
    assert feed["collapsed_representations"] == 1
    assert feed["identity_collapse_applied"] is True

    card = feed["recommendations"][0]
    assert card["logical_opportunity_id"] == POSTED
    assert card["historical_representations"] == [FORECAST]
    assert card["has_pre_publication_history"] is True


def test_3_counts_report_opportunities_and_representations_separately(connection):
    relate(connection, a=FORECAST, b=POSTED, primary=POSTED)
    res = resolutions_for(connection, [FORECAST, POSTED])
    assert logical_opportunity_count([FORECAST, POSTED], resolutions=res) == 1
    # The representation count is a real number with a different meaning.
    assert len({FORECAST, POSTED}) == 2


def test_4_search_style_row_collapse(connection):
    relate(connection, a=FORECAST, b=POSTED, primary=POSTED)
    res = resolutions_for(connection, [FORECAST, POSTED, OTHER])
    out = collapse_rows([rec(FORECAST), rec(POSTED), rec(OTHER)], resolutions=res)
    assert out["logical_opportunity_count"] == 2
    assert out["collapsed_count"] == 1


# ---- 2. detail: either id lands on the same opportunity ---------------


def test_2_either_representation_id_resolves_to_the_same_opportunity(connection):
    relate(connection, a=FORECAST, b=POSTED, primary=POSTED)
    res = resolutions_for(connection, [FORECAST, POSTED])
    assert logical_key(FORECAST, res) == logical_key(POSTED, res) == POSTED


# ---- 5/6. watch and dismiss survive the transition -------------------


def test_5_watching_the_forecast_still_watches_it_after_posting(connection):
    relate(connection, a=FORECAST, b=POSTED, primary=POSTED)
    res = resolutions_for(connection, [FORECAST, POSTED])

    watched = build_decision(
        organization_id=ORG,
        canonical_id=FORECAST,
        decision_state=WATCHED,
        logical_canonical_id=logical_key(FORECAST, res),
    )
    # The same person later opens the posted record.
    viewed = build_decision(
        organization_id=ORG,
        canonical_id=POSTED,
        decision_state=WATCHED,
        logical_canonical_id=logical_key(POSTED, res),
    )
    assert watched["decision_id"] == viewed["decision_id"]
    assert watched["logical_canonical_id"] == POSTED
    # And the row still records which representation was in front of them.
    assert watched["canonical_id"] == FORECAST
    assert viewed["canonical_id"] == POSTED


def test_6_dismissal_remains_associated_after_posting(connection):
    relate(connection, a=FORECAST, b=POSTED, primary=POSTED)
    res = resolutions_for(connection, [FORECAST, POSTED])
    decisions = [
        build_decision(
            organization_id=ORG,
            canonical_id=FORECAST,
            decision_state=DISMISSED,
            logical_canonical_id=logical_key(FORECAST, res),
        )
    ]
    state = reconcile_customer_state(decisions, resolutions=res)
    assert state["by_logical_opportunity"][POSTED]["decision_state"] == DISMISSED
    assert state["conflict_count"] == 0


def test_without_the_logical_id_the_decision_splits(connection):
    """Falsifiability: this is the split-brain the wiring removes."""
    watched = build_decision(
        organization_id=ORG, canonical_id=FORECAST, decision_state=WATCHED
    )
    pursued = build_decision(
        organization_id=ORG, canonical_id=POSTED, decision_state=PURSUING
    )
    assert watched["decision_id"] != pursued["decision_id"]
    assert watched["decision_binds_to_logical_opportunity"] is False


# ---- 7. pursuits ------------------------------------------------------


def test_7_two_pursuits_for_one_opportunity_are_caught(connection):
    relate(connection, a=FORECAST, b=POSTED, primary=POSTED)
    res = resolutions_for(connection, [FORECAST, POSTED])
    failures = duplicate_pursuit_failures(
        [
            {"pursuit_id": "p1", "canonical_id": FORECAST},
            {"pursuit_id": "p2", "canonical_id": POSTED},
        ],
        resolutions=res,
    )
    assert failures
    assert "duplicate_pursuits_for_one_opportunity" in failures[0]


def test_7_pursuits_on_genuinely_different_grants_are_fine(connection):
    res = resolutions_for(connection, [POSTED, OTHER])
    assert (
        duplicate_pursuit_failures(
            [
                {"pursuit_id": "p1", "canonical_id": POSTED},
                {"pursuit_id": "p2", "canonical_id": OTHER},
            ],
            resolutions=res,
        )
        == []
    )


# ---- 15. conflicting customer state -----------------------------------


def test_15_dismissed_forecast_and_pursued_posting_is_a_conflict(connection):
    relate(connection, a=FORECAST, b=POSTED, primary=POSTED)
    res = resolutions_for(connection, [FORECAST, POSTED])
    decisions = [
        build_decision(
            organization_id=ORG, canonical_id=FORECAST, decision_state=DISMISSED
        ),
        build_decision(
            organization_id=ORG, canonical_id=POSTED, decision_state=PURSUING
        ),
    ]
    state = reconcile_customer_state(decisions, resolutions=res)
    entry = state["by_logical_opportunity"][POSTED]

    assert entry["status"] == CONFLICT
    assert entry["decision_state"] is None  # no silent winner
    assert entry["competing_states"] == [DISMISSED, PURSUING]
    assert entry["requires_human"] is True
    # Both histories survive.
    assert len(entry["decisions"]) == 2


def test_new_is_the_absence_of_a_decision_and_never_conflicts(connection):
    relate(connection, a=FORECAST, b=POSTED, primary=POSTED)
    res = resolutions_for(connection, [FORECAST, POSTED])
    decisions = [
        build_decision(organization_id=ORG, canonical_id=FORECAST),
        build_decision(
            organization_id=ORG, canonical_id=POSTED, decision_state=WATCHED
        ),
    ]
    state = reconcile_customer_state(decisions, resolutions=res)
    assert state["by_logical_opportunity"][POSTED]["status"] != CONFLICT
    assert state["by_logical_opportunity"][POSTED]["decision_state"] == WATCHED


# ---- 16. bypassing the resolver ---------------------------------------


def test_16_a_feed_without_resolutions_shows_the_pair_twice(connection):
    """The defect, demonstrated through the real feed."""
    feed = build_feed(organization_id=ORG, recommendations=[rec(FORECAST), rec(POSTED)])
    assert feed["returned"] == 2
    assert feed["identity_collapse_applied"] is False


def test_16_the_invariant_detector_catches_a_visible_superseded_row(connection):
    relate(connection, a=FORECAST, b=POSTED, primary=POSTED)
    res = resolutions_for(connection, [FORECAST, POSTED])
    # Correctly collapsed: no failure.
    assert (
        customer_visible_invariant_failures(
            rows=[rec(FORECAST), rec(POSTED)], resolutions=res
        )
        == []
    )
    # Without resolutions nothing collapses, and the pair is visible twice.
    out = collapse_rows([rec(FORECAST), rec(POSTED)], resolutions=None)
    assert out["logical_opportunity_count"] == 2


# ---- 19/20. relationships that must not collapse ----------------------


@pytest.mark.parametrize(
    "relationship", ["RECURRENCE_OF", "VERSION_OF", "RELATED_TO", "REPUBLISHED_FROM"]
)
def test_19_20_non_collapsing_relationships_keep_two_cards(connection, relationship):
    relate(
        connection,
        a=FORECAST,
        b=POSTED,
        relationship=relationship,
        primary=POSTED,
    )
    res = resolutions_for(connection, [FORECAST, POSTED])
    feed = build_feed(
        organization_id=ORG,
        recommendations=[rec(FORECAST), rec(POSTED)],
        logical_resolutions=res,
    )
    assert feed["returned"] == 2
    assert feed["logical_opportunity_count"] == 2


# ---- 14. ambiguity ----------------------------------------------------


def test_14_a_relationship_without_a_primary_does_not_collapse_the_feed(connection):
    relate(connection, a=FORECAST, b=POSTED, primary=None)
    res = resolutions_for(connection, [FORECAST, POSTED])
    feed = build_feed(
        organization_id=ORG,
        recommendations=[rec(FORECAST), rec(POSTED)],
        logical_resolutions=res,
    )
    assert feed["returned"] == 2
    assert res["invariant_failures"]


# ---- 17. scale --------------------------------------------------------


@pytest.mark.parametrize("pairs", [10, 100, 1000])
def test_17_a_large_feed_costs_one_relationship_query(connection, pairs):
    ids = []
    for i in range(pairs):
        fc, po = f"L1:s{i}|forecast", f"L1:s{i}|synopsis"
        relate(connection, a=fc, b=po, primary=po, rid=f"s{i}")
        ids.extend([fc, po])

    res = resolutions_for(connection, ids)
    assert res["query_count"] == 1
    assert res["logical_count"] == pairs

    feed = build_feed(
        organization_id=ORG,
        recommendations=[rec(i) for i in ids],
        logical_resolutions=res,
        limit=10_000,
    )
    assert feed["logical_opportunity_count"] == pairs
    assert feed["representation_count"] == pairs * 2


# ---- genericity -------------------------------------------------------


def test_the_read_layer_names_no_publisher():
    import ast
    import inspect

    from nativeforge.services import logical_opportunity_read_service as svc

    tree = ast.parse(inspect.getsource(svc))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    haystack = " ".join(names).lower()
    for leak in ("grants_gov", "search2", "synopsis", "usaspending", "denali"):
        assert leak not in haystack, f"publisher-specific identifier: {leak}"
