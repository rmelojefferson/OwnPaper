# Framework LTS Upgrade Policy

OwnPaper follows a latest-LTS policy for frameworks where an LTS line is
available.

## Current Baseline

- Django 5.2 LTS
- Wagtail 7.0 LTS
- Python 3.12 in Docker

Do not use Wagtail 7.3 as the default package baseline unless a specific
feature or security issue requires it, because 7.3 is not an LTS release.

## Local Development

The old local `.venv` uses Python 3.8 and is no longer compatible with the
framework baseline. Recreate local development on Python 3.12 before using
`manage.py` outside Docker.

Until then, run checks and migrations through Docker.

## Validation Required

After framework upgrades, validate:

1. Dependency resolution and image build.
2. `makemigrations --check --dry-run`.
3. `manage.py check` with warnings enabled.
4. Database migrations.
5. `collectstatic`.
6. Public home page.
7. Admin redirect and two-factor login screen.
8. Bootstrap command.
9. Wagtail settings, snippets, images, admin CSV import, and newsletter flows.

## Sources

- https://docs.wagtail.org/en/stable/releases/upgrading.html
- https://docs.wagtail.org/en/stable/releases/7.0.html
- https://docs.wagtail.org/en/stable/releases/7.3.html
- https://docs.djangoproject.com/en/5.2/releases/5.2/
