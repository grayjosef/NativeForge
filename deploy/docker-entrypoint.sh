#!/usr/bin/env bash
#
# Deterministic startup. Three commands, nothing provider-specific.
#
#   serve     run migrations (unless told not to) and start the API
#   migrate   run migrations and exit - for a release phase that runs
#             separately from the app, which is what you want the moment
#             there is more than one replica
#   *         exec anything else, so `docker run ... bash` still works
#
# Migrations run on boot by default because controlled-live is a single
# instance and a database that silently lags the code is worse than a slow
# start. With multiple replicas, set NF_RUN_MIGRATIONS=false and run the
# `migrate` command as its own release step: concurrent `alembic upgrade head`
# from several containers is a race, and Alembic does not arbitrate it.

set -euo pipefail

: "${PORT:=8000}"
: "${NF_RUN_MIGRATIONS:=true}"

log() { printf '[entrypoint] %s\n' "$*"; }

# ── deployment identity ──────────────────────────────────────────────────
#
# The application knows only NF_GIT_SHA and NF_SOURCE_DIRTY. Translating a
# provider's own name for the commit belongs here, in deployment tooling,
# and NOT in application code - the moment `settings.py` reads
# RAILWAY_GIT_COMMIT_SHA the image stops being provider-neutral.
#
# Checked in order; the first non-empty wins. NF_GIT_SHA set explicitly by a
# deploy wrapper always takes precedence.
for _candidate in \
    "${NF_GIT_SHA:-}" \
    "${RAILWAY_GIT_COMMIT_SHA:-}" \
    "${SOURCE_VERSION:-}" \
    "${VERCEL_GIT_COMMIT_SHA:-}" \
    "${GITHUB_SHA:-}" \
    "${CI_COMMIT_SHA:-}"; do
    if [ -n "${_candidate}" ]; then
        NF_GIT_SHA="${_candidate}"
        break
    fi
done
export NF_GIT_SHA="${NF_GIT_SHA:-}"

identity_known() {
    case "${NF_GIT_SHA}" in
        "" | unknown) return 1 ;;
        *) return 0 ;;
    esac
}

#: Environments where serving an unidentifiable build is a defect rather than
#: a developer convenience. A local or test run may be anonymous; a
#: controlled-live one may not.
require_identity() {
    case "${NF_APP_ENV:-local}" in
        controlled-live | staging | production | prod) return 0 ;;
        *) return 1 ;;
    esac
}

case "${1:-serve}" in
  migrate)
    log "alembic upgrade head"
    exec alembic upgrade head
    ;;

  serve)
    if [ -z "${DATABASE_URL:-}" ]; then
      log "FATAL: DATABASE_URL is not set"
      exit 2
    fi

    # Fail loudly rather than serve an anonymous build.
    #
    # A deployment that cannot name its commit cannot be verified: "is the new
    # version live?" stops having an answer, and a rollback cannot be
    # confirmed. This is not hypothetical - a variable reference that did not
    # resolve put an empty git_sha into a controlled-live deployment, which
    # looked like a healthy service.
    #
    # The value is never invented from filesystem state. An image that was not
    # told what it is does not get to guess.
    if require_identity && ! identity_known; then
      log "FATAL: NF_APP_ENV=${NF_APP_ENV:-} requires a deployment identity"
      log "  NF_GIT_SHA is empty or unknown, and no provider commit variable was found."
      log "  Set NF_GIT_SHA to the exact deployed commit (scripts/deploy_railway.sh does this)."
      exit 3
    fi

    if ! identity_known; then
      log "WARNING: serving without a deployment identity (NF_APP_ENV=${NF_APP_ENV:-local})"
    fi

    # Migration authority and runtime authority are different things.
    #
    # Alembic must own the schema; the application must not. A managed
    # provider issues one superuser credential, and a superuser bypasses
    # row-level security unconditionally - so an application connecting with
    # it is exempt from every policy protecting tenants.
    #
    # When NF_MIGRATION_DATABASE_URL is set, migrations use it and the server
    # runs as whatever DATABASE_URL names, which should be the restricted
    # role. When it is not set, both are the same credential and that is the
    # single-credential development case.
    if [ -n "${NF_MIGRATION_DATABASE_URL:-}" ]; then
      log "bootstrapping the restricted runtime role"
      DATABASE_URL="${NF_MIGRATION_DATABASE_URL}" \
        python /app/deploy/bootstrap_runtime_role.py || \
        log "WARNING: runtime role bootstrap reported a problem (see above)"
    fi

    if [ "${NF_RUN_MIGRATIONS}" = "true" ]; then
      log "alembic upgrade head"
      DATABASE_URL="${NF_MIGRATION_DATABASE_URL:-${DATABASE_URL}}" alembic upgrade head
    else
      log "NF_RUN_MIGRATIONS=false - skipping migrations"
    fi

    # Opt-in, bounded self-verification at boot.
    #
    # Two facts can only be measured from inside the deployed artifact on the
    # provider's own network: that the MANAGED database refuses the wrong
    # tenant, and that OCR executes here rather than merely having been
    # installed. Providers vary in whether they expose a one-shot command, and
    # the alternatives are worse - an account-wide SSH key, or a debug route
    # that outlives the question it answered.
    #
    # So it runs at boot, only when explicitly asked, writes its receipt to
    # the deployment log, and does not gate serving: a verification failure
    # must be visible without taking the service down, because an unavailable
    # service is not safer than one with a reported flaw.
    if [ "${NF_VERIFY_ON_BOOT:-false}" = "true" ]; then
      log "NF_VERIFY_ON_BOOT=true - running managed runtime verification"
      python /app/deploy/verify_managed_runtime.py || \
        log "WARNING: managed runtime verification reported failures (see above)"
      log "verification complete; continuing to serve"
    fi

    log "serving on 0.0.0.0:${PORT} (sha=${NF_GIT_SHA:-unknown})"
    exec uvicorn nativeforge.main:app \
      --host 0.0.0.0 \
      --port "${PORT}" \
      --proxy-headers \
      --forwarded-allow-ips '*'
    ;;

  *)
    exec "$@"
    ;;
esac
