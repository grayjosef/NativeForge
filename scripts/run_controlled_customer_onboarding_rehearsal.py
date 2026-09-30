#!/usr/bin/env python3
"""Run first controlled customer onboarding rehearsal (dry-run or hermetic apply).

Production mutation does NOT occur from this script automatically.
Hermetic apply uses the test/dev database via SessionLocal (same as pytest).

Usage:
  python scripts/run_controlled_customer_onboarding_rehearsal.py --dry-run
  NF_REHEARSAL_APPLY=MAYHEM_APPROVES_CONTROLLED_CUSTOMER_ONBOARDING_REHEARSAL \\
    NF_COMMERCIAL_OPERATOR_APPROVAL=MAYHEM_APPROVES_NATIVEFORGE_COMMERCIAL_PROVISIONING \\
    python scripts/run_controlled_customer_onboarding_rehearsal.py --hermetic --write-evidence
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nativeforge.services.controlled_customer_onboarding_rehearsal_service import (  # noqa: E402
    APPLY_APPROVAL_ENV,
    APPLY_APPROVAL_TOKEN,
    rehearsal_apply_permitted,
    run_hermetic_rehearsal,
    write_evidence_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Controlled customer onboarding rehearsal")
    parser.add_argument("--dry-run", action="store_true", help="Print canonical step plan only")
    parser.add_argument(
        "--hermetic",
        action="store_true",
        help="Run hermetic rehearsal against local SessionLocal database",
    )
    parser.add_argument(
        "--write-evidence",
        action="store_true",
        help="Write JSON evidence under artifacts/controlled_customer_onboarding_rehearsal/",
    )
    args = parser.parse_args()

    if args.dry_run:
        out = run_hermetic_rehearsal(None, dry_run=True)  # type: ignore[arg-type]
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if out.get("passed") else 1

    if not args.hermetic:
        print("Specify --dry-run or --hermetic", file=sys.stderr)
        return 2

    if not rehearsal_apply_permitted():
        print(
            f"Hermetic apply requires {APPLY_APPROVAL_ENV}={APPLY_APPROVAL_TOKEN}",
            file=sys.stderr,
        )
        return 3

    import os

    if os.environ.get("NF_COMMERCIAL_OPERATOR_APPROVAL") != (
        "MAYHEM_APPROVES_NATIVEFORGE_COMMERCIAL_PROVISIONING"
    ):
        print(
            "Set NF_COMMERCIAL_OPERATOR_APPROVAL for operator fulfill step",
            file=sys.stderr,
        )
        return 4

    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        try:
            out = run_hermetic_rehearsal(session.connection(), dry_run=False)
            session.commit()
        except Exception as exc:
            session.rollback()
            print(json.dumps({"passed": False, "error": str(exc)}), file=sys.stderr)
            return 5

    if args.write_evidence:
        write_evidence_json(
            str(ROOT / "artifacts/controlled_customer_onboarding_rehearsal/rehearsal_evidence.json"),
            out,
        )

    print(json.dumps({"passed": out.get("passed"), "steps": len(out.get("steps") or [])}))
    return 0 if out.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
