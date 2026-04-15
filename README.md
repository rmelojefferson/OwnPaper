# OwnPaper

OwnPaper is a self-hosted editorial CMS built with Django and Wagtail.

The current codebase is being extracted from a project-specific prototype into
a reusable application that can be installed on any server, configured through
the admin, and packaged with Docker.

## Current Status

This repository currently contains the working prototype:

- Wagtail CMS for editorial pages.
- Publications with authors, categories, tags, images, videos, notes, and references.
- Configurable home page with carousel, highlights, and latest publications.
- Institutional pages.
- Contact form.
- Newsletter subscription, cancellation, and privacy workflows.
- Research/indexer records with CSV import and export.
- Public search, sitemap, robots.txt, and publication PDF export.
- Two-factor authentication for admin access.
- Maintenance mode for public pages.

## Project Layout

```text
config/      Django project settings, URLs, middleware, templates, static files
conteudo/    Main editorial/content app
home/        Wagtail home page app
search/      Wagtail search view/template
docs/        Project and deployment notes
```

## Local Development

The Docker image uses Python 3.12 and is the supported development baseline.
If your local virtualenv uses an older Python version, recreate it before
running Django outside Docker.

The local entrypoint uses development settings:

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py runserver
```

The same checks can be run through Docker:

```bash
docker compose run --rm --no-deps --entrypoint python web manage.py check
docker compose run --rm --no-deps --entrypoint python web manage.py makemigrations --check --dry-run
```

Configuration is driven by environment variables. Use `.env.example` as the
starting point for database, hosts, static paths, media paths, secrets, email,
and HTTPS settings.

## Docker Compose

OwnPaper is PostgreSQL-first. The Compose setup runs the app and PostgreSQL:

```bash
cp .env.example .env
docker compose up -d --build
```

Then create an admin user:

```bash
docker compose exec web python manage.py createsuperuser
```

The app will be available on:

```text
http://localhost:8000/
```

To use another host port, change `OWNPAPER_HTTP_PORT` in `.env`.

The container entrypoint waits for PostgreSQL, runs migrations, collects static
files, and starts Gunicorn. These startup actions can be disabled with:

```text
OWNPAPER_WAIT_FOR_DB=false
OWNPAPER_RUN_MIGRATIONS=false
OWNPAPER_BOOTSTRAP=false
OWNPAPER_COLLECTSTATIC=false
```

## Initial Bootstrap

For a fresh installation, OwnPaper can prepare the Wagtail site, default pages,
site settings, and an optional admin user:

```bash
docker compose exec web python manage.py bootstrap_ownpaper
```

To run this automatically during container startup, set:

```text
OWNPAPER_BOOTSTRAP=true
OWNPAPER_SITE_NAME=OwnPaper
OWNPAPER_SITE_HOSTNAME=localhost
OWNPAPER_SITE_PORT=80
```

To create the first admin user automatically, also set:

```text
OWNPAPER_ADMIN_USERNAME=admin
OWNPAPER_ADMIN_EMAIL=admin@example.com
OWNPAPER_ADMIN_PASSWORD=change-this-password
```

The command is idempotent. It creates missing records and keeps existing
content by default. Use `OWNPAPER_BOOTSTRAP_FORCE=true` or `--force` only when
you want bootstrap-managed settings and pages to be overwritten.

## Packaging Direction

The OwnPaper packaging work should follow this order:

1. Document the current app and deployment assumptions.
2. Complete the Python dependency list.
3. Add `.env.example` with all configurable values and no secrets.
4. Move deployment-specific settings out of source code.
5. Add Docker Compose with app, PostgreSQL, static/media volumes, and optional nginx notes.
6. Move remaining public labels and install-time defaults into editable site settings.
7. Add a controlled Wagtail upgrade path and smoke-test suite.

## Deployment Notes

See [HTTPS without interrupting Plausible](docs/deployment/https-with-plausible.md)
for the current test-server situation.

See [Framework LTS upgrade policy](docs/upgrade-framework-lts.md) for the
current Django/Wagtail baseline.

See [Smoke tests](docs/smoke-tests.md) for the minimum validation flow before
deployment changes.
