"""The checkpoint state, measured rather than asserted in a report.

Every line is a question with one answer the commit is allowed to have.

The raw payload table stores `source_url_fingerprint`, not the URL, so "which
hosts were contacted" is answered from the authorized source id and the robots
evidence table rather than from a URL column that deliberately does not exist.
"""

from __future__ import annotations

import os
import sys
import uuid

import sqlalchemy as sa

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.hermetic_test_guard_service import (  # noqa: E402
    ENV_ALLOW_LIVE_NETWORK,
    live_network_allowed,
)
from nativeforge.services.source_allowlist_projection_service import (  # noqa: E402
    project_allowlist,
)
from nativeforge.services.source_authority_service import (  # noqa: E402
    derive_authorized_source_ids,
)
from nativeforge.services.source_live_fetch_opt_in_service import (  # noqa: E402
    describe_opt_in_state,
    opt_in_invariant_failures,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402
    load_registry_rows,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"

session = SessionLocal()
rows: list[str] = []


def say(label: str, value: object) -> None:
    rows.append(f"{label:<36} {value}")


say("ENV_ALLOW_LIVE_NETWORK absent", ENV_ALLOW_LIVE_NETWORK not in os.environ)
say("live_network_allowed()", live_network_allowed())

projection = project_allowlist(connection=session, organization_id=DEMO)
real_allowlisted = [
    s
    for s in (projection.get("allowlisted_source_ids") or [])
    if not str(s).startswith("nf162.fixture.")
]
say("real sources allowlisted", f"{len(real_allowlisted)}  {real_allowlisted}")

opt_in = describe_opt_in_state(connection=session, organization_id=DEMO)
say("live_fetch opted-in count", opt_in["opted_in_count"])
say("opt-in invariant failures", opt_in_invariant_failures(opt_in) or "none")

real_ids = set(load_registry_rows())
decided = (
    session.execute(
        sa.text("SELECT DISTINCT source_id FROM nf_source_authorization_decisions")
    )
    .scalars()
    .all()
)
say("real sources with decisions", sorted(set(decided) & real_ids))
# Gate 166B: derived from the signed rows, not read from a constant.
AUTHORIZED = derive_authorized_source_ids(connection=session, organization_id=DEMO)
say("derived authorized source ids", sorted(AUTHORIZED))

payloads = session.execute(
    sa.text(
        "SELECT source_id, authorized_source_id, response_status, "
        "payload_size_bytes, payload_sha256, live_fetch_performed, job_id "
        "FROM nf_source_collection_raw_payloads WHERE live_fetch_performed = 1"
    )
).all()
say("rows recording a live fetch", len(payloads))
for row in payloads:
    rows.append(f"    source={row[0]} authorized={row[1]} http={row[2]} bytes={row[3]}")
    rows.append(f"    sha256={row[4]}")

say("unauthorized live rows", len([p for p in payloads if not p[1]]))
say(
    "live rows outside the authorized set",
    len([p for p in payloads if str(p[1]) not in AUTHORIZED]),
)

robots = session.execute(
    sa.text(
        "SELECT host, evaluated_path, decision, http_status, payload_sha256 "
        "FROM nf_source_robots_evidence"
    )
).all()
say("robots evidence rows", len(robots))
for row in robots:
    rows.append(f"    {row[0]}{row[1]}  decision={row[2]}  http={row[3]}")
    rows.append(f"    sha256={row[4]}")

hosts = sorted({str(r[0]) for r in robots})
say("hosts with recorded live contact", hosts)
say("a second authority was contacted", len(hosts) > 1)

# Counted by what IS recorded. An earlier version required
# `response_status == 200`, and the status is NULL by design - never captured,
# not backfilled - so it read 0 for a collection that demonstrably succeeded,
# contradicting the evidence printed two lines above it.
#
# A collection is a payload row for the COLLECTION JOB that names its
# authorization and carries bytes with a verified hash. The HTTP status stays
# out of it: a probe that needs an unknown value is asserting something nobody
# measured.
#
# Discriminated on job_id. A first attempt filtered `"robots" not in source_id`
# - and the source id is the seed id, which contains no such word, so the
# robots preflight counted as a collection. Both rows share the same source and
# the same authorization; the job is what tells a preflight from a collection.
COLLECTION_JOB = "gate163-first-live-collection"
collection_rows = [
    p
    for p in payloads
    if str(p[6]) == COLLECTION_JOB
    and str(p[0]) == SOURCE
    and str(p[1]) == SOURCE
    and int(p[3] or 0) > 0
    and str(p[4] or "")
]
say("recorded search2 collections", len(collection_rows))
say(
    "http status on those rows",
    sorted({str(p[2]) for p in collection_rows}) or "none",
)

attempts = session.execute(
    sa.text(
        "SELECT count(*) FROM nf_source_collection_execution_attempts "
        "WHERE transport_kind <> 'hermetic' OR live_source_call <> 0"
    )
).scalar_one()
say("non-hermetic execution attempts", attempts)

head = (
    session.execute(sa.text("SELECT version_num FROM alembic_version")).scalars().all()
)
say("alembic head", head)

session.close()
print("\n".join(rows))
