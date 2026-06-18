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

if [ "${OWNPAPER_PROCESS_PRIVACY_EXCLUSIONS:-true}" = "true" ]; then
    python manage.py processar_exclusoes_privacidade_newsletter
fi

if [ "${OWNPAPER_CLEAN_PRIVACY_EXPORTS:-true}" = "true" ]; then
    python manage.py limpar_exportacoes_privacidade --dias "${OWNPAPER_PRIVACY_EXPORT_RETENTION_DAYS:-7}"
fi

if [ "${OWNPAPER_COLLECTSTATIC:-true}" = "true" ]; then
    python manage.py collectstatic --noinput --clear
fi

if [ "${OWNPAPER_PRECOMPUTE_SEARCH_CACHE:-false}" = "true" ]; then
    python manage.py aquecer_cache_busca_multilingue --limite "${OWNPAPER_PRECOMPUTE_SEARCH_CACHE_LIMIT:-200}"
fi

exec "$@"
