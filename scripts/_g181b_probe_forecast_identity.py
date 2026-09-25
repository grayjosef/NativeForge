"""Wave 1B survey probe: does a forecast and its posting become ONE opportunity?

`build_opportunity_identity` sets composite_key = "<number>|<doc_type>", so a
forecast keys as PA-26-118|forecast and its later posting as
PA-26-118|synopsis. Whether that produces one canonical opportunity or two
depends on what canonical resolution actually keys on, and that is the whole
load-bearing question of this workstream.

Reading the code suggests a risk. This settles it by observing the pair and
counting rows. Runs against an isolated COPY of the database file and makes no
network request.
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


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("wave 1b probe makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.canonical_opportunity_batch_repository import (  # noqa: E402
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.services.canonical_opportunity_normalizer_service import (  # noqa: E402
    normalize_record,
)
from nativeforge.services.opportunity_identity_versioning_service import (  # noqa: E402
    build_opportunity_identity,
)

ADAPTER = "grants_gov_search2"
FED = "11111111-1111-1111-1111-111111111111"

session = SessionLocal()
try:
    DB_PATH = str(session.get_bind().url.database)  # type: ignore[union-attr]
finally:
    session.close()

work = tempfile.mkdtemp(prefix="nf181b_probe_")
copy_path = os.path.join(work, "probe.db")
shutil.copy2(pathlib.Path(DB_PATH), copy_path)
engine = sa.create_engine(f"sqlite+pysqlite:///{copy_path}")

#: One real-world opportunity, seen twice: first as a forecast, then as the
#: posted synopsis. Same opportunity number, same agency, same ALN.
BASE = {
    "id": "F-181B",
    "number": "O-NF181B-000001",
    "title": "Rural Water Infrastructure Program",
    "agency": "Environmental Protection Agency",
    "agencyCode": "NF181B-EPA",
    "openDate": "03/01/2027",
    "closeDate": "07/01/2027",
    "cfdaList": ["66.468"],
}


def observe(connection, *, doc_type, opp_status, seed):
    rec = dict(BASE, docType=doc_type, oppStatus=opp_status)
    normalized = normalize_record(record=rec, adapter_key=ADAPTER)
    fields = normalized["fields"]
    identity = build_opportunity_identity(
        opportunity_number=fields.get("opportunity_number"),
        doc_type=fields.get("doc_type"),
        opportunity_id=fields.get("source_record_id"),
        aln_list=fields.get("assistance_listings"),
        agency_code=fields.get("funder_agency_code"),
    )
    result = persist_observations(
        connection=connection,
        observations=[
            NormalizedSourceObservation(
                source_id=FED,
                normalized=normalized,
                raw_payload_sha256=f"{seed:064x}",
                identity=identity,
                source_authority_host="fixture.invalid",
            )
        ],
    )
    return identity, result


out: dict[str, object] = {"ran_against": "an isolated copy of the database file"}

with engine.connect() as connection:
    before = int(
        connection.execute(
            sa.text("SELECT count(*) FROM nf_canonical_opportunities")
        ).scalar()
        or 0
    )

    fc_identity, fc_result = observe(
        connection, doc_type="forecast", opp_status="forecasted", seed=1
    )
    syn_identity, syn_result = observe(
        connection, doc_type="synopsis", opp_status="posted", seed=2
    )

    after = int(
        connection.execute(
            sa.text("SELECT count(*) FROM nf_canonical_opportunities")
        ).scalar()
        or 0
    )

    out["forecast_composite_key"] = fc_identity.get("composite_key")
    out["posted_composite_key"] = syn_identity.get("composite_key")
    out["composite_keys_differ"] = fc_identity.get("composite_key") != syn_identity.get(
        "composite_key"
    )
    out["forecast_canonical_id"] = fc_result["results"][0].get("canonical_id")
    out["posted_canonical_id"] = syn_result["results"][0].get("canonical_id")
    out["same_canonical_id"] = fc_result["results"][0].get(
        "canonical_id"
    ) == syn_result["results"][0].get("canonical_id")
    out["canonical_rows_created"] = after - before

    # The question this probe exists to answer.
    out["forecast_and_posting_are_one_opportunity"] = bool(
        out["same_canonical_id"]
    ) and (out["canonical_rows_created"] == 1)

out["network_attempts"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True))
