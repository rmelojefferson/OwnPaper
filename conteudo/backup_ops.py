import hashlib
import json
import logging
import os
import base64
import http.client
import ipaddress
import secrets
import shutil
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.mail import EmailMessage
from django.db import connections
from django.urls import reverse
from django.utils import timezone

from .models import BackupExecucao, ConfiguracaoSite

logger = logging.getLogger(__name__)

BACKUP_SCOPE_TOTAL = "total"
BACKUP_SCOPE_TEXTOS = "textos"
BACKUP_SCOPE_MIDIAS = "midias"
BACKUP_SCOPE_CADASTROS = "cadastros"
BACKUP_SCOPE_LOGS = "logs"
BACKUP_SCOPE_CHOICES = [
    (BACKUP_SCOPE_TOTAL, "Backup total"),
    (BACKUP_SCOPE_TEXTOS, "Textos e estrutura editorial"),
    (BACKUP_SCOPE_MIDIAS, "Mídias públicas e privadas"),
    (BACKUP_SCOPE_CADASTROS, "Usuários, autores e cadastros"),
    (BACKUP_SCOPE_LOGS, "Logs e auditoria"),
]

_BACKUP_SCOPE_LABELS = {
    BACKUP_SCOPE_TEXTOS: [
        "wagtailcore.Page",
        "home.HomePage",
        "conteudo.PublicacoesIndexPage",
        "conteudo.PublicacaoPage",
        "conteudo.PublicacaoIdiomaManual",
        "conteudo.PublicacaoPageAutor",
        "conteudo.PublicacaoPageTag",
        "conteudo.ReferenciaPublicacao",
        "conteudo.NotaRodapePublicacao",
        "conteudo.NotaRodapePublicacaoIdiomaManual",
        "conteudo.MidiaIncorporadaPublicacao",
        "conteudo.ImagemPublicacao",
        "conteudo.Categoria",
        "conteudo.TagPublicacao",
        "conteudo.PerguntaQuizCatalogo",
        "conteudo.QuizOpcaoPerguntaCatalogo",
        "conteudo.PublicacaoPerguntaQuizCatalogo",
    ],
    BACKUP_SCOPE_CADASTROS: [
        "auth.User",
        "auth.Group",
        "auth.Permission",
        "conteudo.Autor",
        "conteudo.UsuarioPainelPerfil",
        "conteudo.ConviteUsuario",
        "conteudo.InscritoNewsletter",
        "conteudo.RegistroIndexador",
        "conteudo.RegistroIndexadorAutor",
        "conteudo.ComentarioPublicacao",
        "conteudo.UsuarioComentario",
        "conteudo.IdentidadeExternaComentario",
    ],
    BACKUP_SCOPE_LOGS: [
        "conteudo.AuditLog",
        "conteudo.BackupExecucao",
        "conteudo.PublicacaoRevisao",
        "conteudo.PublicacaoComentarioRevisao",
        "conteudo.MensagemContato",
        "conteudo.InteracaoMensagemContato",
        "conteudo.NewsletterEvento",
        "conteudo.DisparoEmail",
        "conteudo.DisparoEmailDestino",
        "conteudo.DisparoEmailClique",
    ],
}


def normalizar_escopo_backup(escopo):
    valor = (escopo or BACKUP_SCOPE_TOTAL).strip().lower()
    validos = {item[0] for item in BACKUP_SCOPE_CHOICES}
    return valor if valor in validos else BACKUP_SCOPE_TOTAL


def label_escopo_backup(escopo):
    escopo = normalizar_escopo_backup(escopo)
    return dict(BACKUP_SCOPE_CHOICES).get(escopo, "Backup total")


def escopo_inclui_midia(escopo):
    escopo = normalizar_escopo_backup(escopo)
    return escopo in {BACKUP_SCOPE_TOTAL, BACKUP_SCOPE_MIDIAS}


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value in {None, ""}:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default, minimum=None):
    try:
        value = int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    return value


def validar_url_webdav_segura(url):
    texto = (url or "").strip()
    if not texto:
        return False, "Informe a URL WebDAV."
    parsed = urllib.parse.urlparse(texto)
    if parsed.scheme != "https":
        return False, "Use apenas URL WebDAV com HTTPS."
    if not parsed.hostname:
        return False, "URL WebDAV sem host válido."
    host = parsed.hostname.strip().lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        return False, "URL WebDAV local não é permitida."
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False, "URL WebDAV com IP interno não é permitida."
    except ValueError:
        pass
    return True, ""


def _backup_backend_config(config=None):
    backend = (os.getenv("OWNPAPER_BACKUP_EXTERNAL_BACKEND", "local") or "local").strip().lower()
    if backend not in {"local", "webdav"}:
        backend = "local"
    env_webdav_url = (os.getenv("OWNPAPER_BACKUP_WEBDAV_URL", "") or "").strip()
    env_webdav_username = (os.getenv("OWNPAPER_BACKUP_WEBDAV_USERNAME", "") or "").strip()
    env_webdav_password = os.getenv("OWNPAPER_BACKUP_WEBDAV_PASSWORD", "") or ""
    fonte = "env"
    webdav_url = env_webdav_url
    webdav_username = env_webdav_username
    webdav_password = env_webdav_password
    return {
        "enabled": _env_bool("OWNPAPER_BACKUP_ENABLED", True),
        "interval_hours": _env_int("OWNPAPER_BACKUP_INTERVAL_HOURS", 168, minimum=1),
        "retention_days": _env_int("OWNPAPER_BACKUP_RETENTION_DAYS", 30, minimum=1),
        "include_media": _env_bool("OWNPAPER_BACKUP_INCLUDE_MEDIA", True),
        "include_private_media": _env_bool("OWNPAPER_BACKUP_INCLUDE_PRIVATE_MEDIA", True),
        "external_backend": backend,
        "external_config_source": fonte,
        "webdav_url": webdav_url,
        "webdav_username": webdav_username,
        "webdav_password": webdav_password,
    }


def _sha256_arquivo(path):
    hash_obj = hashlib.sha256()
    with open(path, "rb") as arquivo:
        for chunk in iter(lambda: arquivo.read(1024 * 1024), b""):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def gerar_token_download_backup(execucao, *, origem="email", horas_validade=48):
    token = secrets.token_urlsafe(32)
    agora = timezone.now()
    expira_em = agora + timedelta(hours=max(1, int(horas_validade or 48)))
    detalhes = dict(execucao.detalhes or {})
    detalhes["download_manual"] = {
        "token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest(),
        "origem": origem,
        "criado_em": agora.isoformat(),
        "expira_em": expira_em.isoformat(),
        "usado_em": "",
        "usado_por_id": None,
    }
    execucao.detalhes = detalhes
    execucao.save(update_fields=["detalhes"])
    return token, expira_em


def url_download_backup(execucao, token):
    path = reverse("admin_backup_download", args=[execucao.id, token])
    base = (getattr(execucao.site, "root_url", "") or "").rstrip("/")
    if base:
        return f"{base}{path}"
    host = getattr(execucao.site, "hostname", "") or ""
    if getattr(execucao.site, "port", 80) not in (80, 443, None):
        host = f"{host}:{execucao.site.port}"
    return f"https://{host}{path}"


def _caminho_zip_seguro(nome):
    texto = (nome or "").strip()
    if not texto:
        return False
    caminho = Path(texto)
    if caminho.is_absolute():
        return False
    if ".." in caminho.parts:
        return False
    return True


def _diretorio_backups():
    base = os.getenv("OWNPAPER_BACKUP_DIR", "").strip()
    if base:
        path = Path(base)
    else:
        path = Path(settings.BASE_DIR) / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _dump_banco_pg_dump(temp_dir, nome_base):
    db_cfg = connections["default"].settings_dict
    dump_path = temp_dir / f"{nome_base}.db.dump"
    env = os.environ.copy()
    if db_cfg.get("PASSWORD"):
        env["PGPASSWORD"] = str(db_cfg.get("PASSWORD"))

    cmd = [
        "pg_dump",
        "-h",
        str(db_cfg.get("HOST") or "127.0.0.1"),
        "-p",
        str(db_cfg.get("PORT") or "5432"),
        "-U",
        str(db_cfg.get("USER") or ""),
        "-d",
        str(db_cfg.get("NAME") or ""),
        "-Fc",
        "-f",
        str(dump_path),
    ]
    try:
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None, "pg_dump não disponível no ambiente"
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout or "Falha no pg_dump")
    return dump_path, ""


def _dump_banco_json(temp_dir, nome_base):
    dump_path = temp_dir / f"{nome_base}.db.json"
    with open(dump_path, "w", encoding="utf-8") as output:
        call_command("dumpdata", stdout=output)
    return dump_path


def _dump_modelos_json(temp_dir, nome_base, labels):
    dump_path = temp_dir / f"{nome_base}.db.json"
    with open(dump_path, "w", encoding="utf-8") as output:
        call_command("dumpdata", *labels, stdout=output)
    return dump_path


def _compactar_diretorio(temp_dir, nome_base, origem, sufixo, arcname):
    origem = Path(origem)
    if not origem.exists():
        return None
    arquivo = temp_dir / f"{nome_base}.{sufixo}.tar.gz"
    with tarfile.open(arquivo, "w:gz") as tar:
        tar.add(origem, arcname=arcname)
    return arquivo


def _aplicar_retencao(backups_dir, dias):
    if dias <= 0:
        return
    limite = timezone.now() - timedelta(days=dias)
    for item in backups_dir.glob("*.zip"):
        mtime = timezone.make_aware(datetime.fromtimestamp(item.stat().st_mtime))
        if mtime < limite:
            item.unlink(missing_ok=True)


def _enviar_relatorio_email(config, execucao):
    if not config.backup_enviar_relatorio or not config.backup_email_destino:
        return {"ok": False, "ignorado": True, "motivo": "Relatório desativado ou sem destinatário."}
    assunto = f"Relatório de backup - {execucao.site.hostname}"
    escopo = execucao.detalhes.get("escopo_label") or label_escopo_backup(execucao.detalhes.get("escopo"))
    corpo = (
        f"<p>Status: <strong>{execucao.get_status_display()}</strong></p>"
        f"<p>Escopo: {escopo}</p>"
        f"<p>Formato banco: {execucao.formato_db}</p>"
        f"<p>Inclui mídia: {'sim' if execucao.inclui_midia else 'não'}</p>"
        f"<p>Arquivo: {execucao.arquivo_caminho or '-'}</p>"
        f"<p>Tamanho: {execucao.arquivo_tamanho_bytes} bytes</p>"
        f"<p>Checksum: {execucao.checksum_sha256 or '-'}</p>"
    )
    if execucao.erro:
        corpo += f"<p>Erro: {execucao.erro}</p>"
    if execucao.status == BackupExecucao.STATUS_CONCLUIDO and execucao.arquivo_caminho:
        token, expira_em = gerar_token_download_backup(execucao, origem="email_relatorio", horas_validade=48)
        url_download = url_download_backup(execucao, token)
        corpo += (
            "<hr>"
            "<p><strong>Download manual protegido:</strong></p>"
            f'<p><a href="{url_download}">{url_download}</a></p>'
            f"<p>Este link expira em {expira_em.strftime('%d/%m/%Y %H:%M')} e exige login admin, senha atual e 2FA. "
            "O arquivo não é anexado ao e-mail.</p>"
        )

    msg = EmailMessage(
        subject=assunto,
        body=corpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[config.backup_email_destino],
    )
    msg.content_subtype = "html"

    resultado = {
        "ok": False,
        "destino": config.backup_email_destino,
        "remetente": settings.DEFAULT_FROM_EMAIL,
        "enviado_em": timezone.now().isoformat(),
    }
    try:
        enviados = msg.send(fail_silently=False)
        resultado.update({"ok": bool(enviados), "enviados": enviados})
    except Exception as exc:
        resultado.update({"erro": str(exc)[:1000]})
        logger.warning("Falha ao enviar relatório de backup %s: %s", execucao.pk, exc)

    detalhes = dict(execucao.detalhes or {})
    detalhes["email_relatorio"] = resultado
    execucao.detalhes = detalhes
    execucao.save(update_fields=["detalhes"])
    return resultado


def _webdav_request(backup_config, method, url, *, arquivo_path=None, body=None, content_type=None, timeout=120):
    ok_url, erro_url = validar_url_webdav_segura(url)
    if not ok_url:
        return {"ok": False, "erro": erro_url}
    parsed = urllib.parse.urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        path += f"?{parsed.query}"
    headers = {}
    webdav_username = backup_config.get("webdav_username") or ""
    webdav_password = backup_config.get("webdav_password") or ""
    if webdav_username:
        token = base64.b64encode(f"{webdav_username}:{webdav_password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    if content_type:
        headers["Content-Type"] = content_type

    conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=timeout)
    try:
        if arquivo_path:
            path_obj = Path(arquivo_path)
            tamanho = path_obj.stat().st_size
            headers["Content-Length"] = str(tamanho)
            conn.putrequest(method, path)
            for key, value in headers.items():
                conn.putheader(key, value)
            conn.endheaders()
            with open(path_obj, "rb") as arquivo:
                for chunk in iter(lambda: arquivo.read(1024 * 1024), b""):
                    conn.send(chunk)
        else:
            data = body if body is not None else b""
            if isinstance(data, str):
                data = data.encode("utf-8")
            headers["Content-Length"] = str(len(data))
            conn.request(method, path, body=data, headers=headers)
        response = conn.getresponse()
        response_body = response.read(1000)
        return {
            "ok": 200 <= response.status < 300,
            "status": response.status,
            "body": response_body.decode("utf-8", errors="replace")[:1000],
        }
    except Exception as exc:
        return {"ok": False, "erro": str(exc)[:1000]}
    finally:
        conn.close()


def _upload_backup_webdav(backup_config, arquivo_path):
    webdav_url = backup_config.get("webdav_url") or ""
    if not webdav_url:
        return {"ok": False, "erro": "URL WebDAV não configurada."}
    ok_url, erro_url = validar_url_webdav_segura(webdav_url)
    if not ok_url:
        return {"ok": False, "erro": erro_url}
    webdav_username = backup_config.get("webdav_username") or ""
    webdav_password = backup_config.get("webdav_password") or ""
    if webdav_username and not webdav_password:
        return {"ok": False, "erro": "Senha WebDAV ausente no ambiente."}

    base_url = webdav_url.rstrip("/") + "/"
    file_name = urllib.parse.quote(Path(arquivo_path).name)
    upload_url = urllib.parse.urljoin(base_url, file_name)
    resultado = _webdav_request(
        backup_config,
        "PUT",
        upload_url,
        arquivo_path=arquivo_path,
        content_type="application/zip",
        timeout=300,
    )
    if resultado.get("ok"):
        return {"ok": True, "url": upload_url, "status": resultado.get("status")}
    if resultado.get("status"):
        return {"ok": False, "erro": f"WebDAV retornou status {resultado.get('status')}.", **resultado}
    return resultado


def criar_solicitacao_backup_painel(site, usuario, escopo):
    escopo = normalizar_escopo_backup(escopo)
    return BackupExecucao.objects.create(
        site=site,
        tipo=BackupExecucao.TIPO_PAINEL,
        status=BackupExecucao.STATUS_PENDENTE,
        formato_db=BackupExecucao.FORMATO_JSON,
        inclui_midia=escopo_inclui_midia(escopo),
        solicitado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
        detalhes={
            "escopo": escopo,
            "escopo_label": label_escopo_backup(escopo),
            "solicitado_via": "painel",
        },
    )


def executar_backup_site(
    site,
    solicitado_por=None,
    tipo=BackupExecucao.TIPO_MANUAL,
    incluir_midia=True,
    escopo=BACKUP_SCOPE_TOTAL,
    execucao=None,
):
    config = ConfiguracaoSite.for_site(site)
    backup_config = _backup_backend_config(config=config)
    now = timezone.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    escopo = normalizar_escopo_backup(escopo)
    nome_base = f"{site.hostname}_{escopo}_{timestamp}"
    backups_dir = _diretorio_backups()

    if execucao is None:
        execucao = BackupExecucao.objects.create(
            site=site,
            tipo=tipo,
            status=BackupExecucao.STATUS_EM_EXECUCAO,
            inclui_midia=bool(incluir_midia),
            solicitado_por=solicitado_por if getattr(solicitado_por, "is_authenticated", False) else None,
            detalhes={"escopo": escopo, "escopo_label": label_escopo_backup(escopo)},
        )
    else:
        execucao.status = BackupExecucao.STATUS_EM_EXECUCAO
        execucao.tipo = tipo or execucao.tipo
        execucao.inclui_midia = bool(incluir_midia)
        if solicitado_por is not None and getattr(solicitado_por, "is_authenticated", False):
            execucao.solicitado_por = solicitado_por
        detalhes_execucao = dict(execucao.detalhes or {})
        detalhes_execucao.update({"escopo": escopo, "escopo_label": label_escopo_backup(escopo)})
        execucao.detalhes = detalhes_execucao
        execucao.erro = ""
        execucao.save(update_fields=["status", "tipo", "inclui_midia", "solicitado_por", "detalhes", "erro"])

    temp_dir = Path(tempfile.mkdtemp(prefix="backup_", dir=str(backups_dir)))
    detalhes = dict(execucao.detalhes or {})
    detalhes.update({"arquivos": [], "escopo": escopo, "escopo_label": label_escopo_backup(escopo)})
    try:
        db_dump_path = None
        if escopo == BACKUP_SCOPE_TOTAL:
            db_dump_path, erro_pg = _dump_banco_pg_dump(temp_dir, nome_base)
            if db_dump_path:
                execucao.formato_db = BackupExecucao.FORMATO_PGDUMP
                detalhes["arquivos"].append(db_dump_path.name)
            else:
                db_dump_path = _dump_banco_json(temp_dir, nome_base)
                execucao.formato_db = BackupExecucao.FORMATO_JSON
                detalhes["pg_dump_erro"] = erro_pg
                detalhes["arquivos"].append(db_dump_path.name)
        elif escopo != BACKUP_SCOPE_MIDIAS:
            labels = _BACKUP_SCOPE_LABELS.get(escopo, [])
            db_dump_path = _dump_modelos_json(temp_dir, nome_base, labels)
            execucao.formato_db = BackupExecucao.FORMATO_JSON
            detalhes["modelos"] = labels
            detalhes["arquivos"].append(db_dump_path.name)
        else:
            execucao.formato_db = BackupExecucao.FORMATO_JSON
            detalhes["sem_dump_banco"] = True

        media_path = None
        private_media_path = None
        if incluir_midia and backup_config["include_media"]:
            media_path = _compactar_diretorio(
                temp_dir,
                nome_base,
                settings.MEDIA_ROOT,
                "media",
                "media",
            )
            if media_path:
                detalhes["arquivos"].append(media_path.name)
        if incluir_midia and backup_config["include_private_media"]:
            private_root = Path(settings.BASE_DIR) / "private_media"
            private_media_path = _compactar_diretorio(
                temp_dir,
                nome_base,
                private_root,
                "private_media",
                "private_media",
            )
            if private_media_path:
                detalhes["arquivos"].append(private_media_path.name)

        manifest = {
            "site_id": site.id,
            "site_hostname": site.hostname,
            "gerado_em": now.isoformat(),
            "escopo": escopo,
            "escopo_label": label_escopo_backup(escopo),
            "formato_db": execucao.formato_db,
            "inclui_midia": bool(media_path),
            "inclui_midia_privada": bool(private_media_path),
            "backup_backend": {
                "external_backend": backup_config["external_backend"],
                "retention_days": backup_config["retention_days"],
                "interval_hours": backup_config["interval_hours"],
                "include_media": backup_config["include_media"],
                "include_private_media": backup_config["include_private_media"],
            },
            "arquivos": detalhes["arquivos"],
        }
        manifest_path = temp_dir / f"{nome_base}.manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        final_path = backups_dir / f"{nome_base}.zip"
        with zipfile.ZipFile(final_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(manifest_path, arcname=manifest_path.name)
            if db_dump_path:
                zf.write(db_dump_path, arcname=db_dump_path.name)
            if media_path:
                zf.write(media_path, arcname=media_path.name)
            if private_media_path:
                zf.write(private_media_path, arcname=private_media_path.name)

        execucao.arquivo_caminho = str(final_path)
        execucao.arquivo_tamanho_bytes = final_path.stat().st_size
        execucao.checksum_sha256 = _sha256_arquivo(final_path)
        resultado_restore = simular_restore_backup(str(final_path), execucao.checksum_sha256)
        detalhes["restore_dry_run"] = resultado_restore
        if not resultado_restore.get("ok"):
            execucao.detalhes = detalhes
            execucao.status = BackupExecucao.STATUS_FALHOU
            execucao.erro = f"Backup criado, mas falhou no dry-run de restore: {resultado_restore.get('erro', '')}"[:10000]
            execucao.concluido_em = timezone.now()
            execucao.save(
                update_fields=[
                    "arquivo_caminho",
                    "arquivo_tamanho_bytes",
                    "checksum_sha256",
                    "detalhes",
                    "status",
                    "erro",
                    "concluido_em",
                    "formato_db",
                ]
            )
            _enviar_relatorio_email(config, execucao)
            return execucao
        execucao.detalhes = detalhes
        execucao.status = BackupExecucao.STATUS_CONCLUIDO
        execucao.concluido_em = timezone.now()
        execucao.save(
            update_fields=[
                "arquivo_caminho",
                "arquivo_tamanho_bytes",
                "checksum_sha256",
                "detalhes",
                "status",
                "concluido_em",
                "formato_db",
            ]
        )
        _aplicar_retencao(backups_dir, backup_config["retention_days"])
        if backup_config["external_backend"] == "webdav":
            resultado_webdav = _upload_backup_webdav(backup_config, final_path)
            detalhes["webdav"] = resultado_webdav
            execucao.detalhes = detalhes
            if not resultado_webdav.get("ok"):
                execucao.erro = f"Backup local concluído, mas envio WebDAV falhou: {resultado_webdav.get('erro', '')}"[:10000]
                execucao.status = BackupExecucao.STATUS_FALHOU
                execucao.save(update_fields=["detalhes", "erro", "status"])
                _enviar_relatorio_email(config, execucao)
                return execucao
            execucao.save(update_fields=["detalhes", "erro"])
        _enviar_relatorio_email(config, execucao)
        config.backup_ultimo_envio_em = timezone.now()
        config.save(update_fields=["backup_ultimo_envio_em"])
        return execucao
    except Exception as exc:
        execucao.status = BackupExecucao.STATUS_FALHOU
        execucao.erro = str(exc)[:10000]
        execucao.detalhes = detalhes
        execucao.concluido_em = timezone.now()
        execucao.save(
            update_fields=["status", "erro", "detalhes", "concluido_em", "formato_db"]
        )
        try:
            _enviar_relatorio_email(config, execucao)
        except Exception:
            pass
        return execucao
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def backup_agendado_pendente(site):
    backup_config = _backup_backend_config()
    if not backup_config["enabled"]:
        return False
    config = ConfiguracaoSite.for_site(site)
    ultimo = config.backup_ultimo_envio_em
    if not ultimo:
        return True
    proximo = ultimo + timedelta(hours=backup_config["interval_hours"])
    return timezone.now() >= proximo


def simular_restore_backup(arquivo_path, checksum_esperado=""):
    caminho = Path(arquivo_path)
    if not caminho.exists():
        return {"ok": False, "erro": "Arquivo não encontrado."}
    if not zipfile.is_zipfile(caminho):
        return {"ok": False, "erro": "Arquivo não é um ZIP válido."}

    if checksum_esperado:
        checksum_calculado = _sha256_arquivo(caminho)
        if checksum_calculado.lower() != checksum_esperado.strip().lower():
            return {
                "ok": False,
                "erro": "Checksum inválido.",
                "checksum_calculado": checksum_calculado,
            }

    with zipfile.ZipFile(caminho, "r") as zf:
        nomes = zf.namelist()
        inseguros = [n for n in nomes if not _caminho_zip_seguro(n)]
        if inseguros:
            return {
                "ok": False,
                "erro": "Backup ZIP contém caminho inseguro.",
            }
        manifestos = [n for n in nomes if n.endswith(".manifest.json")]
        if not manifestos:
            return {"ok": False, "erro": "Manifesto não encontrado no backup."}

        manifesto = json.loads(zf.read(manifestos[0]).decode("utf-8"))
        arquivos_manifesto = manifesto.get("arquivos", [])
        faltantes = [n for n in arquivos_manifesto if n not in nomes]
        if faltantes:
            return {
                "ok": False,
                "erro": f"Arquivos faltando no backup: {', '.join(faltantes)}",
            }

        escopo = normalizar_escopo_backup(manifesto.get("escopo"))
        db_arquivo = next((n for n in arquivos_manifesto if ".db." in n), "")
        if not db_arquivo and escopo != BACKUP_SCOPE_MIDIAS:
            return {"ok": False, "erro": "Arquivo de banco não identificado no backup."}

        if db_arquivo and db_arquivo.endswith(".json"):
            try:
                json.loads(zf.read(db_arquivo).decode("utf-8"))
            except Exception as exc:
                return {"ok": False, "erro": f"JSON do banco inválido: {exc}"}

        media_arquivos = [n for n in arquivos_manifesto if n.endswith(".tar.gz")]
        for media_arquivo in media_arquivos:
            with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=True) as tmp_media:
                tmp_media.write(zf.read(media_arquivo))
                tmp_media.flush()
                with tarfile.open(tmp_media.name, "r:gz") as tar:
                    membros = tar.getmembers()
                    for membro in membros:
                        nome_membro = (membro.name or "").strip()
                        if not nome_membro:
                            return {"ok": False, "erro": "Arquivo de mídia contém entrada inválida."}
                        caminho_membro = Path(nome_membro)
                        if caminho_membro.is_absolute() or ".." in caminho_membro.parts:
                            return {"ok": False, "erro": "Arquivo de mídia contém caminho inseguro."}

    return {
        "ok": True,
        "manifesto": manifesto,
        "arquivo": str(caminho),
    }


def preparar_restore_backup(arquivo_path, destino_dir, checksum_esperado=""):
    resultado = simular_restore_backup(
        arquivo_path=arquivo_path,
        checksum_esperado=checksum_esperado,
    )
    if not resultado.get("ok"):
        return resultado

    caminho = Path(arquivo_path)
    destino = Path(destino_dir)
    destino.mkdir(parents=True, exist_ok=True)
    destino_resolvido = destino.resolve()

    with zipfile.ZipFile(caminho, "r") as zf:
        for info in zf.infolist():
            if not _caminho_zip_seguro(info.filename):
                return {"ok": False, "erro": "Backup ZIP contém caminho inseguro."}
            caminho_destino = (destino / info.filename).resolve()
            if destino_resolvido not in [caminho_destino, *caminho_destino.parents]:
                return {"ok": False, "erro": "Backup ZIP contém caminho fora do destino."}
            zf.extract(info, destino)

    manifesto = resultado.get("manifesto") or {}
    arquivos = manifesto.get("arquivos") or []
    db_arquivo = next((n for n in arquivos if ".db." in n), "")
    media_arquivo = next((n for n in arquivos if ".media.tar.gz" in n), "")
    return {
        "ok": True,
        "destino": str(destino),
        "manifesto": manifesto,
        "db_arquivo": str(destino / db_arquivo) if db_arquivo else "",
        "media_arquivo": str(destino / media_arquivo) if media_arquivo else "",
    }
