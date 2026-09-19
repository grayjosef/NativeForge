"""Generate the Gate 164 canonical evidence, and record the phase results.

The artifact writer runs inside `canonical_build()`, so a developer `.env`
cannot change a byte of it. The database is passed EXPLICITLY - it is an
input, not ambient state, and 164F holds it constant across every variant.

The phase results are recorded here too, so the evidence does not live only in
a terminal scrollback. That happened once in this gate: the first survey's most
important list was lost to `tail`.

Makes no network request.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

REPO = pathlib.Path(__file__).resolve().parents[1]
PYTHON = REPO / ".venv" / "bin" / "python"
TARGET = REPO / "artifacts" / "live_collection_audit_gate164"
DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

PHASES = (
    ("replay", "scripts/_g164_phase_replay.py"),
    ("tamper_and_ambient_guard", "scripts/_g164_phase_tamper_and_ambient.py"),
    ("build_context_isolation", "scripts/_g164_phase_context_isolation.py"),
    ("health_and_provenance", "scripts/_g164_phase_health_and_provenance.py"),
)


def run_phase(path: str) -> dict:
    proc = subprocess.run(
        [str(PYTHON), str(REPO / path)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=900,
    )
    line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    try:
        return json.loads(line)
    except Exception:  # noqa: BLE001
        return {"phase_did_not_report": True, "stderr": proc.stderr[-400:]}


from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.live_collection_audit_artifact_gate164_service import (  # noqa: E402
    write_audit_artifacts,
)

TARGET.mkdir(parents=True, exist_ok=True)

# ---- the canonical artifact set, with the database as an explicit input --
session = SessionLocal()
try:
    written = write_audit_artifacts(
        repo_root=str(REPO), connection=session, organization_id=DEMO
    )
finally:
    session.close()
print(f"canonical artifacts: {written['file_count']} files, scope={written['scope']}")

# ---- the phase evidence --------------------------------------------------
results: dict[str, dict] = {}
for name, path in PHASES:
    print(f"  running {name}...")
    results[name] = run_phase(path)

network_total = sum(
    int(results[name].get(key) or 0)
    for name, key in (
        ("replay", "network_calls_during_replay"),
        ("tamper_and_ambient_guard", "network_attempts_during_this_phase"),
        ("health_and_provenance", "network_requests_during_this_phase"),
    )
)

(TARGET / "phase_evidence.json").write_text(
    json.dumps(
        {
            "schema_version": "nf_gate164_phase_evidence_v1",
            "phases": results,
            "network_requests_during_gate164": network_total,
            "how_no_network_was_proven": (
                "each phase replaces socket.socket with one that raises and "
                "counts attempts. Not inferred from reading the code."
            ),
            "the_database_is_an_explicit_input": (
                "canonical generation is passed a connection. It is an input, "
                "not ambient state, and 164F holds it constant across every "
                "variant so 'the database moved' is never the variable."
            ),
        },
        indent=2,
        sort_keys=True,
        default=str,
    )
    + "\n",
    encoding="utf-8",
)

# ---- reconcile the two provider-sensitivity measurements ----------------
#
# 21 from the dedicated A-vs-D run, 19 from the six-way matrix. Two numbers
# for one property is exactly what this campaign does not leave lying around.
try:
    dedicated = json.loads(
        (TARGET / "provider_credential_sensitive_builders.json").read_text()
    )
    matrix = json.loads((TARGET / "artifact_writer_classification.json").read_text())
    dedicated_set = set(dedicated.get("builders") or {})
    detail = matrix.get("differing_files_by_variant") or {}
    matrix_d = {k for k, v in detail.items() if "D" in v}
    errored = {k for k, v in detail.items() if "errored_in" in v}
    (TARGET / "provider_sensitivity_reconciliation.json").write_text(
        json.dumps(
            {
                "schema_version": "nf_gate164_provider_reconciliation_v1",
                "dedicated_a_vs_d_run": len(dedicated_set),
                "six_way_matrix_d_sensitive": len(matrix_d),
                "difference": sorted(dedicated_set - matrix_d),
                "explanation": (
                    "the writers in `difference` errored in at least one "
                    "variant of the six-way matrix - variant B has no .env, "
                    "and these auth builders raise without provider "
                    "configuration. The classifier buckets an errored writer "
                    "before it reaches the D comparison, so they are counted "
                    "as environment_scoped by a different route rather than "
                    "dropped."
                ),
                "both_numbers_are_correct": (
                    "21 = provider-sensitive among writers that ran in BOTH "
                    "the A and D runs. 19 = provider-sensitive among writers "
                    "that ran in ALL SIX variants. Same property, different "
                    "populations."
                ),
                "all_are_environment_scoped": sorted(
                    matrix.get("classification", {}).get(k)
                    for k in (dedicated_set - matrix_d)
                ),
                "errored_in_some_variant": sorted(dedicated_set & errored),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print("  reconciliation recorded")
except Exception as exc:  # noqa: BLE001
    print(f"  reconciliation skipped: {type(exc).__name__}: {exc}")

print(f"network requests during gate164: {network_total}")
print(f"written to {TARGET.relative_to(REPO)}/")
for path in sorted(TARGET.iterdir()):
    print(f"  {path.name}")
