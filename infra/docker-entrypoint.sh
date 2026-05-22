#!/bin/sh
set -e

CMD="${1:-serve}"

case "$CMD" in
  migrate)
    echo "[entrypoint] alembic upgrade head"
    exec alembic upgrade head
    ;;

  serve)
    if [ "${RUN_MIGRATIONS_ON_START:-0}" = "1" ]; then
      echo "[entrypoint] running alembic upgrade head before serve"
      alembic upgrade head
    fi

    echo "[entrypoint] starting gunicorn on 0.0.0.0:${APP_PORT:-8800}"
    exec gunicorn app.main:app \
      --workers "${GUNICORN_WORKERS:-2}" \
      --worker-class uvicorn.workers.UvicornWorker \
      --bind "0.0.0.0:${APP_PORT:-8800}" \
      --timeout "${GUNICORN_TIMEOUT:-60}" \
      --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-30}" \
      --access-logfile - \
      --error-logfile -
    ;;

  shell)
    exec python
    ;;

  *)
    exec "$@"
    ;;
esac
