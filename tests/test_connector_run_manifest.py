"""Connector run manifest (additive diagnostics)."""

import uuid

from nativeforge.services.source_connectors.connector_run_manifest import (
    build_connector_run_manifest_v1,
)


def test_manifest_stable_keys() -> None:
    sid = uuid.uuid4()
    rid = uuid.uuid4()
    m = build_connector_run_manifest_v1(
        source_registry_id=sid,
        intake_run_id=rid,
        dry_run=True,
        connector_run_id="run-x",
        fixture_row_count=3,
        normalized_candidate_count=3,
    )
    assert m["schema_version"] == "nf_connector_run_manifest_v1"
    assert m["dry_run"] is True
    assert m["ids"]["source_registry_id"] == str(sid)
    assert m["ids"]["intake_run_id"] == str(rid)
    assert m["counts"]["fixture_rows"] == 3
