"""Gate 164E/164F: which ambient input does each artifact builder read?

The first version of this survey varied two things at once - cwd AND `.env` -
so the database URL disappeared along with the provider configuration. Every
builder that touches the database then differed because the database was gone,
and 68 of 70 came back "ambient-sensitive" for what may have been one cause.
A measurement that cannot say WHICH input moved is the same defect as a check
with two possible causes.

So: one variable at a time, the database held constant, and a self-diff
control first.

```text
CONTROL   baseline run twice          any difference here is non-determinism,
                                      not ambient sensitivity, and has to be
                                      separated before anything else is read
A         baseline                    repo cwd, .env, DB absolute
B         temp cwd, no .env           config discovery moves; DB still absolute
C         unrelated env vars present  NF_G164_NOISE=...
D         provider credentials        OIDC_* and signing key exported
E         relative repo root          artifacts written via a relative path
F         absolute repo root          the same via an absolute path
```

Every environment pins `DATABASE_URL` to the same absolute sqlite file, so
"the database moved" is never the variable. Environment B keeps that pin, so B
measures `.env`-discovery and cwd only.

Makes no network request.
"""

from __future__ import annotations

import hashlib
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

#: Values are irrelevant; presence is the variable. Deliberately not real.
FAKE_PROVIDER = {
    "OIDC_ISSUER": "https://gate164.invalid/",
    "OIDC_CLIENT_ID": "nf-gate164-not-a-real-client",
    "OIDC_AUDIENCE": "https://gate164.invalid/api",
    "OIDC_CLIENT_SECRET": "nf-gate164-not-a-real-secret",
    "NF_SESSION_SIGNING_KEY": "nf-gate164-not-a-real-signing-key",
}


def run(label: str, *, cwd: pathlib.Path, extra_env: dict, root_style: str) -> dict:
    out_root = pathlib.Path(tempfile.mkdtemp(prefix=f"g164-{label}-"))
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(REPO / "src")
    environment["DATABASE_URL"] = DB_ABS
    environment.update(extra_env)

    target = str(out_root)
    if root_style == "relative":
        # A relative root, resolved from the child's cwd.
        target = os.path.relpath(str(out_root), str(cwd))

    proc = subprocess.run(
        [str(PYTHON), str(SURVEY), "--out-root", target],
        cwd=str(cwd),
        env=environment,
        capture_output=True,
        text=True,
        timeout=1200,
    )
    data: dict = {}
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            data = json.loads(proc.stdout.strip().splitlines()[-1])
        except Exception:  # noqa: BLE001
            data = {}
    else:
        print(f"  {label}: rc={proc.returncode} {proc.stderr[-300:]}")
    shutil.rmtree(out_root, ignore_errors=True)
    return data


def files_of(result: dict, key: str) -> dict:
    entry = result.get(key) or {}
    return entry.get("files") or {}


def differing(left: dict, right: dict, key: str) -> list[str]:
    a, b = files_of(left, key), files_of(right, key)
    return sorted(n for n in set(a) | set(b) if a.get(n) != b.get(n))


clean_cwd = pathlib.Path(tempfile.mkdtemp(prefix="g164-cwd-"))
noise_env = {"NF_G164_NOISE": "present", "SOME_UNRELATED_TOOL_HOME": "/tmp/nothing"}

print("CONTROL: baseline, twice")
control_1 = run("ctl1", cwd=REPO, extra_env={}, root_style="absolute")
control_2 = run("ctl2", cwd=REPO, extra_env={}, root_style="absolute")

print("A: baseline")
a = control_1
print("B: temp cwd, no .env")
b = run("B", cwd=clean_cwd, extra_env={}, root_style="absolute")
print("C: unrelated env vars")
c = run("C", cwd=REPO, extra_env=noise_env, root_style="absolute")
print("D: provider credentials present")
d = run("D", cwd=REPO, extra_env=FAKE_PROVIDER, root_style="absolute")
print("E: relative repo root")
e = run("E", cwd=REPO, extra_env={}, root_style="relative")
print("F: absolute repo root")
f = run("F", cwd=REPO, extra_env={}, root_style="absolute")

shutil.rmtree(clean_cwd, ignore_errors=True)

keys = sorted(set(a) | set(b) | set(c) | set(d) | set(e) | set(f))

buckets: dict[str, list[str]] = {
    "NON_DETERMINISTIC (baseline differs from itself)": [],
    "D: provider credentials change the artifact": [],
    "B: cwd / .env discovery changes the artifact": [],
    "C: unrelated env vars change the artifact": [],
    "E/F: repo root style changes the artifact": [],
    "stable across every variant": [],
}

for key in keys:
    if differing(control_1, control_2, key):
        buckets["NON_DETERMINISTIC (baseline differs from itself)"].append(key)
        continue
    hit = False
    if differing(a, d, key):
        buckets["D: provider credentials change the artifact"].append(key)
        hit = True
    if differing(a, b, key):
        buckets["B: cwd / .env discovery changes the artifact"].append(key)
        hit = True
    if differing(a, c, key):
        buckets["C: unrelated env vars change the artifact"].append(key)
        hit = True
    if differing(e, f, key):
        buckets["E/F: repo root style changes the artifact"].append(key)
        hit = True
    if not hit:
        buckets["stable across every variant"].append(key)

for label, names in buckets.items():
    print()
    print(f"=== {label}  ({len(names)})")
    for name in names[:40]:
        print(f"  {name}")

summary = {label: len(names) for label, names in buckets.items()}
summary["writers"] = len(keys)
print()
print(json.dumps(summary, indent=2, sort_keys=True))

digest = hashlib.sha256(
    json.dumps({k: sorted(v) for k, v in buckets.items()}, sort_keys=True).encode()
).hexdigest()
print(f"bucket digest {digest}")
