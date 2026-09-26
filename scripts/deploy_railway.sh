#!/usr/bin/env bash
#
# Deploy the exact committed SHA to Railway, and stamp it.
#
# WHY THIS EXISTS
# ---------------
# `NF_GIT_SHA` was first set as a literal value by hand. That worked for one
# deployment and was a defect waiting to happen: the next deploy would have
# reported the previous commit, and a health endpoint that confidently names
# the wrong commit is worse than one that admits it does not know.
#
# Railway's own `${{ RAILWAY_GIT_COMMIT_SHA }}` does not resolve as a variable
# reference - tested with and without spaces, both produced an empty string in
# a live deployment. The container entrypoint reads that variable directly if
# the platform injects it, but this wrapper does not depend on that: it sets
# the value from git before triggering the deploy, so the stamp is correct
# whatever the provider does.
#
# Refuses to deploy a dirty tree, because `source_dirty=false` would then be a
# lie, and refuses to deploy a commit that is not on the remote, because the
# provider builds from the remote and would silently build something else.

set -euo pipefail

SERVICE="${NF_RAILWAY_SERVICE:-nativeforge}"
ENVIRONMENT="${NF_RAILWAY_ENV:-controlled-live}"
RAILWAY="${RAILWAY_CLI:-npx --yes @railway/cli@latest}"

log() { printf '[deploy] %s\n' "$*"; }
die() { printf '[deploy] FATAL: %s\n' "$*" >&2; exit 1; }

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── the tree must be exactly what will run ──────────────────────────────
dirty="$(git status --porcelain --untracked-files=no)"
if [ -n "${dirty}" ]; then
    printf '%s\n' "${dirty}" >&2
    die "working tree has uncommitted tracked changes; source_dirty=false would be false"
fi

SHA="$(git rev-parse HEAD)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

# The provider builds from the remote, so a local-only commit would deploy
# something other than what was verified here.
if ! git branch -r --contains "${SHA}" 2>/dev/null | grep -q .; then
    die "commit ${SHA} is not on any remote branch; push before deploying"
fi

log "service     ${SERVICE}"
log "environment ${ENVIRONMENT}"
log "branch      ${BRANCH}"
log "sha         ${SHA}"

# ── stamp the identity, then deploy ─────────────────────────────────────
#
# --skip-deploys on the stamps so a half-configured deployment is never
# created; the redeploy below is the single deliberate trigger.
log "stamping deployment identity"
${RAILWAY} variable set "NF_GIT_SHA=${SHA}" \
    --service "${SERVICE}" --environment "${ENVIRONMENT}" --skip-deploys >/dev/null
${RAILWAY} variable set "NF_SOURCE_DIRTY=false" \
    --service "${SERVICE}" --environment "${ENVIRONMENT}" --skip-deploys >/dev/null

log "triggering deployment"
${RAILWAY} redeploy --service "${SERVICE}" --environment "${ENVIRONMENT}" --yes

cat <<EOF

[deploy] verify with:

  curl -s https://<service-domain>/health

[deploy] expected:

  "git_sha": "${SHA}"
  "source_dirty": false
  "deployment_identity_known": true
EOF
