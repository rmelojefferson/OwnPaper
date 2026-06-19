# Instalação com Docker

Este é o caminho recomendado para instalar o OwnPaper em novas instâncias.

## Requisitos

- Docker e Docker Compose;
- domínio apontando para o servidor;
- proxy reverso HTTPS, como Nginx, Caddy ou Traefik;
- conta SMTP para envio de e-mails;
- espaço persistente para banco, mídia, mídia privada e backups;
- opcionalmente, armazenamento WebDAV externo para cópias de backup fora do servidor.

## Subir a instalação local

```bash
cp .env.example .env
```

Edite `.env` e ajuste pelo menos:

```env
DJANGO_SECRET_KEY=troque-por-uma-chave-longa
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_PASSWORD=troque-esta-senha
OWNPAPER_SITE_NAME=OwnPaper
OWNPAPER_SITE_HOSTNAME=localhost
OWNPAPER_ADMIN_USERNAME=primeiro-admin
OWNPAPER_ADMIN_EMAIL=admin@example.com
OWNPAPER_ADMIN_PASSWORD=troque-esta-senha
OWNPAPER_BOOTSTRAP=true
```

Suba os serviços:

```bash
docker compose up -d --build
```

Acompanhe o log inicial:

```bash
docker compose logs -f web
```

## Produção HTTPS

Use `.env.production.example` como base:

```bash
cp .env.production.example .env
```

Ajuste domínio, SMTP, segredos, banco e opções de HTTPS.

Depois suba:

```bash
docker compose up -d --build
```

Aplique o proxy reverso conforme [HTTPS e proxy reverso](https-reverse-proxy.md).

## Bootstrap inicial

O bootstrap cria estrutura mínima do Wagtail, páginas padrão, configurações do site, grupos de papéis e, opcionalmente, o primeiro admin.

Para executar manualmente:

```bash
docker compose exec -T web python manage.py bootstrap_ownpaper
```

Para forçar atualização de valores gerenciados pelo bootstrap:

```bash
docker compose exec -T web python manage.py bootstrap_ownpaper --force
```

Use `--force` com cuidado em sites já configurados.

## Validação pós-instalação

```bash
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py makemigrations --check --dry-run
docker compose exec -T web python manage.py collectstatic --noinput --dry-run
docker compose exec -T web python manage.py validar_saude_operacional
docker compose exec -T web python manage.py validar_producao_ownpaper --backup-latest
```

Para homologação completa:

```bash
docker compose exec -T web python manage.py homologar_ownpaper
```

## Serviços do Compose

- `web`: aplicação Django/Wagtail via Gunicorn;
- `scheduler`: tarefas periódicas de backup, retenção, privacidade e saúde operacional;
- `db`: PostgreSQL;
- `clamav`: antivírus para quarentena e sanitização de uploads;
- `shlink` e `shlink-db`: opcionais, ativados por profile para links curtos.

## Volumes importantes

- estáticos: `OWNPAPER_STATIC_VOLUME`;
- mídia pública: `OWNPAPER_MEDIA_VOLUME`;
- mídia privada/quarentena: `OWNPAPER_PRIVATE_MEDIA_VOLUME`;
- backups: `OWNPAPER_BACKUP_VOLUME`;
- PostgreSQL: volume `ownpaper_postgres`.

Não apague volumes sem backup validado.
