"""Gate 181E — relevance, eligibility, documents, change history, coverage.

The last four consumers. The interesting one is coverage: a forecast and its
posting are ONE opportunity, but seeing only the posting means the early
signal was missed, and that is a real fact about this system's reach. Dedupe
must not erase it, or the product reports perfect coverage of a lifecycle it
only ever caught the end of.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from nativeforge.repositories.opportunity_identity_repository import (
    resolve_logical_canonical_ids,
)
from nativeforge.services.logical_opportunity_read_service import (
    AGREED,
    CONFLICT,
    LIFECYCLE_COMPLETE,
    LIFECYCLE_FORECAST_ONLY,
    LIFECYCLE_POSTING_ONLY,
    REFINED,
    aggregate_assessments,
    aggregate_documents,
    lifecycle_coverage,
    logical_opportunity_count,
    merge_change_timeline,
)

FC = "L1:ONF181E1|forecast"
PO = "L1:ONF181E1|synopsis"
OTHER = "L1:ONF181E9|synopsis"


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


def relate(conn, *, a=FC, b=PO, relationship="FORECAST_OF", primary=PO, rid=None):
    conn.execute(
        sa.text(
            "INSERT INTO nf_opportunity_identity_relationships "
            "(relationship_id, from_canonical_id, to_canonical_id, relationship,"
            " primary_canonical_id) VALUES (:rid,:a,:b,:rel,:p)"
        ),
        {"rid": rid or f"r-{a}-{b}", "a": a, "b": b, "rel": relationship, "p": primary},
    )


def res_for(conn, ids):
    return resolve_logical_canonical_ids(connection=conn, canonical_ids=ids)


@pytest.fixture()
def pair(connection):
    relate(connection)
    return res_for(connection, [FC, PO])


# ---- A/B. relevance ---------------------------------------------------


def test_a_relevance_assessed_on_the_forecast_continues_after_posting(pair):
    out = aggregate_assessments(
        [
            {"canonical_id": FC, "state": "NATIVE_ELIGIBLE", "observed_at": "1"},
            {"canonical_id": PO, "state": "NATIVE_ELIGIBLE", "observed_at": "2"},
        ],
        resolutions=pair,
    )
    assert out["logical_opportunity_count"] == 1
    entry = out["by_logical_opportunity"][PO]
    assert entry["state"] == "NATIVE_ELIGIBLE"
    assert entry["status"] == AGREED
    assert entry["requires_human"] is False
    assert len(entry["contributing"]) == 2


def test_b_contradictory_relevance_is_a_conflict_not_the_newest_answer(pair):
    out = aggregate_assessments(
        [
            {"canonical_id": FC, "state": "NATIVE_ELIGIBLE", "observed_at": "1"},
            {"canonical_id": PO, "state": "NOT_RELEVANT", "observed_at": "2"},
        ],
        resolutions=pair,
    )
    entry = out["by_logical_opportunity"][PO]
    assert entry["status"] == CONFLICT
    assert entry["state"] is None
    assert entry["competing_states"] == ["NATIVE_ELIGIBLE", "NOT_RELEVANT"]
    assert entry["requires_human"] is True
    assert out["conflict_count"] == 1
    # Both survive.
    assert len(entry["contributing"]) == 2


# ---- C/D. eligibility -------------------------------------------------


def test_c_one_tenant_eligibility_path_across_the_transition(pair):
    out = aggregate_assessments(
        [
            {"canonical_id": FC, "eligibility": "ELIGIBLE", "observed_at": "1"},
            {"canonical_id": PO, "eligibility": "ELIGIBLE", "observed_at": "2"},
        ],
        resolutions=pair,
        state_field="eligibility",
    )
    assert out["logical_opportunity_count"] == 1
    assert out["by_logical_opportunity"][PO]["eligibility"] == "ELIGIBLE"


def test_d_unknown_forecast_eligibility_is_refined_not_contradicted(pair):
    """The forecast could not tell yet. The NOFO can. That is not a conflict."""
    out = aggregate_assessments(
        [
            {
                "canonical_id": FC,
                "eligibility": "ELIGIBILITY_NOT_ASSESSED",
                "observed_at": "1",
            },
            {
                "canonical_id": PO,
                "eligibility": "CONDITIONAL_MATCH",
                "observed_at": "2",
            },
        ],
        resolutions=pair,
        state_field="eligibility",
    )
    entry = out["by_logical_opportunity"][PO]
    assert entry["status"] == REFINED
    assert entry["eligibility"] == "CONDITIONAL_MATCH"
    assert entry["requires_human"] is False
    # The earlier, weaker state is kept as history rather than discarded.
    assert any(
        c["eligibility"] == "ELIGIBILITY_NOT_ASSESSED" for c in entry["contributing"]
    )


def test_d_a_disqualifying_posted_requirement_still_conflicts(pair):
    """Refinement is not a licence to overwrite a definite earlier answer."""
    out = aggregate_assessments(
        [
            {"canonical_id": FC, "eligibility": "ELIGIBLE", "observed_at": "1"},
            {"canonical_id": PO, "eligibility": "DISQUALIFIED", "observed_at": "2"},
        ],
        resolutions=pair,
        state_field="eligibility",
    )
    assert out["by_logical_opportunity"][PO]["status"] == CONFLICT


def test_relevance_and_eligibility_stay_separate_questions(pair):
    relevance = aggregate_assessments(
        [{"canonical_id": PO, "state": "NATIVE_ELIGIBLE"}], resolutions=pair
    )
    eligibility = aggregate_assessments(
        [{"canonical_id": PO, "eligibility": "DISQUALIFIED"}],
        resolutions=pair,
        state_field="eligibility",
    )
    assert relevance["by_logical_opportunity"][PO]["state"] == "NATIVE_ELIGIBLE"
    assert eligibility["by_logical_opportunity"][PO]["eligibility"] == "DISQUALIFIED"


# ---- E/F. documents ---------------------------------------------------


def test_e_forecast_and_posted_documents_form_one_history(pair):
    out = aggregate_documents(
        [
            {
                "canonical_id": FC,
                "document_id": "d1",
                "kind": "early_notice",
                "sha256": "aaa",
                "observed_at": "1",
            },
            {
                "canonical_id": PO,
                "document_id": "d2",
                "kind": "nofo",
                "sha256": "bbb",
                "observed_at": "2",
            },
            {
                "canonical_id": PO,
                "document_id": "d3",
                "kind": "amendment",
                "sha256": "ccc",
                "observed_at": "3",
            },
        ],
        resolutions=pair,
    )
    assert out["logical_opportunity_count"] == 1
    history = out["by_logical_opportunity"][PO]
    assert history["document_count"] == 3
    assert [d["kind"] for d in history["documents"]] == [
        "early_notice",
        "nofo",
        "amendment",
    ]
    assert history["spans_multiple_representations"] is True


def test_f_each_document_still_traces_to_its_own_representation(pair):
    out = aggregate_documents(
        [
            {
                "canonical_id": FC,
                "document_id": "d1",
                "sha256": "aaa",
                "observed_at": "1",
            },
            {
                "canonical_id": PO,
                "document_id": "d2",
                "sha256": "bbb",
                "observed_at": "2",
            },
        ],
        resolutions=pair,
    )
    docs = out["by_logical_opportunity"][PO]["documents"]
    by_id = {d["document_id"]: d for d in docs}
    # Provenance is NOT rewritten to the primary.
    assert by_id["d1"]["canonical_id"] == FC
    assert by_id["d2"]["canonical_id"] == PO
    assert by_id["d1"]["sha256"] == "aaa"


# ---- G/H/I. change history --------------------------------------------


def test_g_forecast_posted_amendment_is_one_timeline(pair):
    out = merge_change_timeline(
        [
            {"canonical_id": FC, "change_type": "FIRST_OBSERVED", "observed_at": "1"},
            {
                "canonical_id": FC,
                "change_type": "DEADLINE_CHANGED",
                "field_name": "close_date",
                "observed_at": "2",
            },
            {
                "canonical_id": PO,
                "change_type": "FORECAST_TO_POSTED",
                "observed_at": "3",
            },
            {
                "canonical_id": PO,
                "change_type": "AMENDMENT_PUBLISHED",
                "observed_at": "4",
            },
        ],
        resolutions=pair,
    )
    assert out["logical_opportunity_count"] == 1
    timeline = out["by_logical_opportunity"][PO]
    assert [e["change_type"] for e in timeline["events"]] == [
        "FIRST_OBSERVED",
        "DEADLINE_CHANGED",
        "FORECAST_TO_POSTED",
        "AMENDMENT_PUBLISHED",
    ]
    assert timeline["contributing_representations"] == sorted([FC, PO])


def test_h_forecast_to_posted_appears_exactly_once(pair):
    out = merge_change_timeline(
        [{"canonical_id": PO, "change_type": "FORECAST_TO_POSTED", "observed_at": "3"}],
        resolutions=pair,
    )
    assert out["by_logical_opportunity"][PO]["forecast_to_posted_count"] == 1
    assert out["invariant_failures"] == []


def test_h_two_transitions_are_an_invariant_failure(pair):
    out = merge_change_timeline(
        [
            {
                "canonical_id": PO,
                "change_type": "FORECAST_TO_POSTED",
                "observed_at": "3",
            },
            {
                "canonical_id": PO,
                "change_type": "FORECAST_TO_POSTED",
                "observed_at": "9",
            },
        ],
        resolutions=pair,
    )
    assert any(
        "forecast_to_posted_emitted_2_times" in f for f in out["invariant_failures"]
    )


def test_i_replaying_the_same_event_contributes_once(pair):
    event = {
        "canonical_id": PO,
        "change_type": "FORECAST_TO_POSTED",
        "observed_at": "3",
    }
    out = merge_change_timeline([event, dict(event)], resolutions=pair)
    assert out["by_logical_opportunity"][PO]["event_count"] == 1
    assert out["invariant_failures"] == []


# ---- J. count ---------------------------------------------------------


def test_j_the_pair_is_one_opportunity(pair):
    assert logical_opportunity_count([FC, PO], resolutions=pair) == 1


# ---- K/L/M. coverage without destroying lifecycle evidence ------------


def test_k_one_opportunity_can_still_expose_a_missed_early_signal(pair):
    """The whole point. One opportunity, and we know we missed the forecast."""
    out = lifecycle_coverage(
        [{"canonical_id": PO, "doc_type": "synopsis"}], resolutions=pair
    )
    assert out["logical_opportunity_count"] == 1
    entry = out["by_logical_opportunity"][PO]
    assert entry["lifecycle"] == LIFECYCLE_POSTING_ONLY
    assert entry["early_signal_was_observed"] is False
    assert entry["early_signal_coverage_gap"] is True
    assert out["early_signal_coverage_gaps"] == [PO]


def test_k_a_complete_lifecycle_is_one_opportunity_and_no_gap(pair):
    out = lifecycle_coverage(
        [
            {"canonical_id": FC, "doc_type": "forecast"},
            {"canonical_id": PO, "doc_type": "synopsis"},
        ],
        resolutions=pair,
    )
    assert out["logical_opportunity_count"] == 1
    assert out["representation_count"] == 2
    entry = out["by_logical_opportunity"][PO]
    assert entry["lifecycle"] == LIFECYCLE_COMPLETE
    assert entry["early_signal_coverage_gap"] is False
    assert out["complete_lifecycles"] == [PO]


def test_l_a_posting_with_no_forecast_does_not_invent_one(pair):
    out = lifecycle_coverage(
        [{"canonical_id": PO, "doc_type": "synopsis"}], resolutions=pair
    )
    entry = out["by_logical_opportunity"][PO]
    assert entry["stages_observed"] == ["PUBLISHED"]
    assert entry["representation_count"] == 1


def test_m_a_forecast_with_no_posting_is_not_a_missed_posting(connection):
    """It may simply not have happened yet. That is an observation, not a
    finding, and Gate 176 owns whether an expected posting is overdue."""
    res = res_for(connection, [FC])
    out = lifecycle_coverage(
        [{"canonical_id": FC, "doc_type": "forecast"}], resolutions=res
    )
    entry = out["by_logical_opportunity"][FC]
    assert entry["lifecycle"] == LIFECYCLE_FORECAST_ONLY
    assert entry["early_signal_coverage_gap"] is False
    assert "missed" not in str(entry).lower()


# ---- N/O/P. things that must not aggregate ----------------------------


def test_n_an_ambiguous_pair_does_not_aggregate(connection):
    relate(connection, primary=None)
    res = res_for(connection, [FC, PO])
    out = aggregate_assessments(
        [
            {"canonical_id": FC, "state": "NATIVE_ELIGIBLE"},
            {"canonical_id": PO, "state": "NOT_RELEVANT"},
        ],
        resolutions=res,
    )
    assert out["logical_opportunity_count"] == 2
    assert out["conflict_count"] == 0  # two opportunities, not one conflicted


def test_o_distinct_opportunities_keep_distinct_histories(connection):
    res = res_for(connection, [PO, OTHER])
    out = aggregate_documents(
        [
            {"canonical_id": PO, "document_id": "d1", "observed_at": "1"},
            {"canonical_id": OTHER, "document_id": "d2", "observed_at": "2"},
        ],
        resolutions=res,
    )
    assert out["logical_opportunity_count"] == 2


@pytest.mark.parametrize("relationship", ["RECURRENCE_OF", "VERSION_OF", "RELATED_TO"])
def test_p_next_cycle_stays_a_different_grant(connection, relationship):
    relate(connection, relationship=relationship)
    res = res_for(connection, [FC, PO])
    out = lifecycle_coverage(
        [
            {"canonical_id": FC, "doc_type": "forecast"},
            {"canonical_id": PO, "doc_type": "synopsis"},
        ],
        resolutions=res,
    )
    assert out["logical_opportunity_count"] == 2


# ---- Q. bypassing the resolver ----------------------------------------


def test_q_without_resolutions_every_layer_fragments():
    """Falsifiability: the defect each aggregation removes, demonstrated."""
    assessments = [
        {"canonical_id": FC, "state": "NATIVE_ELIGIBLE"},
        {"canonical_id": PO, "state": "NATIVE_ELIGIBLE"},
    ]
    docs = [
        {"canonical_id": FC, "document_id": "d1", "observed_at": "1"},
        {"canonical_id": PO, "document_id": "d2", "observed_at": "2"},
    ]
    events = [
        {"canonical_id": FC, "change_type": "FIRST_OBSERVED", "observed_at": "1"},
        {"canonical_id": PO, "change_type": "FORECAST_TO_POSTED", "observed_at": "2"},
    ]

    assert aggregate_assessments(assessments)["logical_opportunity_count"] == 2
    assert aggregate_documents(docs)["logical_opportunity_count"] == 2
    assert merge_change_timeline(events)["logical_opportunity_count"] == 2
    assert logical_opportunity_count([FC, PO]) == 2


# ---- scale ------------------------------------------------------------


@pytest.mark.parametrize("pairs", [10, 100, 1000])
def test_every_layer_costs_one_relationship_query(connection, pairs):
    ids, assessments, docs, events, reps = [], [], [], [], []
    for i in range(pairs):
        fc, po = f"L1:s{i}|forecast", f"L1:s{i}|synopsis"
        relate(connection, a=fc, b=po, primary=po, rid=f"s{i}")
        ids += [fc, po]
        assessments += [
            {"canonical_id": fc, "state": "NATIVE_ELIGIBLE"},
            {"canonical_id": po, "state": "NATIVE_ELIGIBLE"},
        ]
        docs += [
            {"canonical_id": fc, "document_id": f"f{i}", "observed_at": "1"},
            {"canonical_id": po, "document_id": f"p{i}", "observed_at": "2"},
        ]
        events += [
            {
                "canonical_id": po,
                "change_type": "FORECAST_TO_POSTED",
                "observed_at": "2",
            }
        ]
        reps += [
            {"canonical_id": fc, "doc_type": "forecast"},
            {"canonical_id": po, "doc_type": "synopsis"},
        ]

    res = res_for(connection, ids)
    assert res["query_count"] == 1

    assert (
        aggregate_assessments(assessments, resolutions=res)["logical_opportunity_count"]
        == pairs
    )
    assert (
        aggregate_documents(docs, resolutions=res)["logical_opportunity_count"] == pairs
    )
    timeline = merge_change_timeline(events, resolutions=res)
    assert timeline["logical_opportunity_count"] == pairs
    assert timeline["invariant_failures"] == []
    coverage = lifecycle_coverage(reps, resolutions=res)
    assert coverage["logical_opportunity_count"] == pairs
    assert coverage["representation_count"] == pairs * 2
    assert coverage["early_signal_coverage_gaps"] == []


# ---- genericity -------------------------------------------------------


def test_the_intelligence_layers_name_no_publisher():
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
    for leak in ("grants_gov", "search2", "synopsis", "usaspending", "cfda"):
        assert leak not in haystack, f"publisher-specific identifier: {leak}"
