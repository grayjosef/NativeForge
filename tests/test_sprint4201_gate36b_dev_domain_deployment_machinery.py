"""Sprint 4201 / Gate 36B: stamp, fail-closed serve, verifier contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from nativeforge.services.gate36b_dev_domain_deployment_machinery_service import (
    DistNotReady,
    claim_boundary_preserved,
    count_build_sha_metas,
    docs_claim_boundary_ok,
    parse_verifier_output,
    require_stamped_dist,
    stamp_html_document,
    validate_html_stamp,
)

ROOT = Path(__file__).resolve().parents[1]

BARE_HTML = "<!DOCTYPE html><html><head></head><body></body></html>"


def test_stamp_validator_rejects_missing_stamp() -> None:
    with pytest.raises(DistNotReady, match="missing"):
        validate_html_stamp(BARE_HTML)
    assert count_build_sha_metas(BARE_HTML) == 0


def test_stamp_validator_rejects_duplicate_stamp() -> None:
    dup = (
        "<head>"
        '<meta name="nativeforge-build-sha" content="aaa">'
        '<meta name="nativeforge-build-sha" content="bbb">'
        "</head>"
    )
    with pytest.raises(DistNotReady, match="duplicate"):
        validate_html_stamp(dup)
    assert count_build_sha_metas(dup) == 2


def test_stamp_html_inserts_exactly_one_sha() -> None:
    out = stamp_html_document(
        BARE_HTML,
        git_sha="abc123",
        build_time="2026-08-22T00:00:00Z",
        source_dirty=False,
    )
    validate_html_stamp(out)
    assert count_build_sha_metas(out) == 1
    assert 'name="nativeforge-artifact-kind" content="dev-domain-demo"' in out


def test_fail_closed_rejects_missing_dist(tmp_path: Path) -> None:
    missing = tmp_path / "no-dist"
    with pytest.raises(DistNotReady, match="dist missing"):
        require_stamped_dist(missing)


def test_fail_closed_rejects_unstamped_dist(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(BARE_HTML, encoding="utf-8")
    (dist / "health").write_text("ok\n", encoding="utf-8")
    (dist / "version").write_text("{}\n", encoding="utf-8")
    (dist / "build-manifest.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(DistNotReady, match="missing nativeforge-build-sha"):
        require_stamped_dist(dist)


def test_verifier_parser_pass_fail() -> None:
    assert parse_verifier_output("check=x status=PASS\nRESULT=PASS\n") == "PASS"
    assert parse_verifier_output("RESULT=FAIL\n") == "FAIL"
    with pytest.raises(ValueError):
        parse_verifier_output("no result line")


def test_claim_boundary_html_rejects_forbidden_go() -> None:
    assert claim_boundary_preserved("<html>limited external demo</html>") is True
    assert (
        claim_boundary_preserved("<html>controlled customer pilot GO</html>") is False
    )


def test_docs_claim_boundary_does_not_allow_forbidden_gos() -> None:
    paths = [
        ROOT / "docs/operations/337_GATE36B_DEV_DOMAIN_DEPLOYMENT_MACHINERY.md",
        ROOT / "docs/operations/338_GATE36B_CLOUDFLARE_OPERATOR_STEPS.md",
        ROOT / "docs/operations/339_GATE36B_MONDAY_DEMO_RUNBOOK.md",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert docs_claim_boundary_ok(text)
        assert "Do not claim controlled customer pilot GO" in text
        assert "Do not claim production-ready" in text
        lowered = text.lower()
        assert "limited external demo" in lowered or "loopback" in lowered
        allowed = text
        if "## Allowed claims" in text:
            allowed = text.split("## Allowed claims", 1)[1]
            if "## Forbidden" in allowed:
                allowed = allowed.split("## Forbidden", 1)[0]
            assert "controlled customer pilot GO" not in allowed
            assert "production rollout GO" not in allowed
