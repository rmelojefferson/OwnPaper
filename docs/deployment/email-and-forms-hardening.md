# Reforço de segurança para e-mails e formulários

Este guia cobre ajustes recomendados para produção nos fluxos de contato, newsletter e formulários públicos.

## 0. Use o arquivo de ambiente de produção

```bash
cp .env.production.example .env
```

Depois substitua os valores de exemplo, como domínio, credenciais SMTP, chaves do Turnstile e segredos.

## 1. Ative o Cloudflare Turnstile

Configure as duas variáveis no `.env`:

```text
TURNSTILE_SITE_KEY=...
TURNSTILE_SECRET_KEY=...
```

Quando as duas variáveis estão presentes, o OwnPaper ativa o Turnstile automaticamente nos formulários públicos compatíveis.

## 2. Configure SMTP e identidade do remetente

Configure as credenciais SMTP:

```text
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=...
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=...
DJANGO_EMAIL_HOST_PASSWORD=...
DJANGO_EMAIL_USE_TLS=true
DJANGO_DEFAULT_FROM_EMAIL=no-reply@seudominio.com
```

## 3. Publique SPF, DKIM e DMARC

No DNS do domínio remetente:

- SPF: autorize o provedor SMTP a enviar e-mails em nome do domínio.
- DKIM: publique as chaves dos seletores DKIM fornecidos pelo provedor.
- DMARC: comece em modo de monitoramento (`p=none`) e avance para política mais restritiva depois de validar os envios.

Exemplo inicial de registro DMARC:

```text
Host: _dmarc.seudominio.com
Tipo: TXT
Valor: v=DMARC1; p=none; rua=mailto:dmarc@seudominio.com; adkim=s; aspf=s
```

## 4. Ajuste limites e retentativas

Os padrões são adequados para a maioria dos sites editoriais pequenos. Ajuste apenas se houver necessidade operacional:

```text
OWNPAPER_FORM_RATE_LIMIT_WINDOW_SECONDS=600
OWNPAPER_FORM_RATE_LIMIT_MAX_ATTEMPTS_IP=5
OWNPAPER_FORM_RATE_LIMIT_MAX_ATTEMPTS_EMAIL=3
OWNPAPER_FORM_RATE_LIMIT_BACKOFF_BASE_SECONDS=120
OWNPAPER_FORM_RATE_LIMIT_BACKOFF_MAX_SECONDS=3600
```

## 5. Limites de entrada

```text
OWNPAPER_CONTACT_MAX_NOME_LENGTH=120
OWNPAPER_CONTACT_MAX_MENSAGEM_LENGTH=5000
OWNPAPER_NEWSLETTER_MAX_EMAIL_LENGTH=254
```

## 6. Rotina de retenção para mensagens de contato

Limpeza manual:

```bash
docker compose exec web python manage.py limpar_mensagens_contato --dias 365
```

Exemplo de cron recomendado, diariamente às 03:00:

```cron
0 3 * * * cd /caminho/para/OwnPaper && docker compose exec -T web python manage.py limpar_mensagens_contato --dias 365
```

## 7. Logs de eventos de segurança

Abusos e falhas em formulários são registrados pelo logger `conteudo.forms_security`.

Controle o nível de detalhamento com:

```text
OWNPAPER_FORMS_SECURITY_LOG_LEVEL=INFO
```

## 8. Comando de validação para produção

Execute uma validação guiada:

```bash
docker compose exec -T web python manage.py validar_producao_ownpaper
```

Modo estrito, falhando também em avisos:

```bash
docker compose exec -T web python manage.py validar_producao_ownpaper --strict
```

Verificações reais úteis:

```bash
# conexão SMTP real
docker compose exec -T web python manage.py validar_producao_ownpaper --smtp-connect

# teste real de envio SMTP
docker compose exec -T web python manage.py validar_producao_ownpaper --smtp-send-test-to seu-email@dominio.com

# verificação de token Turnstile gerado no frontend
docker compose exec -T web python manage.py validar_producao_ownpaper --turnstile-token "<token>"

# simulação de restauração usando o backup mais recente
docker compose exec -T web python manage.py validar_producao_ownpaper --backup-latest
```

Observações:

- O comando informa `OK`, `Aviso` e `Erro`.
- Use `--strict` para falhar também quando houver avisos.
