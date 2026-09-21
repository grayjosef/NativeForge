"""Gate 170C-L: diff, materiality, deadlines, amendments, corroboration,
conflicts, lifecycle and no-op replay. Synthetic. No network.

Runs against a COPY of the database file, so the real graph is never a scratch
pad and there is no residue to clean afterwards.

The two proofs that matter most:

* **170F** - a changed deadline on one canonical identity is a VERSION, and a
  new fiscal year is a different opportunity. A change engine that cannot be
  shown refusing to merge an annual cycle will merge one.
* **170L** - replaying identical evidence writes nothing at all. At thousands
  of repeatedly-polled sources that is the difference between a product and a
  bill.
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
        raise OSError("gate170 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.canonical_opportunity_batch_repository import (  # noqa: E402
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.repositories.opportunity_change_repository import (  # noqa: E402
    ChangeWriteRefused,
    describe_conflicts,
    list_change_events,
    resolve_conflict,
    sync_field_conflicts,
)
from nativeforge.services.canonical_opportunity_normalizer_service import (  # noqa: E402
    normalize_record,
)
from nativeforge.services.opportunity_change_read_model_service import (  # noqa: E402
    build_customer_change_feed,
    read_model_invariant_failures,
)
from nativeforge.services.opportunity_change_taxonomy_service import (  # noqa: E402
    change_invariant_failures,
    classify_change,
    describe_taxonomy,
)
from nativeforge.services.opportunity_identity_versioning_service import (  # noqa: E402
    build_opportunity_identity,
)

ADAPTER = "grants_gov_search2"
REPO = pathlib.Path(__file__).resolve().parents[1]
FED = "nf170.fixture.federal"
AGG = "nf170.fixture.aggregator"

session = SessionLocal()
try:
    DB_PATH = str(session.get_bind().url.database)  # type: ignore[union-attr]
finally:
    session.close()

work = tempfile.mkdtemp(prefix="nf170_sem_")
copy_path = os.path.join(work, "sem.db")
shutil.copy2(REPO / DB_PATH, copy_path)
engine = sa.create_engine(f"sqlite+pysqlite:///{copy_path}")

out: dict[str, object] = {"ran_against": "an isolated copy of the database file"}

BASE = {
    "id": "F-1",
    "number": "O-NF170-000001",
    "title": "FY26 Tribal Resilience Program",
    "agency": "Bureau of Justice Assistance",
    "agencyCode": "NF170-BJA",
    "openDate": "01/05/2027",
    "closeDate": "06/01/2027",
    "oppStatus": "posted",
    "docType": "synopsis",
    "cfdaList": ["16.888"],
}


def record(**kw) -> dict:
    merged = dict(BASE)
    merged.update(kw)
    return merged


def observe(connection, rec: dict, *, source_id: str, seed: int) -> dict:
    normalized = normalize_record(record=rec, adapter_key=ADAPTER)
    identity = build_opportunity_identity(
        opportunity_number=normalized["fields"].get("opportunity_number"),
        doc_type=normalized["fields"].get("doc_type"),
        opportunity_id=normalized["fields"].get("source_record_id"),
        aln_list=normalized["fields"].get("assistance_listings"),
        agency_code=normalized["fields"].get("funder_agency_code"),
    )
    result = persist_observations(
        connection=connection,
        observations=[
            NormalizedSourceObservation(
                source_id=source_id,
                normalized=normalized,
                raw_payload_sha256=f"{seed:064x}",
                identity=identity,
                source_authority_host="fixture.invalid",
            )
        ],
    )
    return {"metrics": result["metrics"], "result": result["results"][0]}


def counts(connection) -> dict:
    return {
        name: int(
            connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar() or 0
        )
        for name, table in (
            ("canonical", "nf_canonical_opportunities"),
            ("versions", "nf_opportunity_versions"),
            ("events", "nf_opportunity_change_events"),
            ("conflicts", "nf_opportunity_field_conflicts"),
        )
    }


# ---- 170B: the taxonomy is complete and rule-backed ------------------
taxonomy = describe_taxonomy()
out["b_every_change_type_is_classified"] = taxonomy["every_type_is_classified"]
out["b_types_without_a_rule"] = taxonomy["types_without_a_rule"]
out["b_change_type_count"] = len(taxonomy["change_types"])
out["b_llm_used"] = taxonomy["llm_used"]

# ---- 170D: materiality, in isolation --------------------------------
materiality_cases = {
    "deadline_shortened": ("close_date", "06/01/2027", "04/01/2027"),
    "deadline_extended": ("close_date", "06/01/2027", "08/01/2027"),
    "cancelled": ("status", "posted", "cancelled"),
    "closed": ("status", "posted", "closed"),
    "forecast_to_posted": ("status", "forecasted", "posted"),
    "reopened": ("status", "closed", "posted"),
    "eligibility": ("eligibility_text", "tribes", "tribes and states"),
    "number_changed": ("opportunity_number", "O-A-1", "O-A-2"),
    "cosmetic_title": ("title", "A B Program", "A  B  Program!"),
    "real_title": ("title", "A B Program", "Z Y Program"),
    "source_url": ("source_url", "https://a.gov/1", "https://a.gov/2"),
}
graded: dict[str, object] = {}
for label, (field, before, after) in materiality_cases.items():
    change = classify_change(
        field_name=field,
        prior_value=before,
        new_value=after,
        deadline_shape="single" if field == "close_date" else None,
    )
    assert not change_invariant_failures(change), (label, change)
    graded[label] = {
        "change_type": change["change_type"],
        "materiality": change["materiality"],
        "rule": change["materiality_rule"],
    }
out["d_materiality_grid"] = graded
out["d_shortened_is_critical"] = (
    graded["deadline_shortened"]["materiality"] == "CRITICAL"
)
out["d_extended_is_material_not_critical"] = (
    graded["deadline_extended"]["materiality"] == "MATERIAL"
)
out["d_direction_produces_different_types"] = (
    graded["deadline_shortened"]["change_type"]
    != graded["deadline_extended"]["change_type"]
)
out["d_cosmetic_title_is_not_material"] = (
    graded["cosmetic_title"]["materiality"] == "NON_MATERIAL"
)
out["d_every_case_named_a_rule"] = all(
    bool(v["rule"]) for v in graded.values()
)

# ---- 170E: multi-valued deadline shapes are not collapsed -----------
shapes: dict[str, object] = {}
for shape in ("single", "dual", "per_region", "phased", "revised", "multi_year"):
    change = classify_change(
        field_name="close_date",
        prior_value="06/01/2027",
        new_value="04/01/2027",
        deadline_shape=shape,
    )
    shapes[shape] = {
        "change_type": change["change_type"],
        "deadline_shape": change["deadline_shape"],
        "notes_multi_valued": any(
            "one_of_several_deadlines" in r for r in change["reasons"]
        ),
    }
out["e_deadline_shapes"] = shapes
out["e_multi_valued_shapes_are_flagged"] = all(
    shapes[s]["notes_multi_valued"] for s in ("dual", "per_region", "phased")
)
out["e_single_shape_is_not_flagged_as_multi"] = not shapes["single"][
    "notes_multi_valued"
]
out["e_shape_travels_with_the_event"] = all(
    shapes[s]["deadline_shape"] == s for s in shapes
)

with engine.connect() as connection:
    # ---- 170C/F: a changed deadline is a VERSION ---------------------
    first = observe(connection, record(), source_id=FED, seed=1)
    canonical_id = first["result"]["canonical_id"]
    out["c_first_events"] = first["metrics"]["change_events_inserted"]
    out["c_first_is_not_an_amendment"] = all(
        e["change_type"] == "FIRST_OBSERVED"
        for e in list_change_events(connection=connection, canonical_id=canonical_id)
    )

    before_amend = counts(connection)
    amended = observe(
        connection, record(closeDate="04/01/2027"), source_id=FED, seed=2
    )
    after_amend = counts(connection)
    out["f_amendment_same_canonical"] = (
        amended["result"]["canonical_id"] == canonical_id
    )
    out["f_amendment_created_no_new_canonical"] = (
        after_amend["canonical"] == before_amend["canonical"]
    )
    out["f_amendment_created_a_version"] = (
        after_amend["versions"] == before_amend["versions"] + 1
    )
    deadline_events = [
        e
        for e in list_change_events(connection=connection, canonical_id=canonical_id)
        if e["field_name"] == "close_date" and e["change_type"] != "FIRST_OBSERVED"
    ]
    out["f_deadline_event_type"] = (
        deadline_events[0]["change_type"] if deadline_events else None
    )
    out["f_deadline_event_materiality"] = (
        deadline_events[0]["materiality"] if deadline_events else None
    )
    out["f_deadline_event_rule"] = (
        deadline_events[0]["materiality_rule"] if deadline_events else None
    )
    out["f_deadline_event_shape"] = (
        deadline_events[0]["deadline_shape"] if deadline_events else None
    )
    out["f_shortened_deadline_is_critical"] = (
        out["f_deadline_event_type"] == "DEADLINE_SHORTENED"
        and out["f_deadline_event_materiality"] == "CRITICAL"
    )

    # ---- negative control: a new fiscal year is a new opportunity ----
    recurrence = observe(
        connection,
        record(
            id="F-9",
            number="O-NF170-000002",
            title="FY27 Tribal Resilience Program",
        ),
        source_id=FED,
        seed=3,
    )
    out["f_recurrence_is_a_different_canonical"] = (
        recurrence["result"]["canonical_id"] != canonical_id
    )
    out["f_recurrence_did_not_become_an_amendment"] = (
        recurrence["metrics"]["canonical_created"] >= 1
    )

    # ---- 170L: identical evidence writes nothing ---------------------
    statements = {"n": 0}

    @sa.event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001,E501
        statements["n"] += 1

    before_noop = counts(connection)
    statements["n"] = 0
    replay = observe(
        connection, record(closeDate="04/01/2027"), source_id=FED, seed=2
    )
    noop_statements = statements["n"]
    after_noop = counts(connection)
    out["l_noop_statements"] = noop_statements
    out["l_noop_wrote_no_version"] = (
        after_noop["versions"] == before_noop["versions"]
    )
    out["l_noop_wrote_no_event"] = after_noop["events"] == before_noop["events"]
    out["l_noop_wrote_no_conflict"] = (
        after_noop["conflicts"] == before_noop["conflicts"]
    )
    out["l_noop_outcome"] = replay["result"]["outcome"]
    out["l_replay_is_a_true_noop"] = bool(
        out["l_noop_wrote_no_version"]
        and out["l_noop_wrote_no_event"]
        and out["l_noop_wrote_no_conflict"]
    )
    out["l_noop_inserted_nothing"] = (
        replay["metrics"]["change_events_inserted"] == 0
        and replay["metrics"]["versions_inserted"] == 0
    )

    # ---- 170H: two sources report the SAME semantic change ------------
    #
    # Two cases, and the difference between them is worth stating.
    #
    # SEQUENTIAL: source B observes the new value AFTER the graph already
    # moved. B's observation produces no diff, because the version chain is
    # shared and already carries the new value. That is the correct answer -
    # B is agreeing with the current state, not reporting a transition - and
    # the important property is that it creates no second event.
    #
    # SAME BATCH: a fleet sweep polls both sources and both report the same
    # transition against the same prior version. Now both produce an
    # identical semantic change, and it must collapse into ONE event with a
    # corroboration count of two rather than two alerts about one deadline.
    before_seq = counts(connection)
    sequential = observe(
        connection,
        record(id="A-1", closeDate="04/01/2027"),
        source_id=AGG,
        seed=4,
    )
    after_seq = counts(connection)
    out["h_sequential_agreement_created_no_event"] = (
        after_seq["events"] == before_seq["events"]
    )
    out["h_sequential_outcome"] = sequential["result"]["outcome"]

    # Now the same-batch case, on a separate opportunity so the chain is
    # clean: both sources see X, then both report Y together.
    batch_base = record(
        id="F-2", number="O-NF170-000003", title="FY26 Shared Sweep Program"
    )
    observe(connection, batch_base, source_id=FED, seed=10)
    observe(
        connection, dict(batch_base, id="A-2"), source_id=AGG, seed=11
    )
    batch_canonical = "L1:ONF170000003|synopsis"
    before_batch = counts(connection)

    def sweep_observation(source_id: str, record_id: str, seed: int):
        moved = dict(batch_base, id=record_id, closeDate="03/01/2027")
        normalized = normalize_record(record=moved, adapter_key=ADAPTER)
        identity = build_opportunity_identity(
            opportunity_number=normalized["fields"].get("opportunity_number"),
            doc_type=normalized["fields"].get("doc_type"),
            opportunity_id=normalized["fields"].get("source_record_id"),
            aln_list=normalized["fields"].get("assistance_listings"),
            agency_code=normalized["fields"].get("funder_agency_code"),
        )
        return NormalizedSourceObservation(
            source_id=source_id,
            normalized=normalized,
            raw_payload_sha256=f"{seed:064x}",
            identity=identity,
            source_authority_host="fixture.invalid",
        )

    sweep = persist_observations(
        connection=connection,
        observations=[
            sweep_observation(FED, "F-2", 12),
            sweep_observation(AGG, "A-2", 13),
        ],
    )
    after_batch = counts(connection)
    out["h_sweep_metrics"] = {
        k: v
        for k, v in sweep["metrics"].items()
        if k.startswith("change_events") or k == "versions_inserted"
    }
    out["h_events_added_by_the_sweep"] = (
        after_batch["events"] - before_batch["events"]
    )

    sweep_events = [
        e
        for e in list_change_events(
            connection=connection, canonical_id=batch_canonical
        )
        if e["field_name"] == "close_date"
        and e["change_type"] == "DEADLINE_SHORTENED"
    ]
    out["h_sweep_produced_one_event"] = len(sweep_events) == 1
    out["h_corroborating_source_count"] = (
        sweep_events[0]["corroborating_source_count"] if sweep_events else None
    )
    out["h_corroborated_by"] = (
        json.loads(sweep_events[0]["corroborated_by_json"] or "[]")
        if sweep_events
        else []
    )
    out["h_timing_still_visible"] = bool(
        sweep_events
        and sweep_events[0]["first_reported_at"]
        and sweep_events[0]["last_reported_at"]
    )
    out["h_one_semantic_event_not_two"] = bool(
        out["h_sweep_produced_one_event"]
        and out["h_corroborating_source_count"] == 2
        and out["h_sequential_agreement_created_no_event"]
    )

    # ---- 170I: two sources disagree ----------------------------------
    observe(
        connection,
        record(id="A-1", closeDate="09/30/2027", title="FY26 Tribal Resilience"),
        source_id=AGG,
        seed=5,
    )
    conflict_sync = sync_field_conflicts(
        connection=connection, canonical_id=canonical_id
    )
    connection.commit()
    out["i_conflict_sync"] = conflict_sync
    open_conflicts = describe_conflicts(
        connection=connection, canonical_id=canonical_id
    )
    out["i_open_conflict_fields"] = sorted(
        str(c["field_name"]) for c in open_conflicts
    )
    out["i_conflict_recorded"] = bool(open_conflicts)
    if open_conflicts:
        row = open_conflicts[0]
        out["i_competing_values"] = json.loads(row["competing_values_json"])
        out["i_has_first_detected"] = bool(row["first_detected_at"])
        out["i_has_last_observed"] = bool(row["last_observed_at"])
        out["i_competing_source_count"] = row["competing_source_count"]
        out["i_state"] = row["conflict_state"]
        out["i_both_sides_preserved"] = len(out["i_competing_values"]) >= 2

    # An unsigned resolution is refused.
    try:
        resolve_conflict(
            connection=connection,
            canonical_id=canonical_id,
            field_name="close_date",
            resolved_by="",
            rule="",
            evidence={},
        )
        out["i_unsigned_resolution_refused"] = False
    except ChangeWriteRefused as exc:
        out["i_unsigned_resolution_refused"] = True
        out["i_unsigned_resolution_reasons"] = exc.reasons

    # A signed one is accepted, and the competing facts survive it.
    resolved = resolve_conflict(
        connection=connection,
        canonical_id=canonical_id,
        field_name="close_date",
        resolved_by="MAYHEM",
        rule="federal_source_is_authoritative_for_this_field",
        evidence={"preferred_source": FED, "basis": "fixture"},
    )
    connection.commit()
    out["i_resolution_recorded"] = resolved["resolved"]
    out["i_resolution_deleted_nothing"] = resolved["rows_deleted"] == 0
    out["i_competing_facts_preserved"] = resolved["competing_facts_preserved"]
    still_open = describe_conflicts(
        connection=connection, canonical_id=canonical_id
    )
    out["i_still_open_fields_after_resolution"] = sorted(
        str(c["field_name"]) for c in still_open
    )
    # Only close_date was resolved. The title conflict is untouched and must
    # stay open - resolving one field must not resolve another, which the
    # first version of this check asserted by looking at the whole list.
    out["i_resolved_field_is_no_longer_open"] = "close_date" not in (
        out["i_still_open_fields_after_resolution"]
    )
    out["i_unresolved_field_is_still_open"] = "title" in (
        out["i_still_open_fields_after_resolution"]
    )
    provenance_rows = int(
        connection.execute(
            sa.text(
                "SELECT count(*) FROM nf_opportunity_field_provenance WHERE "
                "canonical_id = :c AND field_name = 'close_date'"
            ),
            {"c": canonical_id},
        ).scalar()
        or 0
    )
    out["i_close_date_provenance_rows_after_resolution"] = provenance_rows
    out["i_resolution_kept_every_fact"] = provenance_rows >= 3

    # ---- 170J: the lifecycle -----------------------------------------
    # Each step must be genuinely new CONTENT, or the writer correctly
    # recognises it as a replay and writes nothing - which the first version
    # of this fixture ran into: reopening with the same fields as an earlier
    # version produced no event, and the test read that as "REOPENED is not
    # supported" rather than "this is the same version again".
    lifecycle: list[str] = []
    for status, seed, note in (
        ("closed", 6, " (closed)"),
        ("posted", 7, " (reopened)"),
    ):
        observe(
            connection,
            record(
                closeDate="04/01/2027",
                oppStatus=status,
                title=BASE["title"] + note,
            ),
            source_id=FED,
            seed=seed,
        )
        events = [
            e
            for e in list_change_events(
                connection=connection, canonical_id=canonical_id
            )
            if e["field_name"] == "status"
        ]
        lifecycle = sorted({str(e["change_type"]) for e in events})
    out["j_status_change_types"] = lifecycle
    out["j_posted_to_closed_seen"] = "POSTED_TO_CLOSED" in lifecycle
    out["j_reopened_seen"] = "REOPENED" in lifecycle
    canonical_total = int(
        connection.execute(
            sa.text(
                "SELECT count(*) FROM nf_canonical_opportunities WHERE "
                "canonical_id = :c"
            ),
            {"c": canonical_id},
        ).scalar()
        or 0
    )
    out["j_lifecycle_did_not_fork_the_opportunity"] = canonical_total == 1

    # ---- 170K: the customer-safe read model ---------------------------
    feed = build_customer_change_feed(
        connection=connection, canonical_id=canonical_id, limit=50
    )
    out["k_change_count"] = feed["change_count"]
    out["k_customer_safe"] = feed["customer_safe"]
    out["k_forbidden_markers_found"] = feed["forbidden_markers_found"]
    out["k_invariant_failures"] = read_model_invariant_failures(feed)
    out["k_notifications_sent"] = feed["notifications_sent"]
    # Show the deadline change, not whichever event sorted first - a sample
    # of "UNKNOWN_CHANGE" tells a reader nothing about the model.
    sample = next(
        (c for c in feed["changes"] if c["what_changed"] == "DEADLINE_SHORTENED"),
        feed["changes"][0] if feed["changes"] else {},
    )
    out["k_sample_keys"] = sorted(sample)
    out["k_sample"] = {
        k: sample.get(k)
        for k in (
            "what_changed",
            "importance",
            "explanation",
            "has_unresolved_conflict",
            "reported_by_sources",
        )
    }
    out["k_no_unknown_change_events_reach_a_customer"] = not [
        c for c in feed["changes"] if c["what_changed"] == "UNKNOWN_CHANGE"
    ]
    out["k_importance_is_customer_vocabulary"] = all(
        c["importance"]
        in ("act_now", "review_soon", "for_information", "no_action", "unclassified")
        for c in feed["changes"]
    )

    out["final_counts"] = counts(connection)

engine.dispose()
shutil.rmtree(work, ignore_errors=True)
out["isolated_copy_removed"] = not os.path.exists(copy_path)

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["rows_written_to_the_real_database"] = 0
print(json.dumps(out, sort_keys=True, default=str))
