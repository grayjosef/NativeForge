"""Regenerate ONLY the artifacts whose migration head pin moved to 0062.

Migration 0062 moved the alembic head, and committed artifacts pin it. The
Gate 173-175 block hit exactly this and found it via the two-hour suite; this
does it deliberately, names its targets, and shows the diff.

## Why not just run every artifact writer

Earlier in this campaign that was tried, and it wiped the Gate 164 audit
chain: `audit_chain_complete` flipped true->false, six sections were deleted,
and MAYHEM's recorded activation approval went with them. Artifacts fall into
two classes. CODE-DERIVED ones are a pure function of the source and are safe
to rebuild. EVIDENCE-DERIVED ones record something that HAPPENED - an
approval, an observation, a decision - and rebuilding them against an empty
database destroys the only copy. Every target below is code-derived.

## The environment has TWO halves, and both are load-bearing

A previous attempt reproduced only one and produced artifacts that differed
from what the suite builds. `tests/conftest.py` establishes:

  1. `DATABASE_URL` pointing at a fresh temp SQLite file, upgraded to head -
     so a writer that seeds demo rows touches scratch, never the live
     `nativeforge.local.db`.
  2. the auth environment removed: the nine OIDC/session keys popped from
     `os.environ` AND `Settings.model_config["env_file"] = None`, because
     blanking the variables alone is not enough - the overlay falls through
     to Settings, and Settings reads `.env`.

Miss half 2 and `canonical_build()` refuses the read outright (which is how
this script failed the first time, correctly). Miss half 1 and the bytes
depend on whatever is in the developer's database.

Both are reproduced below, before nativeforge is imported.

These three writers are deliberately NOT wrapped in `canonical_build()`. That
boundary refuses `auth_environment_overlay` outright, and these writers reach
it through the activation gate - so wrapping them raises AmbientStateRefused,
which is how the first version of this script failed. The suite does not wrap
them either; it calls each writer directly under the environment above. The
rule is to match what the suite does, not to add a boundary the suite never
applied, because these bytes must agree with the suite's and nothing else.

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
_SCRATCH = pathlib.Path(tempfile.mkdtemp(prefix="nf_g176_regen_"))
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
        raise OSError("gate176 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]

get_settings.cache_clear()
_URL = str(get_settings().database_url)
if "nativeforge.local.db" in _URL or "nf_g176_regen_" not in _URL:
    raise SystemExit(f"refusing to regenerate against {_URL}")
command.upgrade(Config(str(REPO / "alembic.ini")), "head")

from nativeforge.services import (  # noqa: E402
    backup_restore_artifact_gate153_service as backup,
)
from nativeforge.services import (  # noqa: E402
    customer_auth_live_redirect_artifact_service as redirect,
)
from nativeforge.services import (  # noqa: E402
    operational_health_artifact_gate154_service as health,
)
from nativeforge.services import (  # noqa: E402
    tenant_profile_persistence_artifact_service as tenant_profile,
)
from nativeforge.services import (  # noqa: E402
    verified_binding_workflow_artifact_service as binding,
)

#: (label, module, writer). Code-derived only, each pinning the alembic head.
TARGETS = (
    ("verified_binding", binding, binding.write_workflow_artifacts),
    ("tenant_profile", tenant_profile, tenant_profile.write_persistence_artifacts),
    ("live_redirect", redirect, redirect.write_live_redirect_artifacts),
)

changed_lines = 0
rewritten = 0

print(f"scratch_database={_URL}")
print()

for label, module, write in TARGETS:
    directory = pathlib.Path(module.ARTIFACT_DIR)
    print(f"=== {label}: {directory}")
    with tempfile.TemporaryDirectory() as tmp:
        write(repo_root=tmp)
        for fresh_path in sorted((pathlib.Path(tmp) / directory).iterdir()):
            committed = REPO / directory / fresh_path.name
            body = fresh_path.read_text(encoding="utf-8")
            before = (
                committed.read_text(encoding="utf-8") if committed.is_file() else ""
            )
            if before == body:
                continue
            diff = difflib.unified_diff(
                before.splitlines(),
                body.splitlines(),
                fromfile=f"committed/{fresh_path.name}",
                tofile=f"rebuilt/{fresh_path.name}",
                lineterm="",
                n=0,
            )
            for line in diff:
                if line.startswith(("---", "+++", "@@")):
                    continue
                if line.startswith(("+", "-")):
                    changed_lines += 1
                    print(f"    {line}")
            shutil.copyfile(fresh_path, committed)
            rewritten += 1
            print(f"    -> rewrote {fresh_path.name}")

#: Builders that return {name: body} instead of writing a tree. Gate 154's
#: registry also gains the Gate 176 verifier registered this gate, so expect
#: more than a head-pin bump in its diff.
DICT_TARGETS = (
    ("gate153_backup", backup, backup.build_backup_restore_artifacts),
    ("gate154_readiness", health, health.build_operational_health_artifacts),
)

for label, module, build in DICT_TARGETS:
    directory = REPO / module.ARTIFACT_DIR
    print(f"=== {label}: {module.ARTIFACT_DIR}")
    for name, body in sorted(build().items()):
        committed = directory / name
        before = committed.read_text(encoding="utf-8") if committed.is_file() else ""
        if before == body:
            continue
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
        committed.write_text(body, encoding="utf-8")
        rewritten += 1
        print(f"    -> rewrote {name}")

print()
print(f"artifacts_rewritten={rewritten}")
print(f"changed_lines={changed_lines}")
print(f"network_attempts={_NETWORK['attempts']}")
