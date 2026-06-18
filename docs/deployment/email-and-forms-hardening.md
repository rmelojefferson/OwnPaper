# Email and Forms Hardening

This guide covers production hardening for Contact and Newsletter flows.

## 0) Use production environment preset

```bash
cp .env.production.example .env
```

Then replace placeholders (domain, SMTP credentials, Turnstile keys, secrets).

## 1) Enable Cloudflare Turnstile

Set both variables in `.env`:

```text
TURNSTILE_SITE_KEY=...
TURNSTILE_SECRET_KEY=...
```

When both are present, OwnPaper enables Turnstile automatically on public forms.

## 2) Configure SMTP and sender identity

Set SMTP credentials:

```text
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=...
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=...
DJANGO_EMAIL_HOST_PASSWORD=...
DJANGO_EMAIL_USE_TLS=true
DJANGO_DEFAULT_FROM_EMAIL=no-reply@yourdomain.com
```

## 3) Publish SPF, DKIM and DMARC

For your sender domain (DNS):

- SPF: allow your SMTP provider to send on behalf of your domain.
- DKIM: publish provider DKIM selector key(s).
- DMARC: start with monitoring mode (`p=none`) and move to enforcement later.

Example DMARC starter record:

```text
Host: _dmarc.yourdomain.com
Type: TXT
Value: v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com; adkim=s; aspf=s
```

## 4) Rate limit / backoff tuning

Defaults are safe for most small editorial sites. Tune only if needed:

```text
OWNPAPER_FORM_RATE_LIMIT_WINDOW_SECONDS=600
OWNPAPER_FORM_RATE_LIMIT_MAX_ATTEMPTS_IP=5
OWNPAPER_FORM_RATE_LIMIT_MAX_ATTEMPTS_EMAIL=3
OWNPAPER_FORM_RATE_LIMIT_BACKOFF_BASE_SECONDS=120
OWNPAPER_FORM_RATE_LIMIT_BACKOFF_MAX_SECONDS=3600
```

## 5) Input limits

```text
OWNPAPER_CONTACT_MAX_NOME_LENGTH=120
OWNPAPER_CONTACT_MAX_MENSAGEM_LENGTH=5000
OWNPAPER_NEWSLETTER_MAX_EMAIL_LENGTH=254
```

## 6) Retention job for contact messages

Manual cleanup:

```bash
docker compose exec web python manage.py limpar_mensagens_contato --dias 365
```

Recommended cron (example, daily at 03:00):

```cron
0 3 * * * cd /path/to/OwnPaper && docker compose exec -T web python manage.py limpar_mensagens_contato --dias 365
```

## 7) Security event logs

Form abuse/failures are logged via logger `conteudo.forms_security`.

Control verbosity with:

```text
OWNPAPER_FORMS_SECURITY_LOG_LEVEL=INFO
```

## 8) Validation command (guided production readiness)

Run a guided validation pass:

```bash
docker compose exec -T web python manage.py validar_producao_ownpaper
```

Strict mode (fails on warnings too):

```bash
docker compose exec -T web python manage.py validar_producao_ownpaper --strict
```

Useful real checks:

```bash
# SMTP real connection
docker compose exec -T web python manage.py validar_producao_ownpaper --smtp-connect

# SMTP real send test
docker compose exec -T web python manage.py validar_producao_ownpaper --smtp-send-test-to seu-email@dominio.com

# Turnstile token verification (token generated on frontend)
docker compose exec -T web python manage.py validar_producao_ownpaper --turnstile-token "<token>"

# Backup restore dry-run using latest backup
docker compose exec -T web python manage.py validar_producao_ownpaper --backup-latest
```

Notes:

- The command reports `OK`, `Aviso` and `Erro`.
- Use `--strict` to fail on warnings as well.
