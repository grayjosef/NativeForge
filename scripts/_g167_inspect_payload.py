"""Gate 167A: what is actually IN the Gate 163 payload? Reads only, no network.

Normalizing a field the payload does not contain is fabrication, so this reads
the stored bytes and reports the field names that are really there, with their
values for the one opportunity Gate 167E will persist.
"""

from __future__ import annotations

import base64
import json
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_raw_payload_replay_service import (  # noqa: E402
    replay_payload,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
ATTEMPT = "c35bbe3c1a84b1f42362ed65c114e44838d14758a274c994fe144732b310c4ec"

out: dict[str, object] = {}
session = SessionLocal()
try:
    replay = replay_payload(
        connection=session, organization_id=DEMO, attempt_id=ATTEMPT
    )
    body = base64.b64decode(replay.get("body_base64") or b"")
    out["bytes"] = len(body)

    parsed = json.loads(body.decode("utf-8"))
    out["top_level_keys"] = sorted(parsed)
    out["errorcode"] = parsed.get("errorcode")
    out["msg"] = parsed.get("msg")

    data = parsed.get("data") or {}
    out["data_keys"] = sorted(data)
    out["hit_count"] = len(data.get("oppHits") or [])

    hits = data.get("oppHits") or []
    if hits:
        first = hits[0]
        out["opp_hit_fields"] = sorted(first)
        out["opp_hit_values"] = {k: first[k] for k in sorted(first)}

    # What ELSE the envelope carries - counts, facets - so the normalizer
    # does not mistake a facet for an opportunity field.
    out["non_hit_data_fields"] = {
        k: (type(v).__name__ if not isinstance(v, (int, str)) else v)
        for k, v in sorted(data.items())
        if k != "oppHits"
    }
finally:
    session.close()

print(json.dumps(out, indent=2, sort_keys=True, default=str))
