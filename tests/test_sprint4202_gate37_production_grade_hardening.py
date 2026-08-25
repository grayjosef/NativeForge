"""Sprint 4202 / Gate 37: fail-closed drills and claim boundary."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from pathlib import Path

import pytest

from nativeforge.services.gate36b_dev_domain_deployment_machinery_service import (
    DistNotReady,
    parse_verifier_output,
    require_stamped_dist,
    stamp_html_document,
)
from nativeforge.services.gate37_production_grade_hardening_service import (
    ALLOWED_DEMO_LANGUAGE,
    require_claim_boundary_source,
    require_loopback_serve_contract,
    require_preview_port_free,
    unnegated_forbidden_hits,
)

ROOT = Path(__file__).resolve().parents[1]
BARE_HTML = "<!DOCTYPE html><html><head></head><body></body></html>"
STAMPED = stamp_html_document(
    BARE_HTML,
    git_sha="abc",
    build_time="2026-08-22T00:00:00Z",
)


def _dist_with(
    tmp_path: Path,
    *,
    html: str,
    manifest: bool = True,
) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(html, encoding="utf-8")
    (dist / "health").write_text("ok\n", encoding="utf-8")
    (dist / "version").write_text("{}\n", encoding="utf-8")
    if manifest:
        (dist / "build-manifest.json").write_text("{}\n", encoding="utf-8")
    return dist


def test_unstamped_dist_blocks_serve(tmp_path: Path) -> None:
    dist = _dist_with(tmp_path, html=BARE_HTML)
    with pytest.raises(DistNotReady, match="missing nativeforge-build-sha"):
        require_stamped_dist(dist)


def test_missing_manifest_blocks_serve(tmp_path: Path) -> None:
    dist = _dist_with(tmp_path, html=STAMPED, manifest=False)
    with pytest.raises(DistNotReady, match="build-manifest.json missing"):
        require_stamped_dist(dist)


def test_duplicate_stamp_blocks_serve(tmp_path: Path) -> None:
    dup = STAMPED.replace(
        "nativeforge-build-sha",
        "nativeforge-build-sha",
        1,
    )
    extra = '<meta name="nativeforge-build-sha" content="zzz">' + dup
    dist = _dist_with(tmp_path, html=extra)
    with pytest.raises(DistNotReady, match="duplicate"):
        require_stamped_dist(dist)


def _free_port() -> int:
    """An ephemeral loopback port, released before it is returned."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_busy_preview_port_blocks_serve() -> None:
    """A listener on the preview port must block serving.

    Was `test_5175_collision_blocks_serve`, which bound port 5175 directly. The
    demo preview service owns 127.0.0.1:5175 by design, so that bind failed with
    `Address already in use` on any machine where the preview is running - and
    stopping the service to satisfy a test is not acceptable.

    The behaviour under test is the collision check, not the specific number, so
    it now runs against an ephemeral port. `require_preview_port_free` already
    takes host and port, so no product change was needed.
    """
    port = _free_port()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(1)
    try:
        with pytest.raises(DistNotReady, match="already in use"):
            require_preview_port_free(port=port)
    finally:
        srv.close()
    # Free again once the listener is gone.
    require_preview_port_free(port=port)


def test_preview_port_default_is_5175() -> None:
    """The default the product actually serves on is still pinned."""
    from nativeforge.services.gate37_production_grade_hardening_service import (
        PREVIEW_HOST,
        PREVIEW_PORT,
    )

    assert PREVIEW_PORT == 5175
    assert PREVIEW_HOST == "127.0.0.1"


def test_loopback_only_contract() -> None:
    text = (ROOT / "scripts/serve_frontend_preview_5175.sh").read_text(encoding="utf-8")
    require_loopback_serve_contract(text)


def test_verifier_fail_when_server_down() -> None:
    """The verifier must fail against a base URL where nothing is listening.

    Was calling `require_preview_port_free()` first, which asserted 5175 was
    free. The demo preview owns that port by design, so the test could only pass
    on a machine with the service stopped.

    The property under test is "verifier fails when the server it checks is
    down", which is expressible without touching 5175: point it at an ephemeral
    port nobody is serving. The verifier takes the base URL as a positional
    argument.
    """
    port = _free_port()
    proc = subprocess.run(
        [
            str(ROOT / "scripts/verify_nativeforge_demo_deployment.sh"),
            f"http://127.0.0.1:{port}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert parse_verifier_output(proc.stdout) == "FAIL"
    # It failed for the right reason: the loopback checks, not something else.
    assert "loopback_home_200 status=FAIL" in proc.stdout


def test_verifier_pass_when_stamped_server_up() -> None:
    dist = ROOT / "frontend" / "dist"
    try:
        require_stamped_dist(dist)
    except DistNotReady:
        pytest.skip("stamped frontend/dist not present")
    # A stamped preview may already be serving 5175 - the demo preview service
    # owns that port by design, and stopping it to run a test is not acceptable.
    # When it is up, verify against it; only start one when the port is free.
    try:
        require_preview_port_free()
    except DistNotReady:
        proc = subprocess.run(
            [str(ROOT / "scripts/verify_nativeforge_demo_deployment.sh")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert parse_verifier_output(proc.stdout) == "PASS", proc.stdout[-2000:]
        assert proc.returncode == 0
        return

    serve = subprocess.Popen(
        [str(ROOT / "scripts/serve_frontend_preview_5175.sh")],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        ready = False
        for _ in range(40):
            time.sleep(0.25)
            try:
                require_preview_port_free()
            except DistNotReady:
                ready = True
                break
        if not ready:
            pytest.fail("preview did not bind 5175")
        proc = subprocess.run(
            [str(ROOT / "scripts/verify_nativeforge_demo_deployment.sh")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert parse_verifier_output(proc.stdout) == "PASS"
        assert proc.returncode == 0
    finally:
        try:
            os.killpg(serve.pid, signal.SIGTERM)
        except ProcessLookupError:
            serve.terminate()
        try:
            serve.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(serve.pid, signal.SIGKILL)


def test_claim_boundary_enforcement_on_demo_page() -> None:
    page = (ROOT / "frontend/src/pages/ScCustomerDemoPage.tsx").read_text(
        encoding="utf-8"
    )
    require_claim_boundary_source(page)
    assert not unnegated_forbidden_hits(page)
    for marker in ALLOWED_DEMO_LANGUAGE:
        assert marker in page


def test_gate37_docs_claim_boundary() -> None:
    paths = [
        ROOT / "docs/operations/340_GATE37_OPERATIONAL_RISK_REGISTER.md",
        ROOT / "docs/operations/341_GATE37_ROLLBACK_RECOVERY_DRILL.md",
        ROOT / "docs/operations/342_GATE37_CUSTOMER_PILOT_READINESS_PACKET_V2.md",
        ROOT / "docs/operations/343_GATE37_RESTART_VERIFIER_DRILL.md",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "Do not claim production-ready" in text
        assert "Do not claim controlled customer pilot GO" in text
        assert not unnegated_forbidden_hits(text)
        if path.name.startswith("342"):
            for marker in ALLOWED_DEMO_LANGUAGE:
                assert marker in text
