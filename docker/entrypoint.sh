#!/bin/sh
set -eu

if [ "${OWNPAPER_WAIT_FOR_DB:-true}" = "true" ]; then
    echo "Waiting for PostgreSQL at ${DATABASE_HOST:-db}:${DATABASE_PORT:-5432}..."

    until nc -z "${DATABASE_HOST:-db}" "${DATABASE_PORT:-5432}"; do
        sleep 1
    done
fi

if [ "${OWNPAPER_RUN_MIGRATIONS:-true}" = "true" ]; then
    python manage.py migrate --noinput
fi

if [ "${OWNPAPER_BOOTSTRAP:-false}" = "true" ]; then
    python manage.py bootstrap_ownpaper
fi

if [ "${OWNPAPER_COLLECTSTATIC:-true}" = "true" ]; then
    python manage.py collectstatic --noinput --clear
fi

exec "$@"
