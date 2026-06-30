#!/usr/bin/env python3
"""SH-1: apply resolver triage to NF_SOURCE_SEED_2026.csv (health + honest posture)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from nativeforge.services.corrected_catalog_posture_report_service import (  # noqa: E402
    build_corrected_catalog_posture_report,
)
from nativeforge.services.seed_catalog_health_service import (  # noqa: E402
    HEALTH_COLUMNS,
    classify_seed_health_from_posture,
    corrected_access_posture_hint,
)
from nativeforge.services.source_ingestion_seed_schema_service import (  # noqa: E402
    EXPECTED_ROW_COUNT,
    SEED_FILENAME,
    seed_csv_path,
)

BASE_COLUMNS = (
    "seed_id",
    "canonical_source_id",
    "source_name",
    "source_url",
    "tier",
    "adapter_key",
    "access_posture_hint",
)


def _posture_index() -> dict[str, dict]:
    report = build_corrected_catalog_posture_report()
    return {str(c["seed_id"]): c for c in report["candidates"]}


def apply_hygiene(*, write: bool) -> dict:
    path = seed_csv_path()
    posture_by_id = _posture_index()
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if len(rows) != EXPECTED_ROW_COUNT:
        raise ValueError(f"expected {EXPECTED_ROW_COUNT} rows, got {len(rows)}")

    updated_rows: list[dict[str, str]] = []
    posture_corrections = 0
    for row in rows:
        sid = row["seed_id"]
        posture = posture_by_id.get(sid, {})
        health = classify_seed_health_from_posture(
            seed_id=sid,
            access_posture_hint=str(row.get("access_posture_hint") or ""),
            url_status=str(posture.get("url_status") or ""),
            access_posture_blocked=bool(posture.get("access_posture_blocked")),
            url_resolved=posture.get("url_status") != "dead",
        )
        new_hint = corrected_access_posture_hint(
            original_hint=str(row.get("access_posture_hint") or ""),
            catalog_accounting_bucket=health["catalog_accounting_bucket"],
        )
        if new_hint != row.get("access_posture_hint"):
            posture_corrections += 1
        out = {col: row.get(col, "") for col in BASE_COLUMNS}
        out["access_posture_hint"] = new_hint
        for col in HEALTH_COLUMNS:
            out[col] = health.get(col, "")
        updated_rows.append(out)

    fieldnames = list(BASE_COLUMNS) + list(HEALTH_COLUMNS)
    summary = {
        "seed_path": str(path),
        "row_count": len(updated_rows),
        "access_posture_corrections": posture_corrections,
        "write": write,
    }
    if write:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(updated_rows)
        sidecar = path.parent / "NF_SOURCE_SEED_HEALTH_SUMMARY.json"
        from nativeforge.services.seed_catalog_health_service import (  # noqa: E402
            build_catalog_reconciliation_report,
        )
        from nativeforge.services.source_ingestion_seed_loader_service import (  # noqa: E402
            build_source_seed_candidate_bundle,
        )

        bundle = build_source_seed_candidate_bundle()
        recon = build_catalog_reconciliation_report(bundle["candidates"])
        sidecar.write_text(
            json.dumps({"apply_summary": summary, "reconciliation": recon}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        summary["reconciliation"] = recon
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help=f"Rewrite {SEED_FILENAME} with health columns",
    )
    args = parser.parse_args()
    if not __import__("os").environ.get("NF_APP_ENV"):
        print(
            "warning: NF_APP_ENV not set; posture uses live resolver",
            file=sys.stderr,
        )
    result = apply_hygiene(write=args.write)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
