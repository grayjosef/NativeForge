"""Gate 164K: the live-collection audit evidence, built canonically.

The one artifact set in this repository that is generated inside
`canonical_build()`. Ambient credential-backed reads raise while it runs, so a
developer's `.env` cannot change a byte of it.

## What "canonical" means here, precisely

```text
inputs      the repository, and an EXPLICIT database connection
not inputs  os.environ, .env, the working directory, provider configuration,
            the wall clock
```

The database is an input rather than ambient state: 164F holds it constant
across every variant, and evidence about a recorded collection has to come
from somewhere.

## No timestamps

Nothing here records when it was generated. A generation timestamp would make
the artifact differ on every run for a reason that says nothing about the
evidence, and "normalize the noncanonical fields" is a harder promise to keep
than simply not emitting them. The evidence carries the timestamps that belong
to it - when the collection was received, when a decision was signed - and
those come from rows.

## The known gap travels with the evidence

`http_status` is absent and says so. An artifact that omitted the gap would
read as complete, and one that filled it in would be inventing a transport
fact. It appears as `null` beside `http_status_known: false` and a note.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_live_collection_audit_artifact_gate164_v1"

ARTIFACT_DIR = "artifacts/live_collection_audit_gate164"

#: The collection this gate audits. A constant, because Gate 164 is about ONE
#: recorded collection; the health and verifier lanes count whatever exists.
COLLECTION_JOB = "gate163-first-live-collection"


def _dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str) + "\n"


def build_audit_artifacts(
    *, connection: Any = None, organization_id: Any = None
) -> dict[str, str]:
    """Compose every Gate 164 evidence file. Reads rows; writes nothing."""
    from nativeforge.services.canonical_artifact_build_context_service import (
        canonical_build,
        describe_scope,
    )

    with canonical_build(reason="gate164 live collection audit evidence") as context:
        from nativeforge.services.live_collection_audit_service import (
            audit_invariant_failures,
            build_live_collection_audit,
        )

        audit = build_live_collection_audit(
            connection=connection,
            organization_id=organization_id,
            job_id=COLLECTION_JOB,
        )
        failures = audit_invariant_failures(audit)

        files: dict[str, str] = {}

        files["build_context.json"] = _dump(
            {
                "schema_version": SCHEMA_VERSION,
                "build_context": context,
                "scope_meaning": describe_scope(context["scope"]),
                "inputs": [
                    "the repository",
                    "an explicit database connection",
                ],
                "not_inputs": [
                    "os.environ",
                    ".env",
                    "the working directory",
                    "provider configuration",
                    "the wall clock",
                ],
                "no_generation_timestamp": (
                    "nothing here records when it was generated. A generation "
                    "time would make the artifact differ on every run for a "
                    "reason that says nothing about the evidence."
                ),
            }
        )

        files["audit_chain.json"] = _dump(
            {
                "schema_version": SCHEMA_VERSION,
                "audit": audit,
                "invariant_failures": failures,
                "audit_chain_complete": audit.get("audit_chain_complete"),
            }
        )

        response = (audit.get("sections") or {}).get("response") or {}
        files["known_evidence_gaps.json"] = _dump(
            {
                "schema_version": SCHEMA_VERSION,
                "known_evidence_gaps": (
                    ["http_status_not_captured"]
                    if not response.get("http_status_known")
                    else []
                ),
                "http_status": response.get("http_status"),
                "http_status_known": response.get("http_status_known"),
                "http_status_note": response.get("http_status_note"),
                "application_errorcode": (
                    (audit.get("sections") or {})
                    .get("normalization", {})
                    .get("application_errorcode")
                ),
                "application_message": (
                    (audit.get("sections") or {})
                    .get("normalization", {})
                    .get("application_message")
                ),
                "these_are_separate_facts": (
                    "an application errorcode is not an HTTP status. Neither "
                    "is inferred from the other, and the absent one is not "
                    "filled in."
                ),
                "a_gap_is_not_corruption": (
                    "the bytes verify, the linkage holds and the collection "
                    "replays. What is missing is one field nobody captured."
                ),
            }
        )

        return files


def write_audit_artifacts(
    *,
    repo_root: Any = None,
    connection: Any = None,
    organization_id: Any = None,
) -> dict[str, Any]:
    """Write the evidence under `repo_root`. The root is explicit, always."""
    import pathlib

    root = pathlib.Path(str(repo_root)) if repo_root else pathlib.Path(".")
    target = root / ARTIFACT_DIR
    target.mkdir(parents=True, exist_ok=True)

    files = build_audit_artifacts(
        connection=connection, organization_id=organization_id
    )
    for name, body in files.items():
        (target / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_dir": ARTIFACT_DIR,
        "file_count": len(files),
        "files": sorted(files),
        "scope": "canonical",
    }
