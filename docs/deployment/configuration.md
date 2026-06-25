# Configuração por ambiente

OwnPaper separa configuração operacional sensível do painel administrativo.

## Arquivos de exemplo

- `.env.example`: instalação local ou base genérica;
- `.env.production.example`: produção HTTPS;
- `.env`: arquivo real da instalação, nunca deve ser commitado.

## Segredos

Configure no backend, não no painel:

```env
DJANGO_SECRET_KEY=
DATABASE_PASSWORD=
DJANGO_EMAIL_HOST_PASSWORD=
OWNPAPER_BACKUP_WEBDAV_PASSWORD=
OWNPAPER_SHLINK_API_KEY=
OWNPAPER_OAUTH_ORCID_CLIENT_SECRET=
OWNPAPER_OAUTH_GITHUB_CLIENT_SECRET=
OWNPAPER_OAUTH_GOOGLE_CLIENT_SECRET=
OWNPAPER_OAUTH_CODEBERG_CLIENT_SECRET=
```

## Configurações editáveis pelo painel

O painel concentra configurações editoriais e públicas:

- identidade e SEO;
- menu e navegação;
- tema e aparência;
- integrações e rastreamento;
- comunicação e comentários;
- apoio e doações;
- operação do site;
- páginas institucionais.

Credenciais sensíveis de backup externo não devem ser configuradas no painel.

## Segurança de uploads

Padrão recomendado:

```env
OWNPAPER_CLAMAV_ENABLED=true
OWNPAPER_CLAMAV_HOST=clamav
OWNPAPER_CLAMAV_PORT=3310
OWNPAPER_CLAMAV_TIMEOUT=30
OWNPAPER_VIDEO_MAX_MB=500
```

SVG não é aceito por padrão.

## Mídia pública

Arquivos enviados para imagens, documentos públicos e logos usam `DJANGO_MEDIA_URL` e `DJANGO_MEDIA_ROOT`.

Em instalação Docker direta, sem Nginx/Apache servindo `/media/`, ative:

```env
OWNPAPER_SERVE_PUBLIC_MEDIA=true
```

Em produção com proxy reverso servindo arquivos estáticos e mídia diretamente, mantenha:

```env
OWNPAPER_SERVE_PUBLIC_MEDIA=false
```

Essa opção serve apenas `MEDIA_ROOT`. A mídia privada/quarentena continua separada em `OWNPAPER_PRIVATE_MEDIA_VOLUME`.


### Exclusão de IPs das estatísticas

Para evitar contaminação por acessos internos, defina no `.env` os IPs públicos ou redes CIDR que não devem contar em visualizações e estatísticas internas:

```env
OWNPAPER_ANALYTICS_EXCLUDED_IPS=203.0.113.10,198.51.100.0/24
```

A lista aceita IPv4, IPv6 e CIDR. O OwnPaper usa o primeiro IP de `X-Forwarded-For` quando há proxy reverso, ou `REMOTE_ADDR` quando não houver.

Depois de alterar essa variável no `.env`, recrie o serviço web para o Docker reler o ambiente:

```bash
docker compose up -d web
```

### Exclusão automática de IP dinâmico

Quando a rede administrativa usa IP público dinâmico, configure um token no servidor:

```env
OWNPAPER_ANALYTICS_DYNAMIC_EXCLUDE_TOKEN=gere-um-token-longo
OWNPAPER_ANALYTICS_DYNAMIC_EXCLUDE_TTL_HOURS=72
```

Depois, em uma máquina dentro da rede que deve ser ignorada, agende uma chamada diária:

```bash
curl -fsS "https://seu-dominio.com/estatisticas/registrar-ip-ignorado/?token=gere-um-token-longo&nome=rede-local"
```

O servidor identifica o IP público pela própria requisição e passa a ignorá-lo nas visualizações e estatísticas internas até a expiração configurada. Não envie o IP como parâmetro.

No Windows, use o modelo:

```text
scripts/windows/atualizar-ip-ownpaper.bat
```

Edite `OWNPAPER_URL`, `OWNPAPER_TOKEN` e `OWNPAPER_NOME`. Para executar ao ligar a máquina, coloque o `.bat` no Agendador de Tarefas do Windows com o gatilho “Ao fazer logon”.

## Backups

```env
OWNPAPER_BACKUP_ENABLED=true
OWNPAPER_BACKUP_INTERVAL_HOURS=168
OWNPAPER_BACKUP_RETENTION_DAYS=30
OWNPAPER_BACKUP_INCLUDE_MEDIA=true
OWNPAPER_BACKUP_INCLUDE_PRIVATE_MEDIA=true
OWNPAPER_BACKUP_EXTERNAL_BACKEND=local
```

Para WebDAV externo:

```env
OWNPAPER_BACKUP_EXTERNAL_BACKEND=webdav
OWNPAPER_BACKUP_WEBDAV_URL=https://storage.example.com/remote.php/dav/files/usuario/ownpaper/
OWNPAPER_BACKUP_WEBDAV_USERNAME=usuario-backup
OWNPAPER_BACKUP_WEBDAV_PASSWORD=token-ou-senha-forte
```

Use conta exclusiva com permissão apenas na pasta de backups.

## SMTP

```env
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=smtp.example.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=usuario-smtp
DJANGO_EMAIL_HOST_PASSWORD=senha-ou-token
DJANGO_EMAIL_USE_TLS=true
DJANGO_EMAIL_USE_SSL=false
DJANGO_DEFAULT_FROM_EMAIL=no-reply@example.com
```

Valide SPF, DKIM e DMARC no domínio de envio.

## HTTPS

Em produção:

```env
DJANGO_SECURE_PROXY_SSL_HEADER=true
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
DJANGO_SECURE_HSTS_SECONDS=31536000
```

Ative HSTS para subdomínios e preload apenas quando todos os subdomínios estiverem prontos para HTTPS.
