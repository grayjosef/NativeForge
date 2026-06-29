#!/usr/bin/env python3
"""LA-0: report actual active federal tier-1 public source count in DB."""

from __future__ import annotations

import csv
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sqlalchemy import create_engine, text  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402

DEMO_ORG = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
CSV_PATH = ROOT / "fixtures" / "source_ingestion" / "NF_SOURCE_SEED_2026.csv"


def main() -> int:
    settings = get_settings()
    fed_seeds: dict[str, str] = {}
    with CSV_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (
                row["seed_id"].startswith("nf-seed-2026-fed-")
                and row.get("tier") == "1"
                and row.get("adapter_key") == "grants_gov_federal"
                and row.get("access_posture_hint") == "public"
            ):
                fed_seeds[row["seed_id"]] = row["source_url"]

    engine = create_engine(settings.database_url)
    org_uuid = uuid.UUID(DEMO_ORG)
    org_compact = org_uuid.hex
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT source_url, is_active
                FROM nf_opportunity_sources
                WHERE organization_id = :org_id
                   OR organization_id = :org_compact
                """
            ),
            {"org_id": DEMO_ORG, "org_compact": org_compact},
        ).fetchall()

    fed_urls = set(fed_seeds.values())
    active_fed = [r for r in rows if r[1] and r[0] in fed_urls]
    inactive_count = len(fed_seeds) - len(active_fed)

    print("LA0_FEDERAL_ACTIVE_COUNT_REPORT")
    print(f"  database_url: {settings.database_url}")
    print(f"  batch_eligible_federal_seeds: {len(fed_seeds)}")
    print(f"  total_sources_demo_org: {len(rows)}")
    print(f"  active_federal_public_tier1: {len(active_fed)}")
    print(f"  inactive_federal_public_tier1: {inactive_count}")
    print(f"  fed_023_excluded_from_batch: {'nf-seed-2026-fed-023' not in fed_seeds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
