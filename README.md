# OwnPaper

OwnPaper is a self-hosted editorial CMS built on top of [Django](https://www.djangoproject.com/) and [Wagtail](https://wagtail.org/).

It was developed as a pragmatic editorial platform for an independent publishing workflow: public site, Wagtail-based admin panel, editorial review, reusable quiz questions, media quarantine, newsletter, comments, contact inbox, donations, privacy controls, internal statistics, backups, audit logs and Docker-based deployment.

This project was developed collaboratively with OpenAI Codex. The code should still be reviewed, tested and operated by the person or organization deploying it.

## Maintenance Position

OwnPaper is open source, but it is not currently planned as a continuously maintained general-purpose product.

The original maintainer intends to keep focusing on features, fixes and operational changes needed by the OwnPaper installations they personally use. If another person, community or organization wants to evolve the project in a broader direction, the recommended path is to fork the repository and maintain that fork independently.

Contributions may be useful, but there is no guaranteed response time, release cadence or long-term support commitment.

## License

OwnPaper is released under the MIT License. See [LICENSE](LICENSE).

MIT was chosen because it is permissive and allows use, modification, distribution, private deployments and forks with minimal restrictions.

Third-party dependencies keep their own licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Main Stack

- Python 3.12
- Django 5.2 LTS line
- Wagtail 7.4 line
- PostgreSQL 16
- Gunicorn
- WhiteNoise
- ClamAV for malware scanning of uploaded files
- Docker Compose for the default deployment path
- MkDocs Material for project documentation

## Current Features

- Wagtail-based admin panel customized for OwnPaper editorial workflows.
- Public site with home, publications, authors, categories, tags, search, RSS and donation page.
- Publications with authorship controls, update attribution, notes, references, credits, quiz blocks and PDF export.
- Editorial flow with review assignments, approvals, rejections, comments and audit history.
- Reusable quiz question catalog.
- Media quarantine for images, PDFs and videos, with sanitization and approval flow.
- Contact inbox with assignment, reply, forwarding, signatures and operator/admin visibility rules.
- Newsletter subscription, templates, CSV importer and notification workflows.
- Internal statistics with limited retention and recommendation for external analytics for deeper analysis.
- Optional integrations with Plausible, Umami, Matomo and Shlink.
- Privacy and consent flows for public users and admin users.
- Hash-chained audit logs for tamper-evidence at application level.
- Backend-managed backups with local and external storage support.
- Two-factor authentication for admin access.

## Project Layout

```text
config/      Django project settings, URLs, middleware, templates and static files
conteudo/    Main editorial/content application
home/        Wagtail home page application
docs/        MkDocs documentation
```

## Quick Start With Docker

Copy the example environment file:

```bash
cp .env.example .env
```

Build and start the services:

```bash
docker compose up -d --build
```

Create the first admin user:

```bash
docker compose exec web python manage.py createsuperuser
```

Bootstrap the initial Wagtail site and default settings:

```bash
docker compose exec web python manage.py bootstrap_ownpaper
```

Open the application:

```text
http://localhost:8000/
```

## Production Baseline

Use `.env.production.example` as the starting point for a production installation:

```bash
cp .env.production.example .env
```

Before production, configure at least:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- database credentials
- public hostname and HTTPS/proxy settings
- SMTP settings
- Turnstile keys if public forms are enabled
- ClamAV settings
- backup settings
- media/static volumes
- first admin creation process

The container entrypoint can wait for PostgreSQL, run migrations, collect static files and run bootstrap routines. These startup actions are controlled by environment variables documented in `docs/deployment/configuration.md`.

## Validation Commands

Run before publishing, deploying or packaging:

```bash
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py makemigrations --check --dry-run
docker compose exec -T web python manage.py collectstatic --noinput --dry-run
docker compose exec -T web python manage.py test --keepdb
docker compose exec -T web python manage.py homologar_ownpaper
docker compose exec -T web python manage.py validar_producao_ownpaper --backup-latest
docker compose exec -T web python manage.py verificar_integridade_logs
```

## Documentation

OwnPaper documentation is written with MkDocs and lives in `docs/`.

Install documentation dependencies:

```bash
python -m venv .venv-docs
. .venv-docs/bin/activate
pip install -r docs/requirements.txt
```

Run locally:

```bash
mkdocs serve
```

Build static documentation:

```bash
mkdocs build
```

The generated `site/` directory is ignored by Git.

## GitHub Publication

The local repository is prepared to be published as a normal GitHub repository. When it is time to publish, authenticate with GitHub and add the remote repository:

```bash
gh auth login
```

Then, after creating the empty GitHub repository:

```bash
git remote add origin git@github.com:YOUR_USER_OR_ORG/OwnPaper.git
git push -u origin main
```

If you want me to execute the GitHub login or push steps from this environment, tell me the target repository URL or GitHub organization first.

## Security Notice

OwnPaper includes several safety controls, but it is a self-hosted application. The deployer remains responsible for server security, HTTPS, SMTP reputation, backup storage, credentials, OS/container updates and production monitoring.

See [SECURITY.md](SECURITY.md) and `docs/deployment/homologacao-checklist.md` before production use.

## Legal And License Notice

The dependency/license inventory in this repository is a technical compliance aid, not legal advice. Before redistributing container images or offering OwnPaper commercially, review third-party licenses, system packages and image licenses according to your distribution model.
