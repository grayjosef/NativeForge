"""Gate 163Y: post-commit verification must reapply demo RLS on PostgreSQL."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OPT_IN = REPO / "scripts" / "record_gate163_live_fetch_opt_in.py"


def test_live_fetch_opt_in_reapplies_rls_after_commit_before_read_back() -> None:
    source = OPT_IN.read_text(encoding="utf-8")
    assert "reapply_org_rls_after_commit" in source
    commit_at = source.index("session.commit()")
    reapply_at = source.index("reapply_org_rls_after_commit", commit_at)
    opted_at = source.index("is_live_fetch_opted_in", reapply_at)
    recorded_at = source.index('print("RECORDED.', opted_at)
    assert reapply_at < opted_at < recorded_at


def test_recorded_only_prints_after_post_write_verification_passes() -> None:
    source = OPT_IN.read_text(encoding="utf-8")
    assert "POST-WRITE VERIFICATION FAILED" in source
    assert re.search(
        r"if verification_failures:[\s\S]*return 1[\s\S]*print\(\"RECORDED\.",
        source,
    )


def test_apply_path_checks_recorded_before_commit() -> None:
    source = OPT_IN.read_text(encoding="utf-8")
    assert "not written.get(\"recorded\")" in source or "not written.get('recorded')" in source
