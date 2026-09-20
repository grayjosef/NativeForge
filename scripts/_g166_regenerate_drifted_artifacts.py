"""Regenerate ONLY the two artifacts Gate 166 drifted, inside a canonical build.

Gate 163 regenerated artifacts and a local Auth0 configuration silently flipped
`provider_env_present_actual` false->true, deleting three real blockers from
committed evidence. It was caught by reading the diff, not by a test.

So this writes inside `canonical_build()` - the Gate 164 boundary, which
refuses ambient credential-backed reads at `auth_environment_overlay` - and
prints every changed line for inspection rather than reporting success.

Reads and writes files. Makes no network request.
"""

from __future__ import annotations

import difflib
import pathlib
import socket
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate166 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

from nativeforge.services import (  # noqa: E402
    operational_health_artifact_gate154_service as g154,
)
from nativeforge.services import (  # noqa: E402
    source_monitoring_artifact_gate143_service as g143,
)
from nativeforge.services.canonical_artifact_build_context_service import (  # noqa: E402
    canonical_build,
)

REPO = pathlib.Path(__file__).resolve().parents[1]

TARGETS = (
    ("gate143", g143.ARTIFACT_DIR, g143.build_source_monitoring_artifacts),
    ("gate154", g154.ARTIFACT_DIR, g154.build_operational_health_artifacts),
)

changed_lines = 0
with canonical_build(reason="gate166_registry_and_file_count_drift"):
    for label, directory, build in TARGETS:
        target = REPO / directory
        built = build()
        print(f"=== {label}: {directory}")
        for name, body in sorted(built.items()):
            path = target / name
            before = path.read_text(encoding="utf-8") if path.is_file() else ""
            if before == body:
                continue
            diff = list(
                difflib.unified_diff(
                    before.splitlines(),
                    body.splitlines(),
                    fromfile=f"committed/{name}",
                    tofile=f"rebuilt/{name}",
                    lineterm="",
                    n=0,
                )
            )
            for line in diff:
                if line.startswith(("---", "+++", "@@")):
                    continue
                if line.startswith(("+", "-")):
                    changed_lines += 1
                    print(f"    {line}")
            path.write_text(body, encoding="utf-8")
            print(f"    -> rewrote {name}")

print()
print(f"changed_lines={changed_lines}")
print(f"network_attempts={_NETWORK['attempts']}")
