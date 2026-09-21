"""Gate 169E/K/L/M/R: persisted relationships, review, reversibility, replay.

Runs against a COPY of the database file, so the real graph is never used as a
scratch pad and there is no residue to clean up.

The load-bearing proof is 169L. An approved merge is applied, then revoked,
and the observation / version / provenance counts are compared before, during
and after. They must be identical at all three points - because a merge here
is a relationship row and never a rewrite, so there was never anywhere for the
evidence to go.

Makes no network request.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import socket
import sys
import tempfile

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate169 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.canonical_opportunity_batch_repository import (  # noqa: E402
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.repositories.opportunity_identity_repository import (  # noqa: E402
    ACTION_APPROVE_MERGE,
    ACTION_DEFER,
    ACTION_MARK_RELATED,
    ACTION_REJECT_MERGE,
    IdentityWriteRefused,
    backfill_blocking_keys,
    describe_identity_graph,
    generate_candidates,
    list_pending_candidates,
    record_candidate,
    record_relationship,
    resolve_candidate,
    revoke_relationship,
)
from nativeforge.services.canonical_opportunity_normalizer_service import (  # noqa: E402
    normalize_record,
)
from nativeforge.services.cross_source_identity_service import (  # noqa: E402
    build_blocking_keys,
    decide_match,
    describe_identity,
)
from nativeforge.services.opportunity_identity_versioning_service import (  # noqa: E402
    build_fuzzy_fallback_key,
    build_opportunity_identity,
)

ADAPTER = "grants_gov_search2"
REPO = pathlib.Path(__file__).resolve().parents[1]
FEDERAL = "nf169.fixture.federal"
AGGREGATOR = "nf169.fixture.aggregator"

TITLE = "FY26 Coordinated Tribal Assistance Solicitation"

session = SessionLocal()
try:
    DB_PATH = str(session.get_bind().url.database)  # type: ignore[union-attr]
finally:
    session.close()

work = tempfile.mkdtemp(prefix="nf169_graph_")
copy_path = os.path.join(work, "graph.db")
shutil.copy2(REPO / DB_PATH, copy_path)
engine = sa.create_engine(f"sqlite+pysqlite:///{copy_path}")

out: dict[str, object] = {"ran_against": "an isolated copy of the database file"}


def record_for(**kw) -> dict:
    base = {
        "id": "F-1",
        "number": "O-NF169-000001",
        "title": TITLE,
        "agency": "Bureau of Justice Assistance",
        "agencyCode": "NF169-BJA",
        "openDate": "01/05/2027",
        "closeDate": "04/01/2027",
        "oppStatus": "posted",
        "docType": "synopsis",
        "cfdaList": ["16.999"],
    }
    base.update(kw)
    return base


def observe(connection, record: dict, *, source_id: str, sha: str) -> dict:
    """Persist one observation, choosing the identity layer the evidence allows.

    A record with no published number cannot carry an L1 identity - the
    validator refuses it, correctly, because an L1 without a number is not an
    L1. Such a record gets the identity service's L4 fuzzy fallback, which is
    marked provisional and which migration 0054 refuses to let settle.
    """
    normalized = normalize_record(record=record, adapter_key=ADAPTER)
    fields = normalized["fields"]
    if fields.get("opportunity_number"):
        identity = build_opportunity_identity(
            opportunity_number=fields.get("opportunity_number"),
            doc_type=fields.get("doc_type"),
            opportunity_id=fields.get("source_record_id"),
            aln_list=fields.get("assistance_listings"),
            agency_code=fields.get("funder_agency_code"),
        )
    else:
        identity = build_fuzzy_fallback_key(
            agency=fields.get("funder_agency_name"),
            title=fields.get("title"),
            earliest_deadline_date=fields.get("close_date"),
            source_id=source_id,
        )
        # The canonical row needs a doc_type; the fuzzy key does not carry one.
        identity = dict(identity, doc_type=fields.get("doc_type") or "unknown")
    result = persist_observations(
        connection=connection,
        observations=[
            NormalizedSourceObservation(
                source_id=source_id,
                normalized=normalized,
                raw_payload_sha256=sha,
                identity=identity,
                source_authority_host="fixture.invalid",
            )
        ],
    )
    return {
        "normalized": normalized,
        "identity": identity,
        "result": result["results"][0],
    }


def counts(connection) -> dict:
    return {
        name: int(
            connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar() or 0
        )
        for name, table in (
            ("observations", "nf_opportunity_source_observations"),
            ("versions", "nf_opportunity_versions"),
            ("provenance", "nf_opportunity_field_provenance"),
            ("canonical", "nf_canonical_opportunities"),
        )
    }


with engine.connect() as connection:
    # ---- 169E: one opportunity, two sources that agree on the number --
    federal = observe(
        connection, record_for(), source_id=FEDERAL, sha=f"{1:064x}"
    )
    agg_same_number = observe(
        connection,
        record_for(id="A-1", title="Coordinated Tribal Assistance Solicitation"),
        source_id=AGGREGATOR,
        sha=f"{2:064x}",
    )
    out["e_same_canonical_when_both_cite_the_number"] = (
        federal["result"]["canonical_id"] == agg_same_number["result"]["canonical_id"]
    )
    canonical_id = federal["result"]["canonical_id"]
    observations = connection.execute(
        sa.text(
            "SELECT source_id FROM nf_opportunity_source_observations "
            "WHERE canonical_id = :c ORDER BY source_id"
        ),
        {"c": canonical_id},
    ).scalars().all()
    out["e_two_source_observations"] = sorted({str(s) for s in observations}) == [
        AGGREGATOR,
        FEDERAL,
    ]
    provenance_sources = connection.execute(
        sa.text(
            "SELECT DISTINCT source_id FROM nf_opportunity_field_provenance "
            "WHERE canonical_id = :c ORDER BY source_id"
        ),
        {"c": canonical_id},
    ).scalars().all()
    out["e_two_provenance_chains"] = len({str(s) for s in provenance_sources}) == 2

    # ---- the aggregator that does NOT cite the number -----------------
    #
    # A separate canonical opportunity, because nothing links them
    # deterministically. This is the case a fuzzy matcher would merge.
    unnumbered = observe(
        connection,
        record_for(id="A-2", number="", title=TITLE),
        source_id=AGGREGATOR,
        sha=f"{3:064x}",
    )
    out["k_unnumbered_record_outcome"] = unnumbered["result"]["outcome"]
    unnumbered_canonical = unnumbered["result"]["canonical_id"]
    out["k_unnumbered_is_a_separate_canonical"] = (
        unnumbered_canonical != canonical_id
    )

    backfill = backfill_blocking_keys(connection=connection)
    out["blocking_backfill"] = backfill

    # ---- 169P: candidate generation is a bounded key lookup -----------
    left_identity = describe_identity(
        opportunity_number="O-NF169-000001",
        doc_type="synopsis",
        agency_code="NF169-BJA",
        title=TITLE,
    )
    candidates = generate_candidates(
        connection=connection,
        keys=build_blocking_keys(left_identity),
        exclude_canonical_id=canonical_id,
    )
    out["p_candidate_count"] = candidates["candidate_count"]
    out["p_widest_bucket"] = candidates["widest_bucket"]
    out["p_keys_probed"] = candidates["keys_probed"]
    out["p_found_the_unnumbered_twin"] = (
        unnumbered_canonical in candidates["candidate_ids"]
    )

    # ---- 169D/K: the decision, and the candidate it produces ----------
    right_identity = describe_identity(
        doc_type="synopsis", agency_code="NF169-BJA", title=TITLE
    )
    decision = decide_match(left=left_identity, right=right_identity)
    out["k_decision"] = decision["decision"]
    out["k_decision_layer"] = decision["identity_layer"]
    out["k_machine_may_settle"] = decision["machine_may_settle"]

    # A machine may NOT write this as a merge. Proven by attempting it.
    try:
        record_relationship(
            connection=connection,
            from_canonical_id=canonical_id,
            to_canonical_id=unnumbered_canonical,
            relationship="SAME_AS",
            match_decision=decision["decision"],
            identity_layer=decision["identity_layer"],
            decided_by="derived",
        )
        out["l4_automatic_merge_was_refused"] = False
        out["l4_refusal_reasons"] = []
    except IdentityWriteRefused as exc:
        out["l4_automatic_merge_was_refused"] = True
        out["l4_refusal_reasons"] = exc.reasons

    candidate = record_candidate(
        connection=connection,
        canonical_a=canonical_id,
        canonical_b=unnumbered_canonical,
        proposed_relationship="SAME_AS",
        match_decision=decision["decision"],
        identity_layer=decision["identity_layer"],
        evidence=decision["evidence"],
        reasons=decision["reasons"],
        confidence=decision["confidence"],
    )
    connection.commit()
    out["k_candidate_written"] = candidate["written"]
    candidate_id = candidate["candidate_id"]

    # Recording it twice is one review item, not two.
    again = record_candidate(
        connection=connection,
        canonical_a=unnumbered_canonical,
        canonical_b=canonical_id,
        proposed_relationship="SAME_AS",
        match_decision=decision["decision"],
        identity_layer=decision["identity_layer"],
    )
    out["k_reversed_pair_is_the_same_candidate"] = (
        again["candidate_id"] == candidate_id and not again["written"]
    )

    pending = list_pending_candidates(connection=connection)
    out["k_pending_queue_size"] = len(pending)
    out["k_queue_holds_our_candidate"] = any(
        p["candidate_id"] == candidate_id for p in pending
    )

    # An unsigned resolution is refused.
    try:
        resolve_candidate(
            connection=connection,
            candidate_id=candidate_id,
            action=ACTION_APPROVE_MERGE,
            reviewer="",
        )
        out["k_unsigned_review_refused"] = False
    except IdentityWriteRefused as exc:
        out["k_unsigned_review_refused"] = True
        out["k_unsigned_review_reasons"] = exc.reasons

    out["k_review_actions_available"] = sorted(
        [ACTION_APPROVE_MERGE, ACTION_REJECT_MERGE, ACTION_MARK_RELATED, ACTION_DEFER]
    )

    # ---- 169L: approve, then reverse, losing nothing ------------------
    before_merge = counts(connection)
    approved = resolve_candidate(
        connection=connection,
        candidate_id=candidate_id,
        action=ACTION_APPROVE_MERGE,
        reviewer="MAYHEM",
        notes="fixture approval for the reversibility proof",
    )
    connection.commit()
    during_merge = counts(connection)
    relationship_id = (approved["relationship_written"] or {}).get(
        "relationship_id"
    )
    out["l_merge_written"] = bool(
        (approved["relationship_written"] or {}).get("written")
    )
    out["l_merge_decided_by_human"] = approved["review_state"] == "approved_merge"

    graph = describe_identity_graph(connection=connection, canonical_id=canonical_id)
    out["l_same_as_visible_after_merge"] = (
        unnumbered_canonical in graph["settled_same_as"]
    )

    revoked = revoke_relationship(
        connection=connection,
        relationship_id=relationship_id,
        revoked_by="MAYHEM",
        reason="fixture: proving the merge is reversible",
    )
    connection.commit()
    after_revoke = counts(connection)
    out["l_revoked"] = revoked["revoked"]
    out["l_rows_deleted_by_revocation"] = revoked["rows_deleted"]

    graph_after = describe_identity_graph(
        connection=connection, canonical_id=canonical_id
    )
    out["l_same_as_gone_after_revocation"] = (
        unnumbered_canonical not in graph_after["settled_same_as"]
    )
    graph_with_history = describe_identity_graph(
        connection=connection, canonical_id=canonical_id, include_revoked=True
    )
    out["l_revoked_merge_still_on_record"] = (
        graph_with_history["relationship_count"] > graph_after["relationship_count"]
    )

    out["l_counts_before_merge"] = before_merge
    out["l_counts_during_merge"] = during_merge
    out["l_counts_after_revocation"] = after_revoke
    out["l_nothing_lost_by_merging"] = before_merge == during_merge
    out["l_nothing_lost_by_unmerging"] = during_merge == after_revoke
    out["l_merge_is_fully_reversible"] = (
        before_merge == during_merge == after_revoke
    )

    # An unsigned revocation is refused.
    try:
        revoke_relationship(
            connection=connection,
            relationship_id=relationship_id,
            revoked_by="",
            reason="",
        )
        out["l_unsigned_revocation_refused"] = False
    except IdentityWriteRefused:
        out["l_unsigned_revocation_refused"] = True

    # ---- 169M: the relationship graph holds more than merges ----------
    recurrence = observe(
        connection,
        record_for(
            id="F-2",
            number="O-NF169-000002",
            title=TITLE.replace("FY26", "FY27"),
        ),
        source_id=FEDERAL,
        sha=f"{4:064x}",
    )
    recurrence_canonical = recurrence["result"]["canonical_id"]
    recurrence_decision = decide_match(
        left=left_identity,
        right=describe_identity(
            opportunity_number="O-NF169-000002",
            doc_type="synopsis",
            agency_code="NF169-BJA",
            title=TITLE.replace("FY26", "FY27"),
        ),
    )
    out["m_recurrence_decision"] = recurrence_decision["decision"]
    out["m_recurrence_relationship"] = recurrence_decision["relationship"]
    written = record_relationship(
        connection=connection,
        from_canonical_id=recurrence_canonical,
        to_canonical_id=canonical_id,
        relationship=recurrence_decision["relationship"],
        match_decision=recurrence_decision["decision"],
        identity_layer=recurrence_decision["identity_layer"],
        evidence=recurrence_decision["evidence"],
        reasons=recurrence_decision["reasons"],
        confidence=recurrence_decision["confidence"],
        decided_by="derived",
    )
    connection.commit()
    out["m_recurrence_recorded_without_review"] = bool(written["written"])
    out["m_recurrence_is_not_a_merge"] = (
        recurrence_decision["relationship"] != "SAME_AS"
    )

    final_graph = describe_identity_graph(
        connection=connection, canonical_id=canonical_id
    )
    out["m_related_by_kind"] = final_graph["related_by_kind"]
    out["m_settled_same_as_after_revocation"] = final_graph["settled_same_as"]
    out["m_canonical_ids_are_distinct_for_the_recurrence"] = (
        recurrence_canonical != canonical_id
    )

    # ---- 169R: replay determinism -------------------------------------
    #
    # The derived decision recomputes identically from the same inputs. The
    # HUMAN decision is read from the persisted review facts - recomputing it
    # would be inventing a reviewer's answer.
    replayed = decide_match(left=left_identity, right=right_identity)
    out["r_derived_decision_replays_identically"] = (
        replayed["decision"] == decision["decision"]
        and replayed["identity_layer"] == decision["identity_layer"]
        and replayed["reasons"] == decision["reasons"]
    )
    stored = connection.execute(
        sa.text(
            "SELECT review_state, reviewed_by, reviewed_at FROM "
            "nf_opportunity_identity_candidates WHERE candidate_id = :c"
        ),
        {"c": candidate_id},
    ).mappings().first()
    out["r_human_decision_is_persisted_not_recomputed"] = bool(
        stored and stored["reviewed_by"] == "MAYHEM" and stored["reviewed_at"]
    )
    out["r_review_state_on_record"] = stored["review_state"] if stored else None

engine.dispose()
shutil.rmtree(work, ignore_errors=True)
out["isolated_copy_removed"] = not os.path.exists(copy_path)

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["rows_written_to_the_real_database"] = 0
print(json.dumps(out, sort_keys=True, default=str))
