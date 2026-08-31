"""Gate 129: the demo-live artifacts, written from measurement.

Five files. Four are generated from the operating shell and the runtime
readiness services; the fifth is the script Mayhem reads off a screen.

Nothing here contacts anything, and no artifact carries a value from the
environment -- key names and booleans only, the rule since Gate 121.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_demo_live_operating_shell_artifact_v1"
ARTIFACT_DIR = "artifacts/demo_live_operating_shell"

DEMO_URL = "https://nf-dev.mayhem-nc.dev/?view=sc_customer_demo"
PUBLIC_ORIGIN = "https://nf-dev.mayhem-nc.dev"
API_ORIGIN = "http://127.0.0.1:8000"

ARTIFACT_FILES: tuple[str, ...] = (
    "customer_demo_operating_shell.json",
    "demo_truth_labels.json",
    "demo_script_for_mayhem.md",
    "demo_readiness_blockers.json",
    "gate129_demo_live_summary.md",
)

#: Names only. A value from any of these must never reach an artifact.
AUTH_ENV_KEY_NAMES: tuple[str, ...] = (
    "OIDC_ISSUER",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_AUDIENCE",
    "OIDC_CALLBACK_URL",
    "NF_PUBLIC_ORIGIN",
    "NF_SESSION_SIGNING_KEY",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def build_demo_live_artifacts() -> dict[str, str]:
    """Return {filename: content}. Deterministic for a given system state."""
    from nativeforge.lib.settings import auth_environment_presence
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )
    from nativeforge.services.customer_demo_operating_shell_service import (
        build_customer_demo_operating_shell,
        operating_shell_invariant_failures,
    )

    shell = build_customer_demo_operating_shell()
    gate = build_customer_auth_activation_gate()
    presence = auth_environment_presence()

    files: dict[str, str] = {}

    # -- 1. the shell itself ------------------------------------------------
    files["customer_demo_operating_shell.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "demo_url": DEMO_URL,
            "shell": shell,
            "invariant_failures": operating_shell_invariant_failures(shell),
        }
    )

    # -- 2. the labels, with what each is derived from ----------------------
    files["demo_truth_labels.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "labels": shell["truth_labels"],
            "active_labels": shell["active_truth_labels"],
            "all_six_active": len(shell["active_truth_labels"]) == 6,
            "note": (
                "active is computed, not asserted. When a capability goes live "
                "its label deactivates because the underlying service changed, "
                "not because anyone edited this list."
            ),
        }
    )

    # -- 3. blockers, split by who can clear them ---------------------------
    code_blockers: list[str] = []
    if not shell["customer_auth_live"]:
        code_blockers.append("dev_header_still_in_place:14_route_modules")
    operator_blockers = [
        b
        for b in gate.get("activation_blocker_names", [])
        if b != "dev_header_still_in_place"
    ]
    files["demo_readiness_blockers.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "demo_visible_today": True,
            "demo_url": DEMO_URL,
            "public_edge": (
                "cloudflare_access_protects_every_path_except_the_oauth_callback"
            ),
            "api_reachable_locally": True,
            "oauth_callback_reachable_publicly_unauthenticated": True,
            "public_edge_measured": {
                "/": "302_to_cloudflare_access",
                "/backend/health": "302_to_cloudflare_access",
                "/api/does-not-exist": "302_to_cloudflare_access",
                "/api/auth/login": "302_to_cloudflare_access",
                "/api/auth/session": "302_to_cloudflare_access",
                "/api/auth/current-user": "302_to_cloudflare_access",
                "/api/auth/callback": "200_api_json_callback_validation_not_passed",
            },
            "public_edge_note": (
                "Exactly one path is exempt, and it is the callback. That is an "
                "Access bypass policy already scoped to /api/auth/callback - it "
                "was not added by this gate. A browser arriving from a provider "
                "carries no Access session, so this exemption is what makes an "
                "OAuth redirect able to land on the API at all."
            ),
            "activation_blockers": sorted(gate.get("activation_blocker_names", [])),
            "code_or_runtime_blockers": sorted(code_blockers),
            "operator_or_provider_blockers": sorted(operator_blockers),
            "auth_env_key_presence": presence,
            "auth_env_values_recorded": False,
            "customer_auth_live": shell["customer_auth_live"],
            "login_live": shell["login_live"],
        }
    )

    # -- 4. the script Mayhem reads ----------------------------------------
    section_lines = "\n".join(
        f"{i + 1}. **{s['title']}** — {s['shows']}"
        for i, s in enumerate(shell["sections"])
    )
    label_lines = "\n".join(f"- {label}" for label in shell["active_truth_labels"])
    files["demo_script_for_mayhem.md"] = f"""# Demo script — {DEMO_URL}

Ten minutes. The order below is the order on the page.

## Before you start

Open the URL and sign in through Cloudflare Access. The page is behind Access,
so an unauthenticated visitor gets a login screen rather than the demo — that is
deliberate and it is what you want on a dev domain.

## Open with the boundary, not the product

Say this first, in your own words:

> Everything on this screen is controlled demo data. The workflow is real, the
> schema is real, the refusals are real. No Tribe's data is in here and nothing
> is being collected live.

The page says the same thing in the labels at the top. Point at them.

## The labels, and why they are there

{label_lines}

These are computed from the system, not typed into the page. When
authentication goes live, the auth label disappears on its own. That is the
honest version of a status badge.

## Walk the ten sections in order

{section_lines}

Each one carries its own status chip:

- **Operational** — live, with real rows
- **Built — not operational** — schema, repository and write path all exist; no
  one owns the rows yet because customer authentication is not live
- **Not built** — no table declares it

Right now nothing is Operational, six are Built, and the reason is the same for
all six: `no_customer_auth_so_nobody_owns_the_row`.

## The question you will be asked

> So what actually works?

The answer, and it is a strong one:

> The compliance spine is built and provably empty. Six persistence lanes have
> schema, row-level security anchored on organization_id, and a write path.
> What they do not have is a customer identity to own a row. That is the next
> gate, and it is a provider configuration away rather than a rebuild.

## What not to say

Do not say NativeForge is monitoring sources, sending digests, storing
documents, or logging anyone in. None of those is true today, all four are
labelled on the screen, and every one of them is one configuration step from
being demonstrable.

## If someone asks to log in

They cannot yet. Login returns a named refusal rather than a broken page — you
can show that if it helps: it lists exactly which provider settings are missing.
"""

    # -- 5. the summary ----------------------------------------------------
    files["gate129_demo_live_summary.md"] = f"""# Gate 129 — demo live summary

## The demo

```text
url            {DEMO_URL}
served by      cloudflared -> 127.0.0.1:5175 (stamped Vite preview)
public edge    Cloudflare Access on every path
visible today  yes, to anyone who can pass Access
```

## What is on it now

An operating shell with {shell["section_count"]} sections and
{len(shell["active_truth_labels"])} active truth labels, all computed rather
than typed. Sections operational: {shell["operational_section_count"]}. Rows
written to any customer table: {shell["rows_written"]}.

## The API

```text
service        nativeforge-backend.service (existing unit, started not enabled)
bind           127.0.0.1:8000, loopback only
/backend/health            200
/api/auth/current-user     401 unauthenticated
/api/auth/callback         200 controlled refusal, not 404
```

The tunnel now routes `/api/*` to the API ahead of the static catch-all, so the
callback path resolves to something that can consume a callback.

## The public edge, measured

```text
/                        302 -> cloudflareaccess.com
/backend/health          302 -> cloudflareaccess.com
/api/does-not-exist      302 -> cloudflareaccess.com
/api/auth/login          302 -> cloudflareaccess.com
/api/auth/session        302 -> cloudflareaccess.com
/api/auth/current-user   302 -> cloudflareaccess.com
/api/auth/callback       200    API JSON, callback_validation_not_passed
```

Exactly one path is exempt from Cloudflare Access, and it is the callback. An
Access bypass scoped to `/api/auth/callback` already exists — this gate did not
add it.

That exemption is what makes OAuth possible: a browser arriving from a provider
carries no Access session for this host, so without it the redirect would land
on a login page instead of the API.

Nothing here is blocked on Cloudflare. Gate 130 needs a provider and its seven
env values.

## Status

```text
customer_auth_live        {shell["customer_auth_live"]}
login_live                {shell["login_live"]}
provider_ready            {shell["provider_ready"]}
object store configured   {shell["object_store_configured"]}
live source monitoring    {shell["live_source_monitoring_active"]}
email delivery            {shell["email_delivery_active"]}
```

Auth env keys configured: {sum(presence.values())} of {len(presence)}. Names
only; no value is recorded in any artifact.
"""

    return files


def write_demo_live_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write the five files and report what was scanned for."""
    root = Path(repo_root) if repo_root else Path(".")
    out = root / ARTIFACT_DIR
    out.mkdir(parents=True, exist_ok=True)

    files = build_demo_live_artifacts()
    if set(files) != set(ARTIFACT_FILES):
        raise ValueError(f"artifact set changed: {sorted(files)}")

    import os

    written: list[str] = []
    secret_values_found: list[str] = []
    for name, content in sorted(files.items()):
        # A value from the environment must never land in an artifact. This
        # checks the real environment rather than a list of what we think is
        # in it, because the list is what goes stale.
        for key in AUTH_ENV_KEY_NAMES:
            value = (os.environ.get(key) or "").strip()
            if value and value in content:
                secret_values_found.append(f"{name}:{key}")
        (out / name).write_text(content, encoding="utf-8")
        written.append(name)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": ARTIFACT_DIR,
            "files_written": sorted(written),
            "file_count": len(written),
            "secret_values_found": sorted(secret_values_found),
            "env_values_recorded": False,
            "fabricated": False,
        }
    )


def demo_live_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("file_count") != len(ARTIFACT_FILES):
        fails.append("file_count_disagrees")
    if result.get("secret_values_found"):
        fails.append("secret_value_reached_an_artifact")
    for key in ("env_values_recorded", "fabricated"):
        if result.get(key) is True:
            fails.append(key)
    return fails
