# SCA Execution Readiness Packet (Gate 13 / Block 32)

## Status

* Packet: **complete**
* SCA run (default Gate 13 surface): **false**
* SCA passed: **false** unless tooling is run and green

## Recommended non-destructive commands

```bash
cd /home/josefgray/projects/nativeforge
source .venv/bin/activate
# If installed:
pip-audit --progress-spinner off
cd frontend && npm audit --omit=dev
```

Do not install broad new SCA tooling without approval.

## Claim rules

* `sca_run=true` only when a command actually executed
* `sca_passed_claimed=true` only on exit 0 / documented clean result
* Unresolved high/critical issues block production claims
