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

    if [ "${NF_RUN_MIGRATIONS}" = "true" ]; then
      log "alembic upgrade head"
      alembic upgrade head
    else
      log "NF_RUN_MIGRATIONS=false - skipping migrations"
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
