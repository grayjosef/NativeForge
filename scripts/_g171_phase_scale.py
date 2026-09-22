"""Gate 171R: the CURRENT stack, measured with all three adapter shapes.

Not a comparison with any previous gate. Gate 170 left a specific UNKNOWN on
the record - 559/sec to 256/sec at 50k, with the split between added indexed
rows and machine variance unmeasured - and re-running historical shapes to
produce a flattering delta would not resolve it. It is carried forward
verbatim instead.

What IS measured here is new: a mixed fleet. Until now every scale run used
one record shape. This one interleaves three, because the cost that matters at
1,000 sources is the cost of a batch containing several source families at
once, not the cost of a homogeneous one.

Runs against a COPY of the database. Writes nothing real. No network.
"""

from __future__ import annotations

import json
import os
import pathlib
import resource
import shutil
import socket
import sys
import tempfile
import time

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate171 scale makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.canonical_opportunity_batch_repository import (  # noqa: E402,E501
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.services.source_adapter_contract_service import (  # noqa: E402
    PageCursor,
    identity_for_normalized,
    normalized_envelope_for,
)
from nativeforge.services.source_adapters import (  # noqa: E402
    bia_program_page_html as bia,
)
from nativeforge.services.source_adapters import (  # noqa: E402
    federal_register_documents_json as fr,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
BATCH_SIZE = 500
SCALE = 6000

#: Gate 170's finding, carried forward unchanged. It is NOT re-measured here
#: and NOT explained here.
GATE170_UNKNOWN = {
    "measurement": "~256 observations/sec at 50,000 on the current stack",
    "gate168_shipped": "559/sec at 50,000",
    "unknown": (
        "the split between added indexed-row cost (about six change-event "
        "rows and two blocking-key rows per observation) and machine variance "
        "between runs on different days is NOT measured"
    ),
    "not_claimed": "no causation is asserted without an A/B on the same machine",
}


def fr_body(index: int) -> bytes:
    return json.dumps(
        {
            "count": 1,
            "next_page_url": None,
            "results": [
                {
                    "document_number": f"2026-{index:06d}",
                    "title": f"Notice of funding {index}",
                    "type": "Notice",
                    "publication_date": "2026-09-01",
                    "agencies": [{"name": f"Agency {index % 40}"}],
                    "html_url": f"https://www.federalregister.gov/d/{index}",
                    "comments_close_on": "2026-11-01",
                }
            ],
        }
    ).encode("utf-8")


def bia_body(index: int) -> bytes:
    return (
        f"<html><head><title>Program {index}</title></head><body>"
        f"<h1>Program {index}</h1><p>Text for program {index}.</p>"
        f'<a href="/media/nofo-{index}.pdf">NOFO</a></body></html>'
    ).encode()


def grants_gov_shaped(index: int) -> dict:
    """The third shape, built as a normalized envelope directly.

    Grants.gov's own adapter parses its API payload; reproducing that payload
    here would be testing a fixture generator. What this phase needs from the
    third family is its FIELD shape - ten canonical fields, an ALN, an agency
    code - so it is built at the envelope layer and said so.
    """
    from nativeforge.services.canonical_opportunity_normalizer_service import (
        content_fingerprint,
        lifecycle_for_status,
    )

    fields = {
        "source_record_id": f"GG-{index}",
        "opportunity_number": f"O-NF171-{index:06d}",
        "title": f"Federal opportunity {index}",
        "doc_type": "synopsis",
        "funder_agency_name": f"Agency {index % 40}",
        "funder_agency_code": f"NF171-{index % 40:02d}",
        "open_date": "01/05/2027",
        "close_date": "04/01/2027",
        "status": "posted",
        "assistance_listings": [f"{10 + index % 80}.{index % 1000:03d}"],
    }
    return {
        "schema_version": "nf_gate171_scale_envelope_v1",
        "parser_version": "1",
        "parser_name": "grants_gov_shaped_scale_fixture",
        "adapter_key": "grants_gov_search2",
        "parseable": True,
        "fields": fields,
        "fields_absent": [],
        "fields_not_supported": [
            "eligibility_text",
            "funding_amount_max",
            "funding_amount_min",
            "source_url",
        ],
        "content_fingerprint": content_fingerprint(fields),
        "source_record_id": fields["source_record_id"],
        # DERIVED, not written by hand. This fixture originally said "open",
        # which is not in the canonical lifecycle vocabulary, and every batch
        # containing one rolled back on the CHECK constraint - taking 500
        # valid records with it. A hand-built envelope that skips the
        # normalizer has to use the normalizer's own mapping.
        "lifecycle_state": lifecycle_for_status(fields["status"]),
        "provenance_fields_present": [
            "close_date",
            "open_date",
            "opportunity_number",
            "status",
            "title",
        ],
        "provenance_fields_missing": [],
    }


out: dict[str, object] = {"schema_version": "nf_gate171_scale_v1"}
out["gate170_unknown_carried_forward"] = GATE170_UNKNOWN

session = SessionLocal()
try:
    db_path = str(session.get_bind().url.database)
finally:
    session.close()

work = tempfile.mkdtemp(prefix="nf171_scale_")
copy_path = os.path.join(work, "scale.db")
shutil.copy2(REPO / db_path, copy_path)
start_bytes = os.path.getsize(copy_path)
engine = sa.create_engine(f"sqlite+pysqlite:///{copy_path}")

statements = {"count": 0}


@sa.event.listens_for(engine, "before_cursor_execute")
def _count(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001,E501
    statements["count"] += 1


fr_descriptor = fr.build_descriptor()
bia_descriptor = bia.build_descriptor()

normalize_seconds = 0.0
identity_seconds = 0.0
built: list[NormalizedSourceObservation] = []

build_started = time.perf_counter()
for index in range(SCALE):
    shape = index % 3
    started = time.perf_counter()
    if shape == 0:
        records = fr.read_records(
            descriptor=fr_descriptor,
            body_bytes=fr_body(index),
            media_type="application/json",
            cursor=PageCursor(max_pages=1, max_records=20),
        )
        envelope = normalized_envelope_for(records[0], adapter_key=fr.ADAPTER_KEY)
        source_id = "nf171.scale.federal_register"
    elif shape == 1:
        records = bia.read_records(
            descriptor=bia.build_descriptor(
                source_id="nf171.scale.bia",
                source_url=f"https://www.bia.gov/service/grants/p{index}",
            ),
            body_bytes=bia_body(index),
            media_type="text/html",
            cursor=PageCursor(max_pages=1, max_records=1),
        )
        envelope = normalized_envelope_for(records[0], adapter_key=bia.ADAPTER_KEY)
        source_id = "nf171.scale.bia"
    else:
        envelope = grants_gov_shaped(index)
        source_id = "nf171.scale.grants_gov"
    normalize_seconds += time.perf_counter() - started

    started = time.perf_counter()
    identity = identity_for_normalized(envelope, source_id=source_id)
    identity_seconds += time.perf_counter() - started

    built.append(
        NormalizedSourceObservation(
            source_id=source_id,
            normalized=envelope,
            raw_payload_sha256=f"{index:064x}",
            identity=identity,
            source_authority_host="scale.invalid",
        )
    )
out["build_seconds"] = round(time.perf_counter() - build_started, 4)

statements["count"] = 0
# Outcomes are ACCUMULATED, not assumed. The first run of this phase reported
# 3,490 observations/sec from 108 statements and 0.0 MB of growth - a rate for
# writes that never happened. A throughput number without a landed-row count
# beside it is not a measurement.
totals: dict[str, int] = {}
rejections: dict[str, int] = {}
write_started = time.perf_counter()
with engine.connect() as connection:
    for offset in range(0, len(built), BATCH_SIZE):
        result = persist_observations(
            connection=connection, observations=built[offset : offset + BATCH_SIZE]
        )
        for name, value in (result.get("metrics") or {}).items():
            if isinstance(value, int):
                totals[name] = totals.get(name, 0) + value
        for record in result.get("results") or []:
            if str(record.get("outcome")) in ("rejected", "failed"):
                for reason in record.get("reasons") or []:
                    rejections[str(reason)] = rejections.get(str(reason), 0) + 1
write_seconds = time.perf_counter() - write_started
engine.dispose()

out["write_metrics"] = dict(sorted(totals.items()))
out["rejection_reasons"] = dict(sorted(rejections.items()))
out["observations_landed"] = int(totals.get("observations_inserted", 0)) + int(
    totals.get("observations_versioned", 0)
)
out["observations_rejected"] = int(totals.get("observations_rejected", 0))
out["every_observation_landed"] = out["observations_landed"] == len(built)

end_bytes = os.path.getsize(copy_path)
peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
shutil.rmtree(work, ignore_errors=True)

out["observations"] = len(built)
out["shapes_interleaved"] = 3

# ---- 171X: a throughput number is invalid without landed rows ----
#
# The standing rule this gate earned. The first run of this phase reported
# 3,490 observations/sec while every batch rolled back and nothing was
# written. The rate was arithmetically correct and completely meaningless.
# So the landed count is reported BESIDE the rate, the rate is named for
# what it measures, and a run that landed nothing refuses to call its rate
# write throughput at all.
attempted = len(built)
landed = int(out["observations_landed"])
rolled_back = int(totals.get("batch_failures", 0))

out["attempted_observations"] = attempted
out["landed_observations"] = landed
out["rejected_observations"] = int(out["observations_rejected"])
out["failed_observations"] = int(totals.get("observations_failed", 0))
out["rolled_back_batches"] = rolled_back
out["duration_seconds"] = round(write_seconds, 4)
out["statements"] = statements["count"]
out["statements_per_observation"] = round(statements["count"] / attempted, 3)
out["statements_per_landed_observation"] = (
    round(statements["count"] / landed, 3) if landed else None
)
out["throughput_is_valid"] = landed > 0 and rolled_back == 0
out["observations_per_second"] = (
    round(landed / max(write_seconds, 1e-9), 1) if landed else None
)
out["observations_per_second_meaning"] = (
    "LANDED observations per second"
    if landed
    else "NOT REPORTED - nothing landed, so there is no write throughput"
)
out["canonical_write_seconds"] = round(write_seconds, 4)
out["normalization_seconds"] = round(normalize_seconds, 4)
out["normalization_ms_per_observation"] = round(
    normalize_seconds * 1000 / len(built), 4
)
out["identity_seconds"] = round(identity_seconds, 4)
out["identity_ms_per_observation"] = round(identity_seconds * 1000 / len(built), 4)
out["db_growth_mb"] = round((end_bytes - start_bytes) / (1024 * 1024), 2)
out["db_growth_kb_per_observation"] = round(
    (end_bytes - start_bytes) / 1024 / len(built), 2
)
out["peak_memory_mb"] = round(peak_kb / 1024, 1)
out["memory_note"] = (
    "RUSAGE_SELF is this PROCESS's peak, which includes the harness holding "
    "the built observations. It is not the writer's footprint alone, and is "
    "reported as the process figure rather than relabelled."
)
out["rows_written_to_the_real_database"] = 0

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
