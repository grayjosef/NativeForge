"""Rewrite the committed artifacts for the source-collection runtime gates.

Four artifact sets carry registry counts and lane readiness in their text, so
adding the Grants.gov registry row and making the live transport
authorization-aware changes what their builders produce. The tests compare the
builder's output to what is on disk, so the files have to be rewritten rather
than the comparison relaxed.

Prints a per-file verdict. `unchanged` is as informative as `rewritten`: a
builder whose output did not move when the registry grew is one that was not
reading the registry.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, "src")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

from nativeforge.services import (  # noqa: E402
    source_authorization_artifact_gate162_service as g162,
)
from nativeforge.services import (  # noqa: E402
    source_collector_execution_artifact_gate161_service as g161,
)
from nativeforge.services import (  # noqa: E402
    source_monitoring_artifact_gate143_service as g143,
)
from nativeforge.services.source_raw_payload_artifact_gate160_service import (  # noqa: E402
    ARTIFACT_DIR as G160_DIR,
)
from nativeforge.services.source_raw_payload_artifact_gate160_service import (  # noqa: E402
    build_raw_payload_artifacts,
)

SETS = (
    ("gate143", g143.ARTIFACT_DIR, g143.build_source_monitoring_artifacts),
    ("gate160", G160_DIR, build_raw_payload_artifacts),
    ("gate161", g161.ARTIFACT_DIR, g161.build_execution_artifacts),
    ("gate162", g162.ARTIFACT_DIR, g162.build_authorization_artifacts),
)

rewritten = 0
unchanged = 0
for label, directory, builder in SETS:
    target = REPO_ROOT / directory
    target.mkdir(parents=True, exist_ok=True)
    for name, body in builder().items():
        path = target / name
        before = path.read_text(encoding="utf-8") if path.exists() else None
        if before == body:
            unchanged += 1
            continue
        path.write_text(body, encoding="utf-8")
        rewritten += 1
        print(f"  rewritten  {label}  {name}")

print(f"rewritten={rewritten} unchanged={unchanged}")
