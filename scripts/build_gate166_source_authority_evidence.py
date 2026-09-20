"""Generate the Gate 166 canonical evidence. Makes no network request."""

from __future__ import annotations

import pathlib
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_authority_artifact_gate166_service import (  # noqa: E402
    write_authority_artifacts,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

session = SessionLocal()
try:
    written = write_authority_artifacts(
        repo_root=str(REPO), connection=session, organization_id=DEMO
    )
finally:
    session.close()

print(f"canonical artifacts: {written['file_count']} files, scope={written['scope']}")
for name in written["files"]:
    print(f"  {name}")
