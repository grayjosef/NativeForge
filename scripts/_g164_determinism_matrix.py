"""Gate 164F + 164F.1: the six-way matrix, and the writer classification.

One run, six environments, every writer. Produces both deliverables from the
same measurement so the classification and the matrix cannot disagree.

```text
A  repo cwd, real local .env
B  temp cwd, no .env
C  unrelated environment variables present
D  fake provider credentials present
E  relative repo_root
F  absolute repo_root
```

`DATABASE_URL` is pinned to the same absolute file in every variant. The first
survey in this gate varied cwd and the database together and produced a number
that could not be attributed; that mistake is not repeated.

## Classification

Every writer lands in exactly one bucket, and `unclassified` must be zero:

```text
ambient_independent      identical across A-F. Depends on the repo and the
                         explicit database, and on nothing else.
environment_scoped       differs across A-F. Describes one deployment, which
                         is legitimate - it just is not repository evidence.
requires_explicit_input  cannot run without caller-supplied data, so it has
                         no ambient behaviour to measure. Reported separately
                         rather than counted as "stable": a writer that fails
                         identically in six environments is not a writer that
                         was proven hermetic.
```

The last bucket exists because of a trap in the first survey: two writers came
back "stable across every variant" when what they actually did was raise the
same TypeError six times.

Writes its evidence to `artifacts/live_collection_audit_gate164/`.
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
TARGET = REPO / "artifacts" / "live_collection_audit_gate164"

FAKE_PROVIDER = {
    "OIDC_ISSUER": "https://gate164.invalid/",
    "OIDC_CLIENT_ID": "nf-gate164-not-a-real-client",
    "OIDC_AUDIENCE": "https://gate164.invalid/api",
    "OIDC_CLIENT_SECRET": "nf-gate164-not-a-real-secret",
    "NF_SESSION_SIGNING_KEY": "nf-gate164-not-a-real-signing-key",
}
NOISE = {"NF_G164_NOISE": "present", "SOME_UNRELATED_TOOL_HOME": "/tmp/nothing"}


def run(label: str, *, cwd: pathlib.Path, extra: dict, relative_root: bool) -> dict:
    out_root = pathlib.Path(tempfile.mkdtemp(prefix=f"g164m-{label}-"))
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO / "src")
    env["DATABASE_URL"] = DB_ABS
    env.update(extra)
    target = (
        os.path.relpath(str(out_root), str(cwd)) if relative_root else str(out_root)
    )
    proc = subprocess.run(
        [str(PYTHON), str(SURVEY), "--out-root", target],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    shutil.rmtree(out_root, ignore_errors=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        print(f"  {label}: rc={proc.returncode} {proc.stderr[-300:]}")
        return {}
    return json.loads(proc.stdout.strip().splitlines()[-1])


clean_cwd = pathlib.Path(tempfile.mkdtemp(prefix="g164m-cwd-"))

# The control, FIRST. A baseline that differs from itself makes every
# comparison below unreadable, and this matrix lost that control once already:
# an earlier run had the tree edited underneath it, the writer count moved
# 70 -> 71 mid-measurement, and a writer that simply did not exist during
# variant A was reported as ambient-sensitive.
print("control: baseline twice...")
control_1 = run("ctl1", cwd=REPO, extra={}, relative_root=False)
control_2 = run("ctl2", cwd=REPO, extra={}, relative_root=False)
non_deterministic = sorted(
    key
    for key in set(control_1) | set(control_2)
    if ((control_1.get(key) or {}).get("files") or {})
    != ((control_2.get(key) or {}).get("files") or {})
)
if non_deterministic:
    print(f"  {len(non_deterministic)} writer(s) differ from themselves:")
    for key in non_deterministic[:10]:
        print(f"    {key}")
    print("  the matrix below cannot attribute differences until this is 0")
else:
    print("  0 writers differ from themselves")

variants: dict[str, dict] = {}
for label, cwd, extra, relative in (
    ("A", REPO, {}, False),
    ("B", clean_cwd, {}, False),
    ("C", REPO, NOISE, False),
    ("D", REPO, FAKE_PROVIDER, False),
    ("E", REPO, {}, True),
    ("F", REPO, {}, False),
):
    print(f"variant {label}...")
    variants[label] = run(label, cwd=cwd, extra=extra, relative_root=relative)
shutil.rmtree(clean_cwd, ignore_errors=True)

keys = sorted({name for result in variants.values() for name in result})

classification: dict[str, str] = {}
differing_detail: dict[str, dict[str, list[str]]] = {}

for key in keys:
    entries = {label: (result.get(key) or {}) for label, result in variants.items()}

    # Non-determinism is its own bucket and outranks everything: a writer that
    # differs from itself cannot be said to differ BECAUSE of an environment.
    if key in non_deterministic:
        classification[key] = "non_deterministic"
        continue

    # A writer that appeared or vanished mid-measurement was not measured.
    # Saying nothing is better than attributing a difference to an environment
    # when the real cause was the tree moving underneath the run.
    if any(not entry for entry in entries.values()):
        classification[key] = "not_measured"
        differing_detail[key] = {
            "absent_in": sorted(label for label, entry in entries.items() if not entry)
        }
        continue

    # A writer that errored in every variant has no ambient behaviour to
    # measure. It is NOT "stable": it failed identically six times.
    if all(entry.get("error") for entry in entries.values()):
        classification[key] = "requires_explicit_input"
        continue
    if any(entry.get("error") for entry in entries.values()):
        classification[key] = "environment_scoped"
        differing_detail[key] = {
            "errored_in": sorted(
                label for label, entry in entries.items() if entry.get("error")
            )
        }
        continue

    baseline = entries["A"].get("files") or {}
    diffs: dict[str, list[str]] = {}
    for label in ("B", "C", "D", "E", "F"):
        other = entries[label].get("files") or {}
        names = sorted(
            n for n in set(baseline) | set(other) if baseline.get(n) != other.get(n)
        )
        if names:
            diffs[label] = names

    if diffs:
        classification[key] = "environment_scoped"
        differing_detail[key] = diffs
    else:
        classification[key] = "ambient_independent"

counts = {
    "total_writers": len(keys),
    "ambient_independent_writers": sum(
        1 for v in classification.values() if v == "ambient_independent"
    ),
    "environment_scoped_writers": sum(
        1 for v in classification.values() if v == "environment_scoped"
    ),
    "requires_explicit_input_writers": sum(
        1 for v in classification.values() if v == "requires_explicit_input"
    ),
    "non_deterministic_writers": sum(
        1 for v in classification.values() if v == "non_deterministic"
    ),
    "not_measured_writers": sum(
        1 for v in classification.values() if v == "not_measured"
    ),
    "unclassified_writers": sum(1 for key in keys if key not in classification),
}

print()
print(json.dumps(counts, indent=2, sort_keys=True))
print()
print("=== ambient independent")
for key in sorted(k for k, v in classification.items() if v == "ambient_independent"):
    print(f"  {key}")
print()
print("=== requires explicit input")
for key in sorted(
    k for k, v in classification.items() if v == "requires_explicit_input"
):
    print(f"  {key}")

TARGET.mkdir(parents=True, exist_ok=True)
(TARGET / "artifact_writer_classification.json").write_text(
    json.dumps(
        {
            "schema_version": "nf_gate164_writer_classification_v1",
            "variants": {
                "A": "repo cwd, real local .env",
                "B": "temp cwd, no .env",
                "C": "unrelated environment variables present",
                "D": "fake provider credentials present (values fake; presence varied)",
                "E": "relative repo_root",
                "F": "absolute repo_root",
            },
            "database_held_constant": True,
            "database_note": (
                "DATABASE_URL pinned to the same absolute file in every "
                "variant, so 'the database moved' is never the variable"
            ),
            "counts": counts,
            "classification": classification,
            "differing_files_by_variant": differing_detail,
            "requires_explicit_input_note": (
                "these writers raise without caller-supplied data. Reported "
                "separately rather than counted as stable: failing identically "
                "in six environments is not a proof of hermeticity."
            ),
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
print()
print(f"recorded to {TARGET.name}/artifact_writer_classification.json")
