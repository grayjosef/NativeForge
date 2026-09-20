"""Gate 167G/H/I/J: versions, multi-source identity, conflict, forecast->posted.

Synthetic throughout. The real Gate 163 opportunity is never touched: every
record here uses a reserved opportunity number, reserved source ids, and
payload hashes that are REAL sha256 digests of the synthetic fixture bytes -
not sha-shaped strings, because a fixture that fakes its own evidence hash
cannot prove anything about a store whose whole job is evidence.

Makes no network request.
"""

from __future__ import annotations

import hashlib
import json
import socket
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate167 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.canonical_opportunity_repository import (  # noqa: E402
    AMENDMENT_OR_VERSION,
    SAME_OPPORTUNITY_DIFFERENT_SOURCE,
    record_observation,
)
from nativeforge.services.canonical_opportunity_normalizer_service import (  # noqa: E402
    normalize_record,
)
from nativeforge.services.opportunity_identity_versioning_service import (  # noqa: E402
    build_opportunity_identity,
)

ADAPTER = "grants_gov_search2"
SOURCE_A = "nf167.fixture.source-a"
SOURCE_B = "nf167.fixture.source-b"
NUMBER = "O-NF167-0001"

BASE = {
    "id": "900001",
    "number": NUMBER,
    "title": "Synthetic Tribal Resilience Program",
    "agency": "Synthetic Agency",
    "agencyCode": "NF167-AG",
    "openDate": "01/05/2027",
    "closeDate": "04/01/2027",
    "oppStatus": "posted",
    "docType": "synopsis",
    "cfdaList": ["99.999"],
}


def fixture_sha(record: dict) -> str:
    """A real digest of the real (synthetic) bytes this fixture stands for."""
    body = json.dumps({"data": {"oppHits": [record]}}, sort_keys=True).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def write(session, *, record: dict, source_id: str) -> dict:
    normalized = normalize_record(record=record, adapter_key=ADAPTER)
    identity = build_opportunity_identity(
        opportunity_number=normalized["fields"].get("opportunity_number"),
        doc_type=normalized["fields"].get("doc_type"),
        opportunity_id=normalized["fields"].get("source_record_id"),
        aln_list=normalized["fields"].get("assistance_listings"),
        agency_code=normalized["fields"].get("funder_agency_code"),
    )
    return record_observation(
        connection=session,
        source_id=source_id,
        normalized=normalized,
        raw_payload_sha256=fixture_sha(record),
        source_authority_host="fixture.invalid",
        identity=identity,
    )


out: dict[str, object] = {}
session = SessionLocal()
try:
    real_before = int(
        session.execute(
            sa.text(
                "SELECT count(*) FROM nf_canonical_opportunities "
                "WHERE canonical_id LIKE 'L1:OBJA%'"
            )
        ).scalar()
        or 0
    )

    # ---- 167G: one field at a time ------------------------------------
    first = write(session, record=dict(BASE), source_id=SOURCE_A)
    canonical_id = first["canonical_id"]
    out["g_first_version"] = first["version_id"]

    retitled = dict(BASE, title="Synthetic Tribal Resilience Program (Revised)")
    second = write(session, record=retitled, source_id=SOURCE_A)
    out["g_title_change_new_version"] = (
        second["version_id"] != first["version_id"] and second["wrote_version"]
    )
    out["g_title_change_same_canonical"] = second["canonical_id"] == canonical_id
    out["g_title_changed_fields"] = second.get("changed_fields")
    out["g_title_is_material"] = second.get("is_material")
    out["g_title_outcome"] = second["identity_outcome"]

    moved = dict(retitled, closeDate="05/15/2027")
    third = write(session, record=moved, source_id=SOURCE_A)
    out["g_deadline_change_new_version"] = third["wrote_version"]
    out["g_deadline_changed_fields"] = third.get("changed_fields")
    out["g_deadline_is_material"] = third.get("is_material")

    closed = dict(moved, oppStatus="closed")
    fourth = write(session, record=closed, source_id=SOURCE_A)
    out["g_status_change_new_version"] = fourth["wrote_version"]

    versions = (
        session.execute(
            sa.text(
                "SELECT version_id, supersedes_version_id, "
                "superseded_by_version_id, is_material, changed_fields_json "
                "FROM nf_opportunity_versions WHERE canonical_id = :c "
                "ORDER BY created_at"
            ),
            {"c": canonical_id},
        )
        .mappings()
        .all()
    )
    out["g_version_count"] = len(versions)
    out["g_previous_versions_retained"] = len(versions) == 4
    # Every version but the newest must point forward; the newest must not.
    out["g_lineage_is_a_chain"] = all(
        row["superseded_by_version_id"] for row in versions[:-1]
    ) and not versions[-1]["superseded_by_version_id"]

    canonical_row = (
        session.execute(
            sa.text("SELECT * FROM nf_canonical_opportunities WHERE canonical_id = :c"),
            {"c": canonical_id},
        )
        .mappings()
        .first()
    )
    out["g_current_pointer_is_newest"] = (
        canonical_row["current_version_id"] == versions[-1]["version_id"]
    )
    out["g_lifecycle_advanced"] = canonical_row["lifecycle_state"]
    out["g_current_close_date"] = canonical_row["current_close_date"]

    # ---- 167H: two sources, one opportunity ---------------------------
    from_b = dict(BASE, id="B-77", title=BASE["title"])
    b_first = write(session, record=from_b, source_id=SOURCE_B)
    out["h_same_canonical"] = b_first["canonical_id"] == canonical_id
    out["h_outcome"] = b_first["identity_outcome"]
    out["h_outcome_is_multi_source"] = (
        b_first["identity_outcome"] == SAME_OPPORTUNITY_DIFFERENT_SOURCE
    )

    observations = (
        session.execute(
            sa.text(
                "SELECT source_id, source_record_id, raw_payload_sha256 "
                "FROM nf_opportunity_source_observations WHERE canonical_id = :c"
            ),
            {"c": canonical_id},
        )
        .mappings()
        .all()
    )
    out["h_observation_count"] = len(observations)
    out["h_distinct_sources"] = sorted({r["source_id"] for r in observations})
    out["h_distinct_evidence_refs"] = len(
        {r["raw_payload_sha256"] for r in observations}
    )
    out["h_source_record_ids_preserved_separately"] = sorted(
        {str(r["source_record_id"]) for r in observations}
    )
    out["h_one_canonical_for_two_sources"] = (
        len({r["source_id"] for r in observations}) == 2
    )

    # ---- 167I: the two sources disagree --------------------------------
    conflicting = dict(from_b, closeDate="06/30/2027", id="B-77")
    b_conflict = write(session, record=conflicting, source_id=SOURCE_B)
    out["i_conflicts_detected"] = b_conflict["conflicts_detected"]
    out["i_conflict_on_close_date"] = "close_date" in (
        b_conflict["conflicts_detected"] or []
    )

    close_rows = (
        session.execute(
            sa.text(
                "SELECT source_id, field_value, is_current_canonical, "
                "conflict_group, raw_payload_sha256 "
                "FROM nf_opportunity_field_provenance "
                "WHERE canonical_id = :c AND field_name = 'close_date' "
                "ORDER BY source_id, field_value"
            ),
            {"c": canonical_id},
        )
        .mappings()
        .all()
    )
    out["i_close_date_rows"] = [dict(r) for r in close_rows]
    out["i_both_values_retained"] = len(
        {r["field_value"] for r in close_rows}
    ) >= 2
    out["i_both_sources_identified"] = len(
        {r["source_id"] for r in close_rows}
    ) == 2
    groups = {r["conflict_group"] for r in close_rows if r["conflict_group"]}
    out["i_conflict_group_links_both_sides"] = len(groups) == 1
    # Nothing was overwritten: the incumbent value is still on file.
    out["i_no_silent_overwrite"] = any(
        r["field_value"] == "05/15/2027" for r in close_rows
    )

    after_conflict = (
        session.execute(
            sa.text(
                "SELECT has_field_conflicts, current_close_date FROM "
                "nf_canonical_opportunities WHERE canonical_id = :c"
            ),
            {"c": canonical_id},
        )
        .mappings()
        .first()
    )
    out["i_canonical_flags_the_conflict"] = bool(
        after_conflict["has_field_conflicts"]
    )
    # The disputed value did NOT quietly become the canonical one.
    out["i_disputed_value_did_not_become_canonical"] = (
        after_conflict["current_close_date"] != "06/30/2027"
    )

    # ---- 167J: forecast and the synopsis it becomes ---------------------
    forecast = dict(BASE, docType="forecast", oppStatus="forecasted", id="F-1")
    f = write(session, record=forecast, source_id=SOURCE_A)
    out["j_forecast_canonical_id"] = f["canonical_id"]
    out["j_forecast_is_a_distinct_canonical"] = f["canonical_id"] != canonical_id

    group_rows = (
        session.execute(
            sa.text(
                "SELECT canonical_id, doc_type, lifecycle_state FROM "
                "nf_canonical_opportunities WHERE opportunity_number_group = :g "
                "ORDER BY doc_type"
            ),
            {"g": "ONF1670001"},
        )
        .mappings()
        .all()
    )
    out["j_group_rows"] = [dict(r) for r in group_rows]
    out["j_forecast_and_synopsis_share_a_group"] = len(group_rows) == 2
    out["j_transition_is_queryable"] = sorted(
        r["doc_type"] for r in group_rows
    ) == ["forecast", "synopsis"]
    out["j_lifecycle_states"] = sorted(r["lifecycle_state"] for r in group_rows)

    # ---- the real opportunity was not disturbed -------------------------
    real_after = int(
        session.execute(
            sa.text(
                "SELECT count(*) FROM nf_canonical_opportunities "
                "WHERE canonical_id LIKE 'L1:OBJA%'"
            )
        ).scalar()
        or 0
    )
    out["real_opportunity_untouched"] = real_before == real_after == 1

    out["g_amendment_outcome_used"] = AMENDMENT_OR_VERSION
finally:
    session.close()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
