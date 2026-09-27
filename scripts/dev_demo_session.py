"""Start a local API with a signed-in demo session, for browser QA.

Every organization-scoped route now requires a real session cookie: the dev
organization header was removed, and `customer_org_context_dependency` reads
the organization out of a membership row or refuses. That is the right
production behaviour, and it makes the product impossible to look at locally
without completing an OAuth round trip - which needs a password nobody should
be typing into an automated QA pass.

So this sets up exactly what a completed sign-in leaves behind: an identity
row, an active membership in the protected demo organization, and a session
cookie signed with the suite's local development key.

It is a **local development tool** and not a bypass:

- it binds to 127.0.0.1 only,
- it mints a session for one hard-coded demo organization and takes no
  argument naming another,
- the cookie it produces is verified by the same verifier production uses -
  signature, expiry, organization and membership all still checked,
- the key it signs with is the committed `local_dev_fixture`, which
  `build_signing_key_readiness` refuses for a production session, so a cookie
  from here cannot be accepted by a correctly configured deployment,
- and it changes no application code. Nothing in `src/` calls it.

    .venv/bin/python scripts/dev_demo_session.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

#: The organization Mayhem protected for demonstration. Hard-coded rather than
#: read from argv: a script that mints a session for any organization you name
#: is a script somebody eventually points at a real one.
DEMO_ORG = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"

PORT = int(os.environ.get("PORT", "8000"))


def main() -> int:
    os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./nativeforge.local.db")

    import session_org_helper as helper

    org_type = helper.ensure_org(DEMO_ORG, "demo")
    if org_type != "demo":
        print(f"refusing: organizations row for {DEMO_ORG} is {org_type!r}, not demo")
        return 2

    cookie = helper.session_cookie_value(DEMO_ORG)

    # Written to a gitignored file rather than to stdout. A session value in
    # a log is a session anybody who reads the log can replay, and QA logs get
    # pasted into places.
    run_dir = ROOT / ".run"
    run_dir.mkdir(exist_ok=True)
    cookie_file = run_dir / "dev_session_cookie"
    cookie_file.write_text(cookie, encoding="utf-8")
    cookie_file.chmod(0o600)

    print(f"organization : {DEMO_ORG}", flush=True)
    print("cookie name  : nf_session", flush=True)
    print(f"cookie file  : {cookie_file}", flush=True)
    print(f"serving      : http://127.0.0.1:{PORT}", flush=True)

    proc = subprocess.Popen(
        [
            str(ROOT / ".venv/bin/python"),
            "-m",
            "uvicorn",
            "nativeforge.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ],
        cwd=ROOT,
        env=os.environ.copy(),
    )
    try:
        while proc.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        proc.terminate()
    return proc.returncode or 0


if __name__ == "__main__":
    raise SystemExit(main())
