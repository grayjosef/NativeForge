"""Regenerate ONLY the two committed artifacts the Gate 176-179 block left stale.

The authoritative full suite after Gate 179 finished 2 failed / 13,693 passed.
Both failures were stale bookkeeping, not behaviour:

  tests/test_gate121_...::test_artifacts_regenerate_deterministically
      customer_auth_environment_preflight.json pins the alembic head and still
      said "0061" after migrations 0062-0065 moved it to "0065". This is an
      ELEVENTH head-pin site beyond the ten this campaign already tracks
      (5 services, 4 tests, 1 verifier script). A sweep of
      `grep -rl '"0061"' artifacts/` found this file and nothing else.

  tests/test_gate143_...::test_the_committed_artifacts_match_what_the_service_builds
      no_live_source_call_guard.json records `files_scanned` and said 1250
      while the service built 1276. The block added 52 code files but exactly
      26 under src/services/, and 1250 + 26 = 1276. The guard scans src/ only.

Neither artifact is evidence-derived. Both are a pure function of the source
tree, so rebuilding them destroys nothing.

## Why this is a new script and not a rerun of the Gate 176 one

`_g176_regenerate_head_pinned_artifacts.py` names five targets and none of
them is either of these. Its docstring carries the reason to keep scripts
narrow: running every artifact writer once wiped the Gate 164 audit chain,
because EVIDENCE-DERIVED artifacts record something that HAPPENED and
rebuilding them against an empty database destroys the only copy. So this
script names its two targets and touches nothing else.

## The environment has TWO halves, and both are load-bearing

Reproduced verbatim from the Gate 176 script, which earned them the hard way:

  1. DATABASE_URL pointing at a fresh temp SQLite file upgraded to head, so a
     writer that seeds demo rows touches scratch and never the live
     nativeforge.local.db.
  2. the auth environment removed: the nine OIDC/session keys popped from
     os.environ AND Settings.model_config["env_file"] = None, because blanking
     the variables alone is not enough - the overlay falls through to Settings,
     and Settings reads .env.

Miss half 2 and the bytes disagree with the suite's. Miss half 1 and they
depend on whatever is in the developer's database.

Neither writer is wrapped in canonical_build(): that boundary refuses
auth_environment_overlay outright, and the suite does not wrap them either.
The rule is to match what the suite does, because these bytes must agree with
the suite's and nothing else.

Makes no network request.
"""

from __future__ import annotations

import difflib
import os
import pathlib
import shutil
import socket
import sys
import tempfile

sys.path.insert(0, "src")
sys.path.insert(0, ".")

# ---- half 1: a scratch database, upgraded to head ----------------------
_SCRATCH = pathlib.Path(tempfile.mkdtemp(prefix="nf_g180_regen_"))
os.environ["DATABASE_URL"] = (
    f"sqlite+pysqlite:///{(_SCRATCH / 'nf.sqlite3').as_posix()}"
)

# ---- half 2: no ambient auth environment, .env included ----------------
for _auth_key in (
    "OIDC_ISSUER",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_AUDIENCE",
    "OIDC_CALLBACK_URL",
    "NF_PUBLIC_ORIGIN",
    "NF_SESSION_SIGNING_KEY",
    "NF_OIDC_DISCOVERY_ENABLED",
    "NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL",
):
    os.environ.pop(_auth_key, None)

from nativeforge.lib.settings import Settings as _Settings  # noqa: E402

_Settings.model_config["env_file"] = None

_NETWORK = {"attempts": 0}


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate180 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]

get_settings.cache_clear()
_URL = str(get_settings().database_url)
if "nativeforge.local.db" in _URL or "nf_g180_regen_" not in _URL:
    raise SystemExit(f"refusing to regenerate against {_URL}")
command.upgrade(Config(str(REPO / "alembic.ini")), "head")

from nativeforge.services import (  # noqa: E402
    customer_auth_activation_preflight_artifact_service as auth_preflight,
)
from nativeforge.services import (  # noqa: E402
    source_monitoring_artifact_gate143_service as source_monitoring,
)

changed_lines = 0
rewritten = 0


def _report(before: str, body: str, name: str) -> None:
    """Print the unified diff and count the lines that moved."""
    global changed_lines
    diff = difflib.unified_diff(
        before.splitlines(),
        body.splitlines(),
        fromfile=f"committed/{name}",
        tofile=f"rebuilt/{name}",
        lineterm="",
        n=0,
    )
    for line in diff:
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith(("+", "-")):
            changed_lines += 1
            print(f"    {line}")


print(f"scratch_database={_URL}")
print()

# ---- target 1: writes a tree, like the Gate 176 TARGETS -----------------
_directory = pathlib.Path(auth_preflight.ARTIFACT_DIR)
print(f"=== customer_auth_preflight: {_directory}")
with tempfile.TemporaryDirectory() as _tmp:
    auth_preflight.write_preflight_artifacts(repo_root=_tmp)
    for _fresh_path in sorted((pathlib.Path(_tmp) / _directory).iterdir()):
        _committed = REPO / _directory / _fresh_path.name
        _body = _fresh_path.read_text(encoding="utf-8")
        _before = _committed.read_text(encoding="utf-8") if _committed.is_file() else ""
        if _before == _body:
            continue
        _report(_before, _body, _fresh_path.name)
        shutil.copyfile(_fresh_path, _committed)
        rewritten += 1
        print(f"    -> rewrote {_fresh_path.name}")

# ---- target 2: returns {name: body}, like the Gate 176 DICT_TARGETS -----
_directory = REPO / source_monitoring.ARTIFACT_DIR
print(f"=== source_monitoring: {source_monitoring.ARTIFACT_DIR}")
_built = source_monitoring.build_source_monitoring_artifacts()
for _name, _body in sorted(_built.items()):
    _committed = _directory / _name
    _before = _committed.read_text(encoding="utf-8") if _committed.is_file() else ""
    if _before == _body:
        continue
    _report(_before, _body, _name)
    _committed.write_text(_body, encoding="utf-8")
    rewritten += 1
    print(f"    -> rewrote {_name}")

print()
print(f"artifacts_rewritten={rewritten}")
print(f"changed_lines={changed_lines}")
print(f"network_attempts={_NETWORK['attempts']}")
