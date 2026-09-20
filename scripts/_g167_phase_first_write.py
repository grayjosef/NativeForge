"""Gate 167E/F: the first canonical opportunity, from stored evidence. No network.

Every value comes from bytes already on disk. The payload is replayed through
the Gate 160 store, parsed by the adapter's declared parser, and written to the
graph. Nothing is fetched and the payload store is not written to.

167F is folded in here because idempotency is only meaningful against the write
it repeats: the same payload is recorded twice in one process and the graph is
counted before and after.
"""

from __future__ import annotations

import base64
import json
import socket
import sys
import uuid

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
    record_observation,
)
from nativeforge.services.canonical_opportunity_normalizer_service import (  # noqa: E402
    extract_records,
    normalize_record,
    normalizer_invariant_failures,
)
from nativeforge.services.opportunity_identity_versioning_service import (  # noqa: E402
    build_opportunity_identity,
    identity_invariant_failures,
)
from nativeforge.services.source_definition_service import (  # noqa: E402
    build_source_definition,
)
from nativeforge.services.source_raw_payload_replay_service import (  # noqa: E402
    replay_payload,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"
ATTEMPT = "c35bbe3c1a84b1f42362ed65c114e44838d14758a274c994fe144732b310c4ec"
EXPECTED_SHA = "eb4cc7cb76d278b9f4ab9aad7375ed0481faa6ff5827786452dc74491c0f1712"
EXPECTED_NUMBER = "O-BJA-2026-172662"

out: dict[str, object] = {}
session = SessionLocal()


def graph_counts() -> dict[str, int]:
    return {
        name: int(
            session.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar() or 0
        )
        for name, table in (
            ("canonical", "nf_canonical_opportunities"),
            ("observations", "nf_opportunity_source_observations"),
            ("versions", "nf_opportunity_versions"),
            ("provenance", "nf_opportunity_field_provenance"),
        )
    }


try:
    # ---- the evidence, replayed ---------------------------------------
    replay = replay_payload(
        connection=session, organization_id=DEMO, attempt_id=ATTEMPT
    )
    body = base64.b64decode(replay.get("body_base64") or b"")
    out["replayed_bytes"] = len(body)
    out["hash_verified"] = bool(replay.get("hash_verified"))

    payload = json.loads(body.decode("utf-8"))

    definition = build_source_definition(
        source_id=SOURCE, connection=session, organization_id=DEMO
    )
    adapter_key = definition.get("adapter_key")
    out["adapter_key"] = adapter_key
    out["source_authority_host"] = definition.get("authority_host")

    records = extract_records(payload=payload, adapter_key=adapter_key)
    out["records_in_payload"] = len(records)

    normalized = normalize_record(record=records[0], adapter_key=adapter_key)
    out["normalizer_invariant_failures"] = normalizer_invariant_failures(normalized)
    out["normalized_fields"] = normalized["fields"]
    out["fields_absent"] = normalized["fields_absent"]
    out["fields_not_supported"] = normalized["fields_not_supported"]
    out["provenance_fields_missing"] = normalized["provenance_fields_missing"]
    out["lifecycle_state"] = normalized["lifecycle_state"]

    # Nothing invented: every normalized field must appear in the raw record.
    raw_keys = set(records[0])
    from nativeforge.services.canonical_opportunity_normalizer_service import (
        OPPORTUNITY_PARSERS,
    )

    field_map = OPPORTUNITY_PARSERS[adapter_key]["field_map"]
    out["every_field_traces_to_a_raw_key"] = all(
        field_map[name] in raw_keys for name in normalized["fields"]
    )

    identity = build_opportunity_identity(
        opportunity_number=normalized["fields"].get("opportunity_number"),
        doc_type=normalized["fields"].get("doc_type"),
        opportunity_id=normalized["fields"].get("source_record_id"),
        aln_list=normalized["fields"].get("assistance_listings"),
        agency_code=normalized["fields"].get("funder_agency_code"),
    )
    out["identity_invariant_failures"] = identity_invariant_failures(identity)
    out["composite_key"] = identity["composite_key"]
    out["identity_layer"] = identity["identity_layer"]

    before = graph_counts()
    out["counts_before"] = before

    # ---- 167E: the first real write -----------------------------------
    first = record_observation(
        connection=session,
        source_id=SOURCE,
        normalized=normalized,
        raw_payload_sha256=EXPECTED_SHA,
        raw_payload_attempt_id=ATTEMPT,
        source_authority_host=definition.get("authority_host"),
        identity=identity,
        http_status=None,
    )
    out["first_write"] = first
    after_first = graph_counts()
    out["counts_after_first"] = after_first

    # ---- 167F: the identical replay ------------------------------------
    second = record_observation(
        connection=session,
        source_id=SOURCE,
        normalized=normalized,
        raw_payload_sha256=EXPECTED_SHA,
        raw_payload_attempt_id=ATTEMPT,
        source_authority_host=definition.get("authority_host"),
        identity=identity,
        http_status=None,
    )
    out["second_write"] = second
    after_second = graph_counts()
    out["counts_after_second"] = after_second

    out["replay_is_idempotent"] = after_first == after_second
    out["replay_wrote_nothing"] = not any(
        [
            second["wrote_canonical"],
            second["wrote_observation"],
            second["wrote_version"],
            second["provenance_rows_written"],
        ]
    )
    out["identity_stable_across_replay"] = (
        first["canonical_id"] == second["canonical_id"]
        and first["version_id"] == second["version_id"]
        and first["observation_id"] == second["observation_id"]
    )
    out["replay_identity_outcome"] = second["identity_outcome"]

    # ---- what the graph now says --------------------------------------
    canonical = (
        session.execute(
            sa.text(
                "SELECT * FROM nf_canonical_opportunities WHERE canonical_id = :c"
            ),
            {"c": first["canonical_id"]},
        )
        .mappings()
        .first()
    )
    out["canonical_row"] = dict(canonical) if canonical else None

    observation = (
        session.execute(
            sa.text(
                "SELECT * FROM nf_opportunity_source_observations "
                "WHERE observation_id = :o"
            ),
            {"o": first["observation_id"]},
        )
        .mappings()
        .first()
    )
    out["observation_row"] = dict(observation) if observation else None

    provenance = (
        session.execute(
            sa.text(
                "SELECT field_name, field_value, source_id, raw_payload_sha256, "
                "is_current_canonical FROM nf_opportunity_field_provenance "
                "WHERE canonical_id = :c ORDER BY field_name"
            ),
            {"c": first["canonical_id"]},
        )
        .mappings()
        .all()
    )
    out["provenance_rows"] = [dict(r) for r in provenance]
    out["every_provenance_row_names_evidence"] = all(
        str(r["raw_payload_sha256"]) == EXPECTED_SHA for r in provenance
    )

    # ---- the things that must NOT have changed -------------------------
    out["opportunity_number_preserved"] = (
        str((canonical or {}).get("normalized_opportunity_number") or "")
        == EXPECTED_NUMBER.replace("-", "")
    )
    out["source_record_id_preserved"] = (
        str((observation or {}).get("source_record_id") or "") == "363308"
    )
    out["http_status_remains_unknown"] = (observation or {}).get(
        "http_status"
    ) is None

    payload_after = (
        session.execute(
            sa.text(
                "SELECT payload_sha256, payload_size_bytes FROM "
                "nf_source_collection_raw_payloads WHERE attempt_id = :a"
            ),
            {"a": ATTEMPT},
        )
        .mappings()
        .first()
    )
    out["raw_payload_immutable"] = bool(
        payload_after
        and payload_after["payload_sha256"] == EXPECTED_SHA
        and int(payload_after["payload_size_bytes"]) == 11131
    )
finally:
    session.close()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
