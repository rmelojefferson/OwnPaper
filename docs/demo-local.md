# Demo local

O GitHub Pages publica apenas documentação estática. Ele não executa Django, Wagtail, PostgreSQL, autenticação, uploads, ClamAV ou rotinas de backend.

Por isso, a demo funcional do OwnPaper deve ser executada localmente ou em um servidor próprio.

## Subir a demo local

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec web python manage.py bootstrap_ownpaper
docker compose exec web python manage.py createsuperuser
```

## Acessos

```text
Site público: http://localhost:8000/
Painel admin: http://localhost:8000/admin/
```

## O que testar no site público

- home;
- publicações;
- autores;
- categorias e tags;
- busca;
- comentários;
- quiz;
- newsletter;
- contato;
- página de apoio/doações;
- consentimento de cookies e privacidade.

## O que testar no painel administrativo

- publicações;
- fluxo editorial;
- perguntas de quiz;
- mídia pendente/quarentena;
- imagens, documentos e vídeos;
- inbox de contato;
- newsletter;
- estatísticas;
- configurações do site;
- usuários, papéis e permissões;
- backups;
- logs de auditoria.

## Observação

Uma demo pública hospedada exige servidor Django ativo, banco de dados, domínio, HTTPS e política de credenciais. Não é recomendável expor uma demo admin aberta sem isolamento e resets automáticos.
