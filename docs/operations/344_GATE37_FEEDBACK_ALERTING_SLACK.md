# Gate 37 — Feedback Slack alerting (Mayhem notify path)

Slack delivery is **not proven live** until Mayhem sets a webhook out of
repo and a live test succeeds. Default mode is **dry_run**.

## What triggers an alert

Customer feedback / report hooks on `/?view=sc_customer_demo` (and any
caller of `send_feedback_slack_alert`). Demo assembler always force-dry-runs.

## Env names only (no values in git)

```text
NATIVEFORGE_FEEDBACK_ALERT_MODE=off|dry_run|live
NATIVEFORGE_FEEDBACK_SLACK_WEBHOOK_URL=<set out of repo>
NATIVEFORGE_FEEDBACK_ALERT_CHANNEL_LABEL=<non-secret label>
```

Default mode: `dry_run` (also the function default `force_dry_run=True`).

Mayhem sets the webhook in the WSL environment or systemd unit
`EnvironmentFile=` — never in the repository.

## Dry-run test

```bash
./scripts/dry_run_nativeforge_feedback_alert.sh
```

Expect `sent=False` and `slack_alert_status=dry_run`.

## Live test (Mayhem only)

Set mode `live` and webhook out of repo, then call
`send_feedback_slack_alert(..., force_dry_run=False)` from a trusted
operator shell. Missing webhook in live mode returns `config_error`
(fail closed for send — not a fake `sent`).

## Successful alert means

Mayhem (or the labeled channel) received a sanitized summary: timestamp,
env, org/contact if provided, type, severity, message summary, route,
internal id.

## It does NOT mean

Login live, production storage, customer persistence, pen-test passed,
controlled customer pilot GO, or production-ready.

Persistence of feedback is still **not claimed**.

## Failure modes

- mode `off`: no send
- mode `dry_run`: preview only
- live + missing webhook: `config_error`
- live + HTTP error: `failed`, `sent=false`
- webhook URL never logged

## Allowed claims

- Limited external demo
- Alert plumbing exists; live Slack is opt-in and unproven until Mayhem verifies

## Forbidden claims

Do not claim controlled customer pilot GO.
Do not claim production rollout GO.
Do not claim production-ready.
Do not claim login live.
Do not claim production storage.
Do not claim customer persistence.
Do not claim pen-test passed.
