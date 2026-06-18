# Backups e restauração do OwnPaper

O OwnPaper permite dois níveis de operação:

- configuração operacional por `.env`, recomendada para responsáveis técnicos;
- configuração WebDAV exclusivamente no backend/ambiente, sem exposição de credenciais no painel administrativo.

## O que entra no backup

Cada backup gera um arquivo `.zip` em `/app/backups` contendo:

- dump do banco de dados;
- mídia pública (`/app/media`);
- mídia privada/quarentena (`/app/private_media`), quando habilitada;
- manifesto JSON;
- checksum SHA256 registrado no banco;
- dry-run automático de restore estrutural.

O backup não inclui segredos de `.env`, certificados TLS ou configuração do servidor/reverse proxy. Esses itens devem ser guardados separadamente pelo responsável pela instalação.

## Configuração por ambiente

Configure no `.env`:

```env
OWNPAPER_BACKUP_ENABLED=true
OWNPAPER_BACKUP_INTERVAL_HOURS=168
OWNPAPER_BACKUP_RETENTION_DAYS=30
OWNPAPER_BACKUP_INCLUDE_MEDIA=true
OWNPAPER_BACKUP_INCLUDE_PRIVATE_MEDIA=true
OWNPAPER_BACKUP_EXTERNAL_BACKEND=local
OWNPAPER_BACKUP_WEBDAV_URL=
OWNPAPER_BACKUP_WEBDAV_USERNAME=
OWNPAPER_BACKUP_WEBDAV_PASSWORD=
```

Valores recomendados:

- `OWNPAPER_BACKUP_INTERVAL_HOURS=168`: semanal.
- `OWNPAPER_BACKUP_RETENTION_DAYS=30`: mantém backups locais por 30 dias.
- `OWNPAPER_BACKUP_EXTERNAL_BACKEND=webdav`: envia o ZIP para WebDAV após validação local.
- WebDAV é configurado exclusivamente por variáveis de ambiente no backend; o painel apenas exibe o status operacional.

## WebDAV no backend e download protegido pelo painel

Acesse:

```text
Administração > Backups
```

A tela permite:

- configurar relatório por e-mail;
- solicitar backups por escopo;
- visualizar se o destino externo está configurado no backend;
- solicitar backup total para a fila;
- gerar link temporário de download local;
- ver histórico de backups e checksums.

WebDAV é um protocolo de armazenamento remoto. O OwnPaper não cria um servidor WebDAV automaticamente e não consegue definir uma URL segura por padrão. A URL deve vir de um serviço externo, como Nextcloud, Storage Box, servidor próprio ou provedor compatível, e deve ser configurada no backend por variáveis de ambiente.

As credenciais WebDAV não são as credenciais do usuário do painel e não são salvas no admin. Crie uma conta ou token exclusivo no armazenamento externo, com permissão apenas para a pasta de backups, e configure no ambiente do servidor.

Todas as ações sensíveis exigem senha atual e 2FA. Links de download enviados por e-mail expiram em 48 horas; links gerados pelo painel expiram em 1 hora. O link é invalidado após o download e registra auditoria.

## Execução automática

O serviço `scheduler` do Docker roda periodicamente:

```bash
docker compose logs -f scheduler
```

Ele verifica se o período venceu e executa:

```bash
python manage.py executar_backup_agendado
```

## Execução manual no backend

Para criar backup manual:

```bash
docker compose exec -T web python manage.py executar_backup_site
```

Para criar backup sem mídia:

```bash
docker compose exec -T web python manage.py executar_backup_site --sem-midia
```

## Validação de backup

Validar o backup mais recente pela homologação:

```bash
docker compose exec -T web python manage.py validar_producao_ownpaper --backup-latest
```

Validar um arquivo específico:

```bash
docker compose exec -T web python manage.py validar_arquivo_backup /app/backups/arquivo.zip --checksum CHECKSUM_SHA256
```

## Preparação de restauração

Primeiro, copie o arquivo `.zip` para o servidor, preferencialmente dentro do volume de backups:

```bash
docker compose cp ./arquivo.zip web:/app/backups/arquivo.zip
```

Faça dry-run:

```bash
docker compose exec -T web python manage.py restaurar_backup_site /app/backups/arquivo.zip --checksum CHECKSUM_SHA256
```

Extraia os arquivos para um diretório temporário:

```bash
docker compose exec -T web python manage.py restaurar_backup_site /app/backups/arquivo.zip --checksum CHECKSUM_SHA256 --executar
```

O comando informa os próximos passos para o tipo de dump encontrado.

## Restauração real

Execute a restauração real apenas em janela de manutenção e com backup atual preservado.

Para dump PostgreSQL (`.dump`), o comando indicará algo como:

```bash
pg_restore -c -d <database> <arquivo_dump>
```

Para dump JSON (`.json`), o comando indicará:

```bash
python manage.py loaddata <arquivo_json>
```

Para mídia:

```bash
tar -xzf <arquivo_media> -C <destino_media>
```

Depois da restauração:

```bash
docker compose exec -T web python manage.py migrate --noinput
docker compose exec -T web python manage.py collectstatic --noinput
docker compose restart web scheduler
docker compose exec -T web python manage.py validar_saude_operacional
docker compose exec -T web python manage.py verificar_integridade_logs
```

## Painel administrativo

O painel mostra:

- status dos backups;
- histórico;
- checksum;
- resultado do dry-run;
- relatório simples por e-mail;
- status do destino externo configurado no backend, sem expor credenciais no painel;
- geração protegida de link temporário para download de backups locais.

O painel não permite restaurar backups nem fazer upload de backup para restaurar o sistema. Restauração continua sendo uma operação de backend, documentada nesta página, para evitar que uma conta administrativa comprometida substitua toda a instalação.
