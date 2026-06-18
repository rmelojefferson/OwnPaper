# Contributing to OwnPaper

OwnPaper is open source under the MIT License, but it is maintained primarily for the installations used by the original maintainer.

## Maintenance Scope

The maintainer does not currently intend to run OwnPaper as a continuously maintained general-purpose product. Work will be prioritized around:

- features needed by the maintainer's own installations;
- bug fixes affecting those installations;
- security or privacy issues that are relevant to the current codebase;
- packaging/documentation needed for deployment and reproducibility.

If you want a different roadmap, broader compatibility, a different UI direction or faster release cadence, the recommended path is to fork the project and maintain your own version.

## AI-Assisted Development Disclosure

OwnPaper was developed collaboratively with OpenAI Codex. Contributions should be reviewed as normal human-authored code: check correctness, security, maintainability, data handling and licensing before merging or deploying.

## Pull Requests

Pull requests are welcome, but may not be reviewed quickly. A useful pull request should include:

- clear description of the problem and solution;
- migrations, tests and documentation when applicable;
- no secrets, media dumps, backups or private data;
- no unrelated formatting churn;
- respect for the existing Django/Wagtail architecture;
- compatibility with the Docker deployment path.

## Development Checks

Run the baseline checks before opening a pull request:

```bash
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py makemigrations --check --dry-run
docker compose exec -T web python manage.py test --keepdb
docker compose exec -T web python manage.py homologar_ownpaper
docker compose exec -T web python manage.py validar_producao_ownpaper --backup-latest
```

## License Of Contributions

Unless explicitly stated otherwise, contributions submitted to this repository are assumed to be licensed under the same MIT License used by OwnPaper.
