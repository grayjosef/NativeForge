"""Which artifact builders change when provider credentials are present?

The Gate 163 defect, measured. Two passes only - baseline, and baseline plus
exported OIDC/signing values - with `DATABASE_URL` pinned absolute in both so
the database is never the variable.

The credential values are deliberately fake. PRESENCE is what is being varied;
no real secret is read, and none is written anywhere.

Writes the result to `artifacts/live_collection_audit_gate164/` so it is not
lost to a terminal scrollback, which is how the first run of this survey lost
its most important list.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
SURVEY = REPO / "scripts" / "_g164_survey_ambient_artifacts.py"
PYTHON = REPO / ".venv" / "bin" / "python"
DB_ABS = f"sqlite+pysqlite:///{REPO}/nativeforge.local.db"

FAKE_PROVIDER = {
    "OIDC_ISSUER": "https://gate164.invalid/",
    "OIDC_CLIENT_ID": "nf-gate164-not-a-real-client",
    "OIDC_AUDIENCE": "https://gate164.invalid/api",
    "OIDC_CLIENT_SECRET": "nf-gate164-not-a-real-secret",
    "NF_SESSION_SIGNING_KEY": "nf-gate164-not-a-real-signing-key",
}


def run(label: str, extra_env: dict) -> dict:
    out_root = pathlib.Path(tempfile.mkdtemp(prefix=f"g164-{label}-"))
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(REPO / "src")
    environment["DATABASE_URL"] = DB_ABS
    environment.update(extra_env)
    proc = subprocess.run(
        [str(PYTHON), str(SURVEY), "--out-root", str(out_root)],
        cwd=str(REPO),
        env=environment,
        capture_output=True,
        text=True,
        timeout=1200,
    )
    shutil.rmtree(out_root, ignore_errors=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        print(f"  {label}: rc={proc.returncode} {proc.stderr[-300:]}")
        return {}
    return json.loads(proc.stdout.strip().splitlines()[-1])


print("baseline...")
baseline = run("base", {})
print("with provider credentials present...")
credentialed = run("cred", FAKE_PROVIDER)

sensitive: dict[str, list[str]] = {}
for key in sorted(set(baseline) | set(credentialed)):
    left = (baseline.get(key) or {}).get("files") or {}
    right = (credentialed.get(key) or {}).get("files") or {}
    names = sorted(n for n in set(left) | set(right) if left.get(n) != right.get(n))
    if names:
        sensitive[key] = names

print()
print(f"=== PROVIDER-CREDENTIAL SENSITIVE ({len(sensitive)})")
for key, names in sensitive.items():
    print(f"  {key}")
    for name in names:
        print(f"      {name}")

target = REPO / "artifacts" / "live_collection_audit_gate164"
target.mkdir(parents=True, exist_ok=True)
(target / "provider_credential_sensitive_builders.json").write_text(
    json.dumps(
        {
            "schema_version": "nf_gate164_ambient_survey_v1",
            "what_was_varied": (
                "presence of OIDC_ISSUER, OIDC_CLIENT_ID, OIDC_AUDIENCE, "
                "OIDC_CLIENT_SECRET and NF_SESSION_SIGNING_KEY. Values were "
                "fake; presence is the variable and no real secret was read."
            ),
            "database_held_constant": True,
            "writers_surveyed": len(set(baseline) | set(credentialed)),
            "provider_credential_sensitive": len(sensitive),
            "builders": sensitive,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
print()
print(f"recorded {len(sensitive)} builders to {target.name}/")
