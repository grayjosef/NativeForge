#!/usr/bin/env python3
"""Operator-only Sprint 62 runtime active source creation + evidence JSON.

Uses explicit operator flags. Requires DATABASE_URL and schema at Alembic 0019.
Does not run Alembic upgrades.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.active_source_runtime_creation_execution_service import (  # noqa: E402
    execute_runtime_active_source_creation_and_build_evidence,
)


def _build_operator_confirmation(ns: argparse.Namespace) -> dict:
    return {
        "operator_confirmed_runtime_db_execution": (
            ns.operator_confirmed_runtime_db_execution
        ),
        "operator_confirmed_single_row_creation": (
            ns.operator_confirmed_single_row_creation
        ),
        "operator_confirmed_no_activation": ns.operator_confirmed_no_activation,
        "operator_confirmed_no_scrape_ingest_api_llm_ledger": (
            ns.operator_confirmed_no_scrape_ingest_api_llm_ledger
        ),
        "operator_confirmed_target_table": ns.operator_confirmed_target_table,
        "operator_confirmed_target_revision_id": (
            ns.operator_confirmed_target_revision_id
        ),
        "operator_confirmed_rollback_contract": ns.operator_confirmed_rollback_contract,
        "operator_confirmed_runtime_evidence_capture": (
            ns.operator_confirmed_runtime_evidence_capture
        ),
        "runtime_organization_id": str(ns.runtime_organization_id),
    }


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Sprint 62 governed runtime nf_active_opportunity_sources row creation."
        ),
    )
    p.add_argument(
        "--runtime-organization-id",
        type=UUID,
        required=True,
        help="Organization UUID that exists in the runtime database (FK target).",
    )
    for flag in (
        "operator_confirmed_runtime_db_execution",
        "operator_confirmed_single_row_creation",
        "operator_confirmed_no_activation",
        "operator_confirmed_no_scrape_ingest_api_llm_ledger",
        "operator_confirmed_rollback_contract",
        "operator_confirmed_runtime_evidence_capture",
    ):
        p.add_argument(
            f"--{flag.replace('_', '-')}",
            dest=flag,
            action="store_true",
            help=f"Required explicit confirmation: {flag} must be passed.",
        )
    p.add_argument(
        "--operator-confirmed-target-table",
        required=True,
        choices=["nf_active_opportunity_sources"],
    )
    p.add_argument(
        "--operator-confirmed-target-revision-id",
        required=True,
        choices=["0019"],
    )
    ns = p.parse_args()
    required_bools = (
        "operator_confirmed_runtime_db_execution",
        "operator_confirmed_single_row_creation",
        "operator_confirmed_no_activation",
        "operator_confirmed_no_scrape_ingest_api_llm_ledger",
        "operator_confirmed_rollback_contract",
        "operator_confirmed_runtime_evidence_capture",
    )
    missing = [f for f in required_bools if not getattr(ns, f)]
    if missing:
        msg = (
            "BLOCKED: pass all required --operator-confirmed-* "
            "flags as true switches."
        )
        print(msg, file=sys.stderr)
        print(f"Missing: {', '.join(missing)}", file=sys.stderr)
        return 2

    op = _build_operator_confirmation(ns)
    out_dir = ROOT / "docs" / "product" / "runtime-evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"sprint62_runtime_active_source_creation_{ts}.json"

    with SessionLocal() as session:
        packet = execute_runtime_active_source_creation_and_build_evidence(
            db_session=session,
            operator_confirmation=op,
        )
    out_path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")

    pre = packet.get("runtime_preflight_evidence", {})
    post = packet.get("runtime_post_execution_evidence", {})
    print("")
    print("======== COPY THIS SUMMARY (Sprint 62 runtime creation) ========")
    print(f"readiness_decision: {packet.get('readiness_decision')}")
    print(f"runtime_execution_status: {packet.get('runtime_execution_status')}")
    rid = packet.get("runtime_created_source_row_id")
    print(f"runtime_created_source_row_id: {rid}")
    print(f"count_before (preflight): {pre.get('runtime_active_source_count_before')}")
    print(f"count_after (post): {post.get('runtime_active_source_count_after')}")
    print(f"count_delta: {post.get('runtime_active_source_count_delta')}")
    na = packet.get("runtime_no_activation_evidence")
    print(f"runtime_no_activation_evidence: {na}")
    print(
        "runtime_no_scrape_ingest_api_llm_ledger_evidence: "
        f"{packet.get('runtime_no_scrape_ingest_api_llm_ledger_evidence')}"
    )
    rb = packet.get("runtime_rollback_contract_evidence")
    print(f"runtime_rollback_contract_evidence: {rb}")
    print(f"evidence_json_written_to: {out_path}")
    print("======== END COPY THIS SUMMARY ========")
    print("")
    ok_rd = "executed_runtime_single_source_row_created"
    return 0 if packet.get("readiness_decision") == ok_rd else 1


if __name__ == "__main__":
    raise SystemExit(main())
