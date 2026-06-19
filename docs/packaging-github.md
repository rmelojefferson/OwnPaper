# Empacotamento e publicação no GitHub

Este checklist prepara o OwnPaper para publicação aberta.

## Antes do registro final no Git

```bash
git status --short
```

Confirme que não aparecem:

- `.env` real;
- backups reais;
- mídia pública ou privada;
- `node_modules`;
- `__pycache__`;
- `.pyc`;
- certificados;
- dumps de banco;
- logs privados.

## Validação técnica

```bash
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py makemigrations --check --dry-run
docker compose exec -T web python manage.py collectstatic --noinput --dry-run
docker compose exec -T web python manage.py test --keepdb
docker compose exec -T web python manage.py homologar_ownpaper
docker compose exec -T web python manage.py validar_producao_ownpaper --backup-latest
docker compose exec -T web python manage.py verificar_integridade_logs
```

## Documentação

A documentação usa MkDocs:

```bash
python -m venv .venv-docs
. .venv-docs/bin/activate
pip install -r docs/requirements.txt
mkdocs serve
```

Compilação estática:

```bash
mkdocs build
```

O diretório `site/` é gerado e não deve ser commitado.

## Licença

A licença padrão é MIT, escolhida por ser permissiva e facilitar adoção, forks e usos derivados.

Antes da publicação, confira também:

- `LICENSE`;
- `THIRD_PARTY_NOTICES.md`;
- `CONTRIBUTING.md`;
- `SECURITY.md`;
- [Governança e manutenção](governance-maintenance.md);
- [Licenças e terceiros](licensing-third-party.md).

O projeto foi desenvolvido em conjunto com OpenAI Codex e essa informação deve permanecer visível no README.

## GitHub

Recomendações iniciais:

- branch principal: `main`;
- GitHub Pages apontando para MkDocs;
- releases versionadas;
- issues e discussions habilitadas;
- security policy documentada;
- deixar claro que o projeto nasceu com auxílio de IA e deve ser revisado por operadores antes de produção.

## Publicação

O roteiro operacional de autenticação, criação de remoto e push está em
[Publicação no GitHub](deployment/github-publication.md).
