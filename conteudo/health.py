import os
import shutil
import socket
from pathlib import Path

from django.core.mail import get_connection
from django.utils import timezone
from wagtail.models import Site

from .backup_ops import _backup_backend_config, _diretorio_backups, backup_agendado_pendente, simular_restore_backup
from .models import AuditLog, BackupExecucao, ConfiguracaoSite


def _item(nome, status, mensagem, detalhes=None):
    return {
        "nome": nome,
        "status": status,
        "mensagem": mensagem,
        "detalhes": detalhes or {},
    }


def _formatar_bytes(valor):
    valor = float(valor or 0)
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if valor < 1024 or unidade == "TB":
            return f"{valor:.1f} {unidade}"
        valor /= 1024
    return f"{valor:.1f} TB"


def _checar_backup(site, config):
    backup_config = _backup_backend_config()
    ultimo = (
        BackupExecucao.objects.filter(site=site, status=BackupExecucao.STATUS_CONCLUIDO)
        .order_by("-criado_em")
        .first()
    )
    if not ultimo:
        return _item(
            "Backup",
            "warn",
            "Nenhum backup concluído encontrado.",
            {"periodo_horas": backup_config["interval_hours"]},
        )

    detalhes = {
        "arquivo": ultimo.arquivo_caminho,
        "criado_em": ultimo.criado_em,
        "checksum": ultimo.checksum_sha256,
        "tamanho": ultimo.arquivo_tamanho_bytes,
    }
    if backup_agendado_pendente(site):
        return _item(
            "Backup",
            "warn",
            "Existe backup concluído, mas a próxima execução agendada está pendente.",
            detalhes,
        )
    if not ultimo.arquivo_caminho or not Path(ultimo.arquivo_caminho).exists():
        return _item("Backup", "error", "O último backup registrado não existe no disco.", detalhes)

    validacao = simular_restore_backup(ultimo.arquivo_caminho, ultimo.checksum_sha256)
    detalhes["restore_dry_run"] = validacao
    if not validacao.get("ok"):
        return _item("Backup", "error", f"Último backup falhou no dry-run: {validacao.get('erro')}", detalhes)
    return _item("Backup", "ok", "Último backup concluído e validado em dry-run.", detalhes)


def _checar_destino_externo(config):
    backup_config = _backup_backend_config()
    destino = backup_config["external_backend"]
    if destino == "local":
        return _item(
            "Destino externo",
            "warn",
            "Backup externo não configurado. O sistema mantém apenas cópias locais.",
        )
    if destino == "webdav":
        if not backup_config["webdav_url"]:
            return _item("Destino externo", "error", "WebDAV habilitado no ambiente sem URL configurada.")
        if backup_config["webdav_username"] and not backup_config["webdav_password"]:
            return _item(
                "Destino externo",
                "error",
                "WebDAV habilitado no ambiente, mas a senha não está disponível.",
                {"url": backup_config["webdav_url"]},
            )
        return _item(
            "Destino externo",
            "ok",
            "WebDAV configurado para envio externo automático dos ZIPs de backup.",
            {"url": backup_config["webdav_url"], "usuario": backup_config["webdav_username"] or "-"},
        )
    return _item("Destino externo", "error", f"Destino externo desconhecido: {destino}")


def _checar_logs():
    resultado = AuditLog.verificar_integridade()
    if resultado.get("ok"):
        return _item(
            "Logs de auditoria",
            "ok",
            f"Cadeia íntegra com {resultado.get('total', 0)} registro(s).",
            {"ultimo_hash": resultado.get("ultimo_hash", "")},
        )
    return _item(
        "Logs de auditoria",
        "error",
        resultado.get("erro") or "Falha na cadeia de logs.",
        resultado,
    )


def _checar_clamav():
    clamav_enabled = str(os.getenv("OWNPAPER_CLAMAV_ENABLED", "false")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not clamav_enabled:
        return _item("ClamAV", "warn", "Varredura antivírus está desativada.")
    host = os.getenv("OWNPAPER_CLAMAV_HOST", "clamav")
    port = int(os.getenv("OWNPAPER_CLAMAV_PORT", "3310") or "3310")
    try:
        with socket.create_connection((host, port), timeout=5):
            return _item("ClamAV", "ok", "Serviço ClamAV acessível.", {"host": host, "port": port})
    except OSError as exc:
        return _item("ClamAV", "error", f"ClamAV indisponível: {exc}", {"host": host, "port": port})


def _checar_email(config):
    if not config.backup_enviar_relatorio:
        return _item("E-mail", "warn", "Envio de relatório de backup por e-mail está desativado.")
    if not config.backup_email_destino:
        return _item("E-mail", "error", "Relatório de backup ativado sem e-mail de destino.")
    try:
        connection = get_connection(fail_silently=False)
        connection.close()
    except Exception as exc:
        return _item("E-mail", "warn", f"Configuração de e-mail não pôde ser pré-validada: {exc}")
    return _item("E-mail", "ok", "E-mail de relatório configurado.", {"destino": config.backup_email_destino})


def _checar_disco():
    backups_dir = _diretorio_backups()
    usage = shutil.disk_usage(backups_dir)
    livre_pct = (usage.free / usage.total) * 100 if usage.total else 0
    detalhes = {
        "diretorio": str(backups_dir),
        "total": _formatar_bytes(usage.total),
        "livre": _formatar_bytes(usage.free),
        "livre_pct": f"{livre_pct:.1f}%",
    }
    if livre_pct < 10:
        return _item("Disco", "error", "Espaço livre crítico para backups/mídia.", detalhes)
    if livre_pct < 20:
        return _item("Disco", "warn", "Espaço livre baixo para backups/mídia.", detalhes)
    return _item("Disco", "ok", "Espaço livre suficiente.", detalhes)


def _checar_retencao(config):
    backup_config = _backup_backend_config()
    detalhes = {
        "backup_reter_dias": backup_config["retention_days"],
        "estatisticas_brutas_dias": config.estatisticas_reter_eventos_brutos_dias,
        "estatisticas_agregadas_dias": config.estatisticas_reter_agregados_dias,
    }
    if int(backup_config["retention_days"] or 0) < 7:
        return _item("Retenção", "warn", "Retenção de backups abaixo de 7 dias.", detalhes)
    return _item("Retenção", "ok", "Políticas de retenção configuradas.", detalhes)


def avaliar_saude_operacional(site=None):
    site = site or Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    if not site:
        return {
            "status": "error",
            "gerado_em": timezone.now(),
            "itens": [_item("Site", "error", "Nenhum site Wagtail encontrado.")],
        }

    config = ConfiguracaoSite.for_site(site)
    itens = [
        _checar_backup(site, config),
        _checar_destino_externo(config),
        _checar_logs(),
        _checar_clamav(),
        _checar_email(config),
        _checar_disco(),
        _checar_retencao(config),
    ]
    if any(item["status"] == "error" for item in itens):
        status = "error"
    elif any(item["status"] == "warn" for item in itens):
        status = "warn"
    else:
        status = "ok"
    return {
        "status": status,
        "site": site,
        "gerado_em": timezone.now(),
        "itens": itens,
    }
