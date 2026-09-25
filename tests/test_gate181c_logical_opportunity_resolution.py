"""Gate 181C — thirty services must not each learn to read a relationship graph.

L1 preserves source truth: a forecast and the posting it became stay two rows.
The product must still act on one opportunity. This exercises the single
resolver that turns an L1 canonical_id into the logical opportunity, against a
real SQLite database and the real repository function - not a mock, because a
mocked resolver proves only that the mock agrees with itself.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from nativeforge.repositories.opportunity_identity_repository import (
    RESOLVED_CONFLICT,
    RESOLVED_SELF,
    RESOLVED_TO_PRIMARY,
    resolve_logical_canonical_id,
    resolve_logical_canonical_ids,
)

FORECAST = "L1:ONF181C1|forecast"
POSTED = "L1:ONF181C1|synopsis"
UNRELATED = "L1:ONF181C9|synopsis"


@pytest.fixture()
def connection():
    """A real database with the real relationships table."""
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(
            sa.text(
                """
                CREATE TABLE nf_opportunity_identity_relationships (
                    relationship_id TEXT PRIMARY KEY,
                    from_canonical_id TEXT,
                    to_canonical_id TEXT,
                    relationship TEXT,
                    match_decision TEXT,
                    identity_layer TEXT,
                    confidence FLOAT,
                    evidence_json TEXT,
                    reasons_json TEXT,
                    decided_by TEXT,
                    decided_at DATETIME,
                    reviewer TEXT,
                    candidate_id TEXT,
                    primary_canonical_id TEXT,
                    revoked_at DATETIME,
                    revoked_by TEXT,
                    revoked_reason TEXT,
                    created_at DATETIME
                )
                """
            )
        )
        yield conn


def relate(conn, *, a, b, relationship, primary, revoked_at=None, rid=None):
    conn.execute(
        sa.text(
            "INSERT INTO nf_opportunity_identity_relationships "
            "(relationship_id, from_canonical_id, to_canonical_id, relationship,"
            " primary_canonical_id, revoked_at) "
            "VALUES (:rid, :a, :b, :rel, :primary, :revoked)"
        ),
        {
            "rid": rid or f"rel-{a}-{b}-{relationship}",
            "a": a,
            "b": b,
            "rel": relationship,
            "primary": primary,
            "revoked": revoked_at,
        },
    )


# ---- no relationship --------------------------------------------------


def test_an_unrelated_opportunity_resolves_to_itself(connection):
    out = resolve_logical_canonical_id(connection=connection, canonical_id=POSTED)
    assert out["logical_canonical_id"] == POSTED
    assert out["status"] == RESOLVED_SELF
    assert out["reason"] == "no_relationship"
    assert out["invariant_failures"] == []


# ---- A/B. confirmed continuity collapses ------------------------------


def test_forecast_resolves_to_the_posting(connection):
    relate(connection, a=FORECAST, b=POSTED, relationship="FORECAST_OF", primary=POSTED)
    out = resolve_logical_canonical_id(connection=connection, canonical_id=FORECAST)
    assert out["logical_canonical_id"] == POSTED
    assert out["primary_canonical_id"] == POSTED
    assert out["status"] == RESOLVED_TO_PRIMARY
    assert out["relationship"] == "FORECAST_OF"


def test_the_posting_resolves_to_itself(connection):
    relate(connection, a=FORECAST, b=POSTED, relationship="FORECAST_OF", primary=POSTED)
    out = resolve_logical_canonical_id(connection=connection, canonical_id=POSTED)
    assert out["logical_canonical_id"] == POSTED
    assert out["status"] == RESOLVED_SELF


def test_b_the_pair_collapses_to_one_logical_opportunity(connection):
    relate(connection, a=FORECAST, b=POSTED, relationship="FORECAST_OF", primary=POSTED)
    batch = resolve_logical_canonical_ids(
        connection=connection, canonical_ids=[FORECAST, POSTED]
    )
    assert batch["requested_count"] == 2
    assert batch["logical_count"] == 1
    assert batch["collapsed_count"] == 1
    assert batch["invariant_failures"] == []


def test_same_as_also_resolves(connection):
    relate(
        connection,
        a="L1:dupe|synopsis",
        b=POSTED,
        relationship="SAME_AS",
        primary=POSTED,
    )
    out = resolve_logical_canonical_id(
        connection=connection, canonical_id="L1:dupe|synopsis"
    )
    assert out["logical_canonical_id"] == POSTED
    assert out["relationship"] == "SAME_AS"


# ---- L. relationships that must NOT collapse --------------------------


@pytest.mark.parametrize(
    "relationship", ["RELATED_TO", "RECURRENCE_OF", "REPUBLISHED_FROM", "VERSION_OF"]
)
def test_non_collapsing_relationships_stay_two(connection, relationship):
    """Last year's cycle is a different grant with a different deadline."""
    relate(connection, a=FORECAST, b=POSTED, relationship=relationship, primary=POSTED)
    batch = resolve_logical_canonical_ids(
        connection=connection, canonical_ids=[FORECAST, POSTED]
    )
    assert batch["logical_count"] == 2
    assert batch["collapsed_count"] == 0


def test_l_distinct_opportunities_stay_distinct(connection):
    batch = resolve_logical_canonical_ids(
        connection=connection, canonical_ids=[POSTED, UNRELATED]
    )
    assert batch["logical_count"] == 2


# ---- M. revocation stops the collapse ---------------------------------


def test_m_a_revoked_relationship_no_longer_collapses(connection):
    relate(
        connection,
        a=FORECAST,
        b=POSTED,
        relationship="FORECAST_OF",
        primary=POSTED,
        revoked_at="2026-09-24T00:00:00Z",
    )
    batch = resolve_logical_canonical_ids(
        connection=connection, canonical_ids=[FORECAST, POSTED]
    )
    assert batch["logical_count"] == 2
    assert batch["collapsed_count"] == 0


# ---- K. ambiguity never auto-collapses --------------------------------


def test_k_a_relationship_without_a_primary_is_refused_not_guessed(connection):
    relate(connection, a=FORECAST, b=POSTED, relationship="FORECAST_OF", primary=None)
    batch = resolve_logical_canonical_ids(
        connection=connection, canonical_ids=[FORECAST, POSTED]
    )
    assert batch["logical_count"] == 2
    assert any("forecast_of_without_primary" in f for f in batch["invariant_failures"])


def test_a_primary_that_is_not_an_endpoint_is_refused(connection):
    relate(
        connection,
        a=FORECAST,
        b=POSTED,
        relationship="FORECAST_OF",
        primary="L1:somewhere-else|synopsis",
    )
    batch = resolve_logical_canonical_ids(
        connection=connection, canonical_ids=[FORECAST, POSTED]
    )
    assert any("primary_is_not_an_endpoint" in f for f in batch["invariant_failures"])
    assert batch["logical_count"] == 2


# ---- O. conflicting state is named, never silently won ----------------


def test_o_conflicting_primaries_are_a_conflict_not_a_winner(connection):
    """Two relationships disagree about where this record belongs."""
    relate(
        connection,
        a=FORECAST,
        b=POSTED,
        relationship="FORECAST_OF",
        primary=POSTED,
        rid="r1",
    )
    relate(
        connection,
        a=FORECAST,
        b=UNRELATED,
        relationship="FORECAST_OF",
        primary=UNRELATED,
        rid="r2",
    )
    batch = resolve_logical_canonical_ids(
        connection=connection, canonical_ids=[FORECAST]
    )
    resolution = batch["resolutions"][FORECAST]
    assert resolution["status"] == RESOLVED_CONFLICT
    # It stays itself rather than picking whichever row came back first.
    assert resolution["logical_canonical_id"] == FORECAST
    assert any("conflicting_primaries_for" in f for f in batch["invariant_failures"])


# ---- P. bad graphs --------------------------------------------------


def test_p_a_relationship_cycle_is_caught_not_walked_forever(connection):
    relate(connection, a="A", b="B", relationship="SAME_AS", primary="B", rid="c1")
    relate(connection, a="B", b="A", relationship="SAME_AS", primary="A", rid="c2")
    batch = resolve_logical_canonical_ids(connection=connection, canonical_ids=["A"])
    assert batch["resolutions"]["A"]["status"] == RESOLVED_CONFLICT
    assert batch["invariant_failures"]


def test_a_chain_resolves_to_the_final_primary(connection):
    """forecast -> posting -> a later republication."""
    relate(connection, a="A", b="B", relationship="FORECAST_OF", primary="B", rid="h1")
    relate(connection, a="B", b="C", relationship="SAME_AS", primary="C", rid="h2")
    out = resolve_logical_canonical_id(connection=connection, canonical_id="A")
    assert out["logical_canonical_id"] == "C"
    assert out["status"] == RESOLVED_TO_PRIMARY


# ---- N. falsifiability: bypassing the resolver double-counts ----------


def test_n_bypassing_the_resolver_double_counts(connection):
    """The failure this whole gate exists to prevent, demonstrated.

    Counting raw L1 ids is what every read path does today. It returns two.
    """
    relate(connection, a=FORECAST, b=POSTED, relationship="FORECAST_OF", primary=POSTED)
    raw_ids = [FORECAST, POSTED]
    naive_count = len(set(raw_ids))
    resolved = resolve_logical_canonical_ids(
        connection=connection, canonical_ids=raw_ids
    )
    assert naive_count == 2
    assert resolved["logical_count"] == 1
    assert naive_count != resolved["logical_count"]


# ---- performance: no N+1 ---------------------------------------------


@pytest.mark.parametrize("n", [10, 100, 1000])
def test_resolution_does_not_issue_a_query_per_opportunity(connection, n):
    ids = [f"L1:bulk{i}|synopsis" for i in range(n)]
    batch = resolve_logical_canonical_ids(connection=connection, canonical_ids=ids)
    assert batch["requested_count"] == n
    assert batch["logical_count"] == n
    # One round, one query - not n.
    assert batch["query_count"] == 1


def test_a_feed_of_pairs_still_takes_one_round(connection):
    ids = []
    for i in range(200):
        fc = f"L1:pair{i}|forecast"
        po = f"L1:pair{i}|synopsis"
        relate(
            connection,
            a=fc,
            b=po,
            relationship="FORECAST_OF",
            primary=po,
            rid=f"p{i}",
        )
        ids.extend([fc, po])
    batch = resolve_logical_canonical_ids(connection=connection, canonical_ids=ids)
    assert batch["requested_count"] == 400
    assert batch["logical_count"] == 200
    assert batch["collapsed_count"] == 200
    # Every primary was already in the requested set, so no second round.
    assert batch["query_count"] == 1
    assert batch["invariant_failures"] == []


# ---- genericity -------------------------------------------------------


def test_the_resolver_is_not_coded_around_any_publisher():
    import ast
    import inspect

    from nativeforge.repositories import opportunity_identity_repository as repo

    tree = ast.parse(inspect.getsource(repo.resolve_logical_canonical_ids))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.append(node.value)
    haystack = " ".join(names).lower()
    for leak in ("grants_gov", "search2", "usaspending", "denali", "ckan"):
        assert leak not in haystack, f"publisher-specific identifier: {leak}"


def test_forecast_is_not_privileged_over_other_collapsing_relationships():
    """A future pre-announcement source reuses this without edits."""
    from nativeforge.repositories.opportunity_identity_repository import (
        RESOLVING_RELATIONSHIPS,
    )

    assert "FORECAST_OF" in RESOLVING_RELATIONSHIPS
    assert "SAME_AS" in RESOLVING_RELATIONSHIPS
    assert "RECURRENCE_OF" not in RESOLVING_RELATIONSHIPS
