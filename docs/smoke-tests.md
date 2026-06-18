# Smoke Tests

Run these checks after dependency upgrades, Docker changes, or deployment
configuration changes.

```bash
export DJANGO_SECRET_KEY=ownpaper-local-test-secret-key-with-enough-length

docker compose build web
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py test conteudo --noinput
docker compose exec -T web python manage.py bootstrap_ownpaper --site-name OwnPaper --hostname localhost --port 80
docker compose exec -T web python manage.py homologar_ownpaper --keepdb
curl -I http://127.0.0.1:${OWNPAPER_HTTP_PORT:-8000}/
curl -I http://127.0.0.1:${OWNPAPER_HTTP_PORT:-8000}/account/login/
```

Expected results:

- `manage.py check` reports no issues.
- `manage.py test conteudo` passes.
- `manage.py homologar_ownpaper --keepdb` finaliza sem erro.
- Bootstrap completes without duplicating records.
- The home page returns `200 OK`.
- The two-factor login page returns `200 OK`.

## Optional Shlink smoke test

When validating the bundled optional short-link stack:

```bash
docker compose --profile shlink up -d
docker compose exec -T web python manage.py check
```

Expected results:

- `web`, `shlink` and `shlink-db` start without blocking each other.
- The site continues to work even if `shlink_ativo` is disabled.
- When Shlink is configured and enabled, publication share links can be shortened.
- When Shlink is unavailable, the site falls back to long URLs without breaking publication pages.
