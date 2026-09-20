"""Gate 167L/M/N: rebuild from evidence, the tenancy boundary, and health.

The rebuild runs against a COPY of the database file. Gate 164 established
that: a destructive proof performed on the real database is a proof you can
only run once, and the first mistake is permanent.

Inside the copy the entire canonical graph is deleted and rebuilt from the
source observations and the payload store alone. Same canonical id, same
version ids, same provenance ids - which is only possible because every
identifier is derived from evidence rather than allocated.

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
from nativeforge.services.canonical_opportunity_graph_service import (  # noqa: E402
    build_graph_health,
    compose_opportunity,
    describe_tenancy_boundary,
    graph_health_invariant_failures,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
REAL_CANONICAL = "L1:OBJA2026172662|synopsis"
REPO = pathlib.Path(__file__).resolve().parents[1]

out: dict[str, object] = {}

# ---- 167L + 167N against the real graph ----------------------------
session = SessionLocal()
try:
    tenancy = describe_tenancy_boundary(connection=session)
    out["tenancy_measured"] = tenancy["measured"]
    out["graph_is_global"] = tenancy["graph_is_global"]
    out["tenant_columns_found_in_graph"] = tenancy["tenant_columns_found_in_graph"]
    out["tenant_tables_referencing_an_opportunity"] = tenancy[
        "tenant_tables_referencing_an_opportunity"
    ]

    # One canonical row, however many tenants exist. Counted, not asserted.
    tenant_orgs = int(
        session.execute(
            sa.text("SELECT count(*) FROM organizations")
        ).scalar()
        or 0
    )
    canonical_rows = int(
        session.execute(
            sa.text(
                "SELECT count(*) FROM nf_canonical_opportunities "
                "WHERE canonical_id = :c"
            ),
            {"c": REAL_CANONICAL},
        ).scalar()
        or 0
    )
    out["organizations_present"] = tenant_orgs
    out["canonical_rows_for_the_real_opportunity"] = canonical_rows
    out["no_per_tenant_duplication"] = canonical_rows == 1

    health = build_graph_health(connection=session, canonical_id=REAL_CANONICAL)
    out["health_conditions"] = health["conditions"]
    out["health_named_gaps"] = health["named_gaps"]
    out["canonical_graph_ready"] = health["canonical_graph_ready"]
    out["health_invariant_failures"] = graph_health_invariant_failures(health)

    before = compose_opportunity(connection=session, canonical_id=REAL_CANONICAL)
    out["before_observation_count"] = before["observation_count"]
    out["before_version_count"] = before["version_count"]
    out["before_fields_with_current_value"] = before["fields_with_current_value"]
    out["no_field_has_two_current_values"] = not before[
        "fields_with_multiple_current_values"
    ]
    before_signature = {
        "canonical_id": before["canonical"]["canonical_id"],
        "current_version_id": before["canonical"]["current_version_id"],
        "observations": sorted(r["observation_id"] for r in before["observations"]),
        "versions": sorted(r["version_id"] for r in before["versions"]),
        "provenance": sorted(r["provenance_id"] for r in before["provenance"]),
    }
    out["before_signature"] = before_signature

    db_path = str(
        session.get_bind().url.database  # type: ignore[union-attr]
    )
finally:
    session.close()

# ---- 167M: rebuild inside an isolated copy --------------------------
work = tempfile.mkdtemp(prefix="nf167_rebuild_")
copy_path = os.path.join(work, "rebuild.db")
shutil.copy2(REPO / db_path, copy_path)
out["rebuilt_against"] = "an isolated copy of the database file"

engine = sa.create_engine(f"sqlite+pysqlite:///{copy_path}")
with engine.connect() as connection:
    # Everything needed to rebuild, read BEFORE the graph is destroyed.
    observations = [
        dict(row)
        for row in connection.execute(
            sa.text(
                "SELECT * FROM nf_opportunity_source_observations "
                "WHERE canonical_id = :c ORDER BY observed_at, observation_id"
            ),
            {"c": REAL_CANONICAL},
        )
        .mappings()
        .all()
    ]
    out["observations_available_for_rebuild"] = len(observations)

    for table in (
        "nf_opportunity_field_provenance",
        "nf_opportunity_versions",
        "nf_opportunity_source_observations",
        "nf_canonical_opportunities",
    ):
        connection.execute(sa.text(f"DELETE FROM {table}"))
    connection.commit()

    out["graph_emptied"] = (
        int(
            connection.execute(
                sa.text("SELECT count(*) FROM nf_canonical_opportunities")
            ).scalar()
            or 0
        )
        == 0
    )
    # The evidence ledger is untouched by the demolition.
    out["payload_store_survived_the_rebuild"] = int(
        connection.execute(
            sa.text("SELECT count(*) FROM nf_source_collection_raw_payloads")
        ).scalar()
        or 0
    )

    # ---- replay each observation through the same writer -------------
    import base64

    from nativeforge.repositories.canonical_opportunity_repository import (
        record_observation,
    )
    from nativeforge.services.canonical_opportunity_normalizer_service import (
        extract_records,
        normalize_record,
    )
    from nativeforge.services.opportunity_identity_versioning_service import (
        build_opportunity_identity,
    )
    from nativeforge.services.source_raw_payload_replay_service import (
        replay_payload,
    )

    rebuilt = 0
    unverified = 0
    for observation in observations:
        # Through the SAME verified replay path the audit uses, not a raw
        # column read. A rebuild that helps itself to the bytes without
        # checking the hash proves less than the thing it is rebuilding.
        replay = replay_payload(
            connection=connection,
            organization_id=DEMO,
            attempt_id=observation["raw_payload_attempt_id"],
        )
        if not replay.get("hash_verified") or not replay.get("body_base64"):
            unverified += 1
            continue
        payload = json.loads(
            base64.b64decode(replay["body_base64"]).decode("utf-8")
        )
        records = extract_records(payload=payload, adapter_key="grants_gov_search2")
        target = next(
            (
                r
                for r in records
                if str(r.get("id")) == str(observation["source_record_id"])
            ),
            None,
        )
        if target is None:
            continue
        normalized = normalize_record(
            record=target, adapter_key="grants_gov_search2"
        )
        identity = build_opportunity_identity(
            opportunity_number=normalized["fields"].get("opportunity_number"),
            doc_type=normalized["fields"].get("doc_type"),
            opportunity_id=normalized["fields"].get("source_record_id"),
            aln_list=normalized["fields"].get("assistance_listings"),
            agency_code=normalized["fields"].get("funder_agency_code"),
        )
        record_observation(
            connection=connection,
            source_id=observation["source_id"],
            normalized=normalized,
            raw_payload_sha256=observation["raw_payload_sha256"],
            raw_payload_attempt_id=observation["raw_payload_attempt_id"],
            source_authority_host=observation["source_authority_host"],
            identity=identity,
        )
        rebuilt += 1

    out["observations_rebuilt"] = rebuilt
    out["observations_skipped_unverified"] = unverified
    out["every_rebuilt_observation_verified_its_hash"] = unverified == 0

    after = compose_opportunity(
        connection=connection, canonical_id=REAL_CANONICAL
    )
    out["after_found"] = after["found"]
    after_signature = {
        "canonical_id": after["canonical"]["canonical_id"],
        "current_version_id": after["canonical"]["current_version_id"],
        "observations": sorted(r["observation_id"] for r in after["observations"]),
        "versions": sorted(r["version_id"] for r in after["versions"]),
        "provenance": sorted(r["provenance_id"] for r in after["provenance"]),
    }
    out["after_signature"] = after_signature

    out["same_canonical_identity"] = (
        before_signature["canonical_id"] == after_signature["canonical_id"]
    )
    out["same_version_identities"] = (
        before_signature["versions"] == after_signature["versions"]
    )
    out["same_observation_identities"] = (
        before_signature["observations"] == after_signature["observations"]
    )
    out["same_provenance_identities"] = (
        before_signature["provenance"] == after_signature["provenance"]
    )
    out["same_current_version_pointer"] = (
        before_signature["current_version_id"]
        == after_signature["current_version_id"]
    )
    out["rebuild_reproduces_the_graph"] = all(
        [
            out["same_canonical_identity"],
            out["same_version_identities"],
            out["same_observation_identities"],
            out["same_provenance_identities"],
            out["same_current_version_pointer"],
        ]
    )

engine.dispose()
shutil.rmtree(work, ignore_errors=True)
out["isolated_copy_removed"] = not os.path.exists(copy_path)

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
