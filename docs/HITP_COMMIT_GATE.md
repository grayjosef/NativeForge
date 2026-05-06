# NativeForge HITP Commit Gate

No automatic commits. Every commit requires explicit human approval.

Valid approval phrases:
- approve commit
- commit it
- go commit

Required block before every commit:

```text
================ HITP COMMIT APPROVAL REQUIRED ================
Proposed commit message:
Branch:
Files changed:
Diff stat:
Backend validation run:
Backend validation result:
Frontend validation run:
Frontend validation result:
Migration status:
Test coverage touched:
Known risks:
What was intentionally not tested:
Why this is safe to commit:

Awaiting explicit human approval before running git commit.
Valid approvals: "approve commit", "commit it", or "go commit".
==============================================================
```

Frontend validation is mandatory when `frontend/package.json` exists. No commit may be made based only on backend tests.

Before `npm run typecheck` or `npm run build`, run **`npm ci`** in `frontend/` (or equivalent install) so local binaries such as `vite` and `tsc` exist under `node_modules/.bin`. CI does this automatically; local manual runs often fail with `vite: not found` / `tsc: not found` if `npm ci` was skipped. The repo script `scripts/nativeforge_full_validation.sh` runs `npm ci` before those commands.
