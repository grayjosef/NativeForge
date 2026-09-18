"""What the first live collection actually recorded.

`http status` and `bytes` printed as None, which means the keys I read from
`execute_request` were not the keys it returns. The bytes persisted correctly -
the hash verified on readback - so the question is which metadata fields are
NULL on the row and whether an execution attempt was recorded at all.
"""

from __future__ import annotations

import json
import sys

import sqlalchemy as sa

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402

SOURCE = "nf-seed-2026-api-grants-gov-search2"

session = SessionLocal()

print("=== the persisted payload rows")
rows = session.execute(
    sa.text(
        "SELECT attempt_id, job_id, source_id, response_status, media_type, "
        "encoding, payload_size_bytes, payload_sha256, payload_status, "
        "collector_invoked, live_fetch_performed, authorized_source_id, "
        "body_storage_mode, fact_status, source_url_fingerprint, "
        "response_header_metadata, parser_version, blocked_reasons "
        "FROM nf_source_collection_raw_payloads ORDER BY received_at"
    )
).mappings().all()
for row in rows:
    print(f"  attempt_id      {row['attempt_id']}")
    print(f"    job_id        {row['job_id']}")
    print(f"    source_id     {row['source_id']}")
    print(f"    http status   {row['response_status']!r}")
    print(f"    bytes         {row['payload_size_bytes']!r}")
    print(f"    sha256        {row['payload_sha256']}")
    print(f"    media_type    {row['media_type']!r}")
    print(f"    status        {row['payload_status']!r}")
    print(f"    collector     {row['collector_invoked']!r}")
    print(f"    live_fetch    {row['live_fetch_performed']!r}")
    print(f"    authorized    {row['authorized_source_id']!r}")
    print(f"    storage       {row['body_storage_mode']!r}")
    print(f"    url fp        {row['source_url_fingerprint']!r}")
    print(f"    headers       {str(row['response_header_metadata'])[:200]!r}")
    print()

print("=== execution attempts")
attempts = session.execute(
    sa.text("SELECT count(*) FROM nf_source_collection_execution_attempts")
).scalar_one()
print(f"  total {attempts}")

print()
print("=== job rows (must be 0)")
jobs = session.execute(
    sa.text("SELECT count(*) FROM nf_source_collection_jobs")
).scalar_one()
print(f"  total {jobs}")

print()
print("=== what execute_request actually returns")
from nativeforge.services.hermetic_source_transport_service import (  # noqa: E402
    HermeticTransportRegistry,
)
from nativeforge.services.source_collection_request_builder_service import (  # noqa: E402
    build_source_request,
)
from nativeforge.services.source_collection_transport_service import (  # noqa: E402
    HERMETIC,
    execute_request,
)

registry = HermeticTransportRegistry()
registry.register_ok("https://fixtures.invalid/nf163/keys", b'{"probe":true}')
built = build_source_request(
    source_definition={
        "source_id": "nf163.fixture.keys",
        "endpoint": "https://fixtures.invalid/nf163/keys",
        "method": "GET",
    }
)
probe = execute_request(
    request=built["transport_request"],
    transport_kind=HERMETIC,
    transport=registry.transport,
    policy={"execution_allowed": True, "hermetic_transport_allowed": True},
)
print(f"  keys: {json.dumps(sorted(probe), indent=None)}")
for key in sorted(probe):
    value = probe[key]
    if isinstance(value, (str, int, float, bool)) or value is None:
        print(f"    {key:<28} {str(value)[:70]!r}")

session.close()
