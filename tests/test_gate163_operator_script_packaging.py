"""The Gate 163 operator scripts have to be in the runtime image.

`.dockerignore` excludes `scripts/`. The Dockerfile used to copy only the
tenant-isolation checker, so the Railway console could not see the Grants.gov
authorization tools. This pins the exception to those two files.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

OPERATOR_SCRIPTS = (
    "scripts/record_gate163_grants_gov_decisions.py",
    "scripts/record_gate163_live_fetch_opt_in.py",
    "scripts/run_gate163_robots_preflight.py",
    "scripts/run_gate163_grants_gov_bounded_corpus_collection.py",
)

DECISIONS = [
    sys.executable,
    "scripts/record_gate163_grants_gov_decisions.py",
    "--operator-handle",
    "MAYHEM",
    "--source-id",
    "nf-seed-2026-api-grants-gov-search2",
    "--human-activation-acknowledged",
    "--public-only-acknowledged",
    "--single-source-only-acknowledged",
]


def test_the_operator_scripts_exist_and_are_reincluded_after_scripts_is_excluded() -> (
    None
):
    ignore = (REPO / ".dockerignore").read_text(encoding="utf-8")
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    excluded_at = ignore.index("\nscripts\n")
    for relative in OPERATOR_SCRIPTS:
        assert (REPO / relative).is_file()
        needle = f"!{relative}"
        assert needle in ignore
        assert ignore.index(needle) > excluded_at
        assert f"COPY {relative} ./{relative}" in dockerfile
    assert (
        "COPY fixtures/source_ingestion/NF_SOURCE_SEED_2026.csv "
        "./fixtures/source_ingestion/NF_SOURCE_SEED_2026.csv"
    ) in dockerfile


def test_the_decisions_dry_run_prints_the_packet_and_does_not_apply() -> None:
    completed = subprocess.run(
        DECISIONS,
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    packet = completed.stdout
    assert '"apply": false' in packet
    assert '"would_write": true' in packet
    assert "nf-seed-2026-api-grants-gov-search2" in packet
    assert "https://api.grants.gov/v1/api/search2" in packet
    assert "DRY RUN" in packet
    assert "REFUSED" not in packet
