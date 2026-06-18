import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.core.mail import EmailMessage, get_connection
from wagtail.models import Site

from conteudo.backup_ops import _backup_backend_config, simular_restore_backup
from conteudo.models import ConfiguracaoSite


class Command(BaseCommand):
    help = (
        "Validação guiada de prontidão para produção: segurança básica, SMTP, "
        "Turnstile e restauração de backup (dry-run)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Falha também quando houver avisos (warnings).",
        )
        parser.add_argument(
            "--smtp-connect",
            action="store_true",
            help="Testa conexão SMTP real (open/login).",
        )
        parser.add_argument(
            "--smtp-send-test-to",
            default="",
            help="E-mail destino para teste real de envio SMTP.",
        )
        parser.add_argument(
            "--turnstile-token",
            default="",
            help="Token real do Turnstile para validar no endpoint da Cloudflare.",
        )
        parser.add_argument(
            "--backup-file",
            default="",
            help="Arquivo .zip de backup para validar restore em modo dry-run.",
        )
        parser.add_argument(
            "--backup-latest",
            action="store_true",
            help="Usa automaticamente o backup mais recente da pasta de backups.",
        )
        parser.add_argument(
            "--backup-checksum",
            default="",
            help="Checksum SHA256 esperado do backup (opcional).",
        )

    def handle(self, *args, **options):
        self.errors = []
        self.warnings = []
        self.ok = []

        self.stdout.write("Iniciando validação de produção...")

        self._validar_segurança_base()
        self._validar_turnstile(options)
        self._validar_smtp(options)
        self._validar_backups(options)
        self._validar_configuracao_sites()

        for item in self.ok:
            self.stdout.write(self.style.SUCCESS(f"OK: {item}"))
        for item in self.warnings:
            self.stdout.write(self.style.WARNING(f"Aviso: {item}"))
        for item in self.errors:
            self.stdout.write(self.style.ERROR(f"Erro: {item}"))

        if self.errors:
            raise CommandError(
                f"Validação finalizada com {len(self.errors)} erro(s) e "
                f"{len(self.warnings)} aviso(s)."
            )
        if options["strict"] and self.warnings:
            raise CommandError(
                f"Validação strict falhou: {len(self.warnings)} aviso(s) encontrado(s)."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Validação concluída sem erros ({len(self.ok)} OK / {len(self.warnings)} aviso(s))."
            )
        )

    def _validar_segurança_base(self):
        if settings.SECURE_SSL_REDIRECT:
            self.ok.append("`DJANGO_SECURE_SSL_REDIRECT` ativo.")
        else:
            self.warnings.append("`DJANGO_SECURE_SSL_REDIRECT` está desativado.")

        if settings.SESSION_COOKIE_SECURE:
            self.ok.append("`DJANGO_SESSION_COOKIE_SECURE` ativo.")
        else:
            self.warnings.append("`DJANGO_SESSION_COOKIE_SECURE` está desativado.")

        if settings.CSRF_COOKIE_SECURE:
            self.ok.append("`DJANGO_CSRF_COOKIE_SECURE` ativo.")
        else:
            self.warnings.append("`DJANGO_CSRF_COOKIE_SECURE` está desativado.")

        if int(settings.SECURE_HSTS_SECONDS or 0) > 0:
            self.ok.append("HSTS ativo (`DJANGO_SECURE_HSTS_SECONDS` > 0).")
        else:
            self.warnings.append("HSTS desativado (`DJANGO_SECURE_HSTS_SECONDS=0`).")

        hosts = [h.strip() for h in settings.ALLOWED_HOSTS if h.strip()]
        if not hosts:
            self.errors.append("`DJANGO_ALLOWED_HOSTS` está vazio.")
        else:
            self.ok.append(f"`ALLOWED_HOSTS` configurado ({len(hosts)} host(s)).")

    def _validar_turnstile(self, options):
        site_key = (settings.TURNSTILE_SITE_KEY or "").strip()
        secret_key = (settings.TURNSTILE_SECRET_KEY or "").strip()
        enabled = bool(settings.TURNSTILE_ENABLED)

        if site_key and secret_key and enabled:
            self.ok.append("Turnstile habilitado com site key e secret key.")
        elif site_key or secret_key:
            self.errors.append(
                "Turnstile incompleto: configure `TURNSTILE_SITE_KEY` e `TURNSTILE_SECRET_KEY` juntos."
            )
        else:
            self.warnings.append("Turnstile desativado (sem chaves configuradas).")

        token = (options.get("turnstile_token") or "").strip()
        if not token:
            return
        if not enabled:
            self.errors.append("`--turnstile-token` informado, mas Turnstile está desativado.")
            return

        data = urllib.parse.urlencode(
            {
                "secret": settings.TURNSTILE_SECRET_KEY,
                "response": token,
            }
        ).encode("utf-8")
        request_http = urllib.request.Request(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(request_http, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            self.errors.append(f"Falha na validação remota do Turnstile: {exc}")
            return

        if payload.get("success"):
            self.ok.append("Validação remota de token Turnstile: sucesso.")
        else:
            codigos = payload.get("error-codes") or []
            self.errors.append(
                f"Token Turnstile inválido/rejeitado. error-codes={codigos}"
            )

    def _validar_smtp(self, options):
        backend = (settings.EMAIL_BACKEND or "").strip()
        host = (settings.EMAIL_HOST or "").strip()
        user = (settings.EMAIL_HOST_USER or "").strip()
        password = (settings.EMAIL_HOST_PASSWORD or "").strip()
        from_email = (settings.DEFAULT_FROM_EMAIL or "").strip()
        tls = bool(settings.EMAIL_USE_TLS)
        ssl = bool(settings.EMAIL_USE_SSL)

        if backend == "django.core.mail.backends.smtp.EmailBackend":
            self.ok.append("Email backend SMTP configurado.")
        else:
            self.warnings.append(
                f"Email backend atual não é SMTP padrão: `{backend or '-'}`."
            )

        if not host:
            self.warnings.append("`DJANGO_EMAIL_HOST` não configurado.")
        else:
            self.ok.append("`DJANGO_EMAIL_HOST` configurado.")

        if not user:
            self.warnings.append("`DJANGO_EMAIL_HOST_USER` vazio.")
        else:
            self.ok.append("`DJANGO_EMAIL_HOST_USER` configurado.")

        if not password:
            self.warnings.append("`DJANGO_EMAIL_HOST_PASSWORD` vazio.")
        else:
            self.ok.append("`DJANGO_EMAIL_HOST_PASSWORD` configurado.")

        if tls and ssl:
            self.errors.append("Configuração inválida: `EMAIL_USE_TLS` e `EMAIL_USE_SSL` não podem estar ativos juntos.")
        elif tls or ssl:
            self.ok.append("Criptografia SMTP ativa (TLS/SSL).")
        else:
            self.warnings.append("SMTP sem TLS/SSL ativo.")

        if not from_email:
            self.warnings.append("`DJANGO_DEFAULT_FROM_EMAIL` não configurado.")
        else:
            self.ok.append("`DJANGO_DEFAULT_FROM_EMAIL` configurado.")

        if options.get("smtp_connect"):
            if not host:
                self.errors.append("`--smtp-connect` requer `DJANGO_EMAIL_HOST` configurado.")
                return
            try:
                connection = get_connection(fail_silently=False)
                connection.open()
                connection.close()
                self.ok.append("Conexão SMTP real estabelecida com sucesso.")
            except Exception as exc:
                self.errors.append(f"Falha na conexão SMTP real: {exc}")

        smtp_test_to = (options.get("smtp_send_test_to") or "").strip()
        if smtp_test_to:
            if not host:
                self.errors.append(
                    "`--smtp-send-test-to` requer `DJANGO_EMAIL_HOST` configurado."
                )
                return
            try:
                msg = EmailMessage(
                    subject="OwnPaper - Teste SMTP",
                    body=(
                        "<p>Teste de envio SMTP do OwnPaper.</p>"
                        "<p>Se você recebeu este e-mail, a integração está funcional.</p>"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[smtp_test_to],
                )
                msg.content_subtype = "html"
                msg.send(fail_silently=False)
                self.ok.append(f"E-mail de teste enviado para {smtp_test_to}.")
            except Exception as exc:
                self.errors.append(f"Falha no envio de teste SMTP para {smtp_test_to}: {exc}")

    def _validar_backups(self, options):
        arquivo = (options.get("backup_file") or "").strip()
        if options.get("backup_latest") and not arquivo:
            arquivo = self._backup_mais_recente()
            if arquivo:
                self.ok.append(f"Backup mais recente selecionado: {arquivo}")
            else:
                self.warnings.append("Nenhum backup encontrado para validar (`--backup-latest`).")
                return

        if not arquivo:
            self.warnings.append("Validação de restore não executada (use `--backup-file` ou `--backup-latest`).")
            return

        resultado = simular_restore_backup(
            arquivo_path=arquivo,
            checksum_esperado=(options.get("backup_checksum") or "").strip(),
        )
        if not resultado.get("ok"):
            self.errors.append(f"Dry-run de restore falhou: {resultado.get('erro')}")
            return

        manifesto = resultado.get("manifesto") or {}
        formato = manifesto.get("formato_db") or "-"
        inclui_midia = "sim" if manifesto.get("inclui_midia") else "não"
        self.ok.append(
            f"Dry-run de restore OK ({Path(arquivo).name} | db={formato} | mídia={inclui_midia})."
        )

    def _validar_configuracao_sites(self):
        backup_config = _backup_backend_config()
        if backup_config["enabled"] and int(backup_config["interval_hours"] or 0) <= 0:
            self.errors.append("OWNPAPER_BACKUP_INTERVAL_HOURS inválido.")
        if backup_config["enabled"] and int(backup_config["retention_days"] or 0) < 7:
            self.warnings.append("OWNPAPER_BACKUP_RETENTION_DAYS abaixo de 7 dias.")
        if backup_config["external_backend"] == "webdav":
            if not backup_config["webdav_url"]:
                self.errors.append("OWNPAPER_BACKUP_EXTERNAL_BACKEND=webdav sem OWNPAPER_BACKUP_WEBDAV_URL.")
            if backup_config["webdav_username"] and not backup_config["webdav_password"]:
                self.errors.append("WebDAV de backup com usuário configurado, mas sem senha no ambiente.")

        sites = Site.objects.all()
        if not sites.exists():
            self.errors.append("Nenhum Site cadastrado no Wagtail.")
            return

        for site in sites:
            config = ConfiguracaoSite.for_site(site)
            if not (config.nome_site or "").strip():
                self.warnings.append(f"Site `{site.hostname}` sem `nome_site` definido.")
            if config.backup_enviar_relatorio and not (config.backup_email_destino or "").strip():
                self.warnings.append(
                    f"Site `{site.hostname}` com relatório de backup ativo, mas sem e-mail de destino."
                )
            if int(config.notificacao_publicacoes_periodo_horas or 0) <= 0:
                self.errors.append(
                    f"Site `{site.hostname}` com `notificacao_publicacoes_periodo_horas` inválido."
                )
        self.ok.append(f"Configurações de {sites.count()} site(s) verificadas.")

    def _backup_mais_recente(self):
        base = os.getenv("OWNPAPER_BACKUP_DIR", "").strip()
        if base:
            diretorio = Path(base)
        else:
            diretorio = Path(settings.BASE_DIR) / "backups"
        if not diretorio.exists():
            return ""
        arquivos = sorted(diretorio.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not arquivos:
            return ""
        return str(arquivos[0])
