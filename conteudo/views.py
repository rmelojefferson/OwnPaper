import json
import hashlib
import os
import urllib.parse
import urllib.request
import urllib.error
import csv
import io
import base64
import logging
import time
import binascii
import uuid
from decimal import Decimal, InvalidOperation
from datetime import timedelta, datetime, timezone as datetime_timezone
from pathlib import Path

import re
import qrcode
import secrets
import socket
import struct
import tempfile

from wagtail.rich_text import expand_db_html
from wagtail.admin.viewsets.pages import page_viewset_registry
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from io import TextIOWrapper, BytesIO
from pypdf import PdfReader, PdfWriter
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import transaction
from django.core.files.base import ContentFile
from wagtail.models import GroupPagePermission, Site
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.db.models import F
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.utils.html import escape, strip_tags
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt

from .analytics import ip_da_requisicao, requisicao_ignorada_para_estatisticas
from .roles import (
    AUTHOR_GROUP_NAME,
)
from .user_roles import (
    aplicar_papeis_por_convite,
    garantir_permissoes_editoriais_grupo_autor as _garantir_permissoes_editoriais_grupo_autor,
    gerar_slug_autor_unico as _gerar_slug_autor_unico,
    vincular_autor_para_usuario as _vincular_autor_para_usuario,
)
from home.models import HomePage
from .models import (
    AvaliacaoPublicacao,
    Autor,
    Categoria,
    ComentarioPublicacao,
    ComentarioAcessoCodigo,
    ComentarioVerificacaoToken,
    ConfiguracaoSite,
    ConviteUsuario,
    ContatoPage,
    coletar_linhas_privacidade_por_email,
    DuvidaQuizPublicacao,
    EstatisticaDiariaSite,
    EstatisticaTempoSite,
    IpDinamicoIgnoradoEstatisticas,
    IdentidadeExternaComentario,
    InscritoNewsletter,
    MensagemContato,
    NewsletterEvento,
    NewsletterPage,
    IndexadorPage,
    PaginaInstitucionalPage,
    PerguntaQuizCatalogo,
    PublicacaoPerguntaQuizCatalogo,
    QuizAcessoCodigo,
    QuizRespostaUsuario,
    QuizEstudoPage,
    QuizSessaoUsuario,
    RegistroIndexador,
    RegistroIndexadorAutor,
    normalizar_codigo_idioma_manual,
    normalizar_marcador_publicacao,
    normalizar_username_publico,
    PublicacaoPage,
    PublicacoesIndexPage,
    UsuarioComentario,
    UsuarioPainelPerfil,
    DisparoEmailClique,
    DisparoEmailDestino,
    SolicitacaoPrivacidadeNewsletter,
    TagPublicacao,
    SubmissaoPublica,
    submissao_publica_upload_to,
)
from .oauth_service import (
    oauth_build_authorize_url,
    oauth_exchange_code,
    oauth_fetch_profile,
    oauth_provider_enabled,
    oauth_provider_enabled_map,
    oauth_provider_label,
)
from .audit import registrar_auditoria

forms_security_logger = logging.getLogger("conteudo.forms_security")
PIXEL_GIF_1X1 = binascii.a2b_base64("R0lGODlhAQABAPAAAAAAAAAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==")
_TEXTO_TOKENS_BLOQUEADOS = (
    "<",
    ">",
    "`",
    "${",
    "$(",
    "&&",
    "||",
    "/*",
    "*/",
    ";--",
)


def _ip_da_requisicao_view(request):
    return ip_da_requisicao(request)


def admin_aceite_termos_painel_view(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        next_url = urllib.parse.quote(request.get_full_path(), safe="/?=&")
        return redirect(f"/account/login/?next={next_url}")

    perfil, _ = UsuarioPainelPerfil.objects.get_or_create(usuario=request.user)
    versao_atual = getattr(settings, "OWNPAPER_PANEL_TERMS_VERSION", "2026-06-02")
    next_url = request.POST.get("next") or request.GET.get("next") or "/admin/"
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = "/admin/"

    if perfil.aceitou_termos_painel_atuais():
        return redirect(next_url)

    if request.method == "POST":
        if request.POST.get("aceitou_termos_painel") != "1":
            messages.error(request, "Você precisa aceitar os termos para acessar o painel.")
        else:
            perfil.termos_painel_versao = versao_atual
            perfil.aceitou_termos_painel_em = timezone.now()
            perfil.aceitou_termos_painel_ip = _ip_da_requisicao_view(request)[:64]
            perfil.aceitou_termos_painel_user_agent = (
                request.META.get("HTTP_USER_AGENT", "") or ""
            )[:255]
            perfil.save(update_fields=[
                "termos_painel_versao",
                "aceitou_termos_painel_em",
                "aceitou_termos_painel_ip",
                "aceitou_termos_painel_user_agent",
                "atualizado_em",
            ])
            registrar_auditoria(
                request=request,
                acao="painel_termos_aceitos",
                alvo=perfil,
                detalhes=f"Usuário aceitou os termos do painel. Versão: {versao_atual}.",
            )
            messages.success(request, "Termos do painel aceitos.")
            return redirect(next_url)

    return render(
        request,
        "conteudo/admin_aceite_termos_painel.html",
        {
            "next_url": next_url,
            "versao_termos": versao_atual,
        },
    )


def admin_sites_redirect_view(request, subpath=None):
    if not (request.user.is_authenticated and request.user.is_staff):
        next_url = urllib.parse.quote(request.get_full_path(), safe="/?=&")
        return redirect(f"/account/login/?next={next_url}")

    messages.info(
        request,
        "Esta instalação usa um único site por projeto. A gestão de Sites foi ocultada no painel.",
    )
    return redirect("admin_configuracoes_site")


def admin_pages_redirect_view(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        next_url = urllib.parse.quote(request.get_full_path(), safe="/?=&")
        return redirect(f"/account/login/?next={next_url}")

    site = (
        Site.find_for_request(request)
        or Site.objects.filter(is_default_site=True).first()
        or Site.objects.first()
    )
    if site is None or site.root_page_id is None:
        messages.error(request, "Site não encontrado.")
        return redirect("/admin/")

    return redirect("wagtailadmin_explore", site.root_page_id)


def admin_publicacoes_index_redirect_view(request, page_id):
    if not (request.user.is_authenticated and request.user.is_staff):
        next_url = urllib.parse.quote(request.get_full_path(), safe="/?=&")
        return redirect(f"/account/login/?next={next_url}")

    if PublicacoesIndexPage.objects.filter(pk=page_id).exists():
        return redirect("admin_publicacoes_lista")

    wagtail_explorer_view = page_viewset_registry.as_view(
        "index",
        parent_page_id_kwarg="parent_page_id",
    )
    return wagtail_explorer_view(request, parent_page_id=page_id)


def sanitizar_texto(valor, multiline=False):
    valor = strip_tags((valor or "").strip())
    valor = valor.replace("\r\n", "\n").replace("\r", "\n")
    for token in _TEXTO_TOKENS_BLOQUEADOS:
        valor = valor.replace(token, " ")
    valor = "".join(ch for ch in valor if ch.isprintable() or ch == "\n")
    if multiline:
        valor = re.sub(r"[ \t]+\n", "\n", valor)
        valor = re.sub(r"\n{3,}", "\n\n", valor)
    else:
        valor = re.sub(r"\s+", " ", valor)
    return valor


def _split_nome_partes(nome_completo):
    texto = sanitizar_texto(nome_completo or "")
    if not texto:
        return "", ""
    partes = [parte for parte in texto.split(" ") if parte]
    if len(partes) == 1:
        return partes[0], ""
    return partes[0], " ".join(partes[1:])


def _montar_nome_completo(nome, sobrenome):
    primeiro = sanitizar_texto(nome or "")
    ultimo = sanitizar_texto(sobrenome or "")
    return " ".join([parte for parte in [primeiro, ultimo] if parte]).strip()


def _payload_username_disponivel(valor):
    bruto = sanitizar_texto(valor or "")
    normalizado = normalizar_username_publico(bruto)
    if not normalizado:
        return {
            "ok": True,
            "normalized": "",
            "available": False,
            "message": "Informe um nome de usuário válido.",
        }
    em_uso = _usuario_por_username_normalizado(normalizado) is not None
    return {
        "ok": True,
        "normalized": normalizado,
        "available": not em_uso,
        "message": (
            "Nome de usuário disponível."
            if not em_uso
            else "Este nome de usuário já está em uso."
        ),
    }


def arquivo_verificacao_site(request, filename):
    nome = sanitizar_texto(filename or "", multiline=False).strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.(?:html|txt)", nome):
        raise Http404

    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first()
    config_site = ConfiguracaoSite.for_site(site) if site else None
    if not config_site:
        raise Http404

    nome_configurado = (config_site.verificacao_arquivo_nome or "").strip()
    conteudo = config_site.verificacao_arquivo_conteudo or ""
    if not nome_configurado or not conteudo or nome != nome_configurado:
        raise Http404

    content_type = "text/html; charset=utf-8" if nome.endswith(".html") else "text/plain; charset=utf-8"
    return HttpResponse(conteudo, content_type=content_type)


def username_disponivel(request):
    return JsonResponse(_payload_username_disponivel(request.GET.get("username") or ""))


@csrf_exempt
def estatistica_tempo_site(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método inválido."}, status=405)
    if request.COOKIES.get("ownpaper_cookie_consent") != "all":
        return HttpResponse(status=204)
    if requisicao_ignorada_para_estatisticas(request):
        return HttpResponse(status=204)

    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    config_site = ConfiguracaoSite.for_site(site) if site else None
    if config_site and not config_site.estatisticas_internas_ativas:
        return HttpResponse(status=204)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "payload"}, status=400)

    session_id = sanitizar_texto(str(payload.get("session_id") or ""))[:80]
    started_at_raw = sanitizar_texto(str(payload.get("started_at") or ""))[:40]
    path = urllib.parse.urlsplit(str(payload.get("path") or "/")).path or "/"
    path = sanitizar_texto(path)[:500]
    try:
        duration = int(payload.get("duration_seconds") or 0)
    except (TypeError, ValueError):
        duration = 0
    duration = max(0, min(duration, 7200))

    if not session_id or not started_at_raw or not path.startswith("/"):
        return JsonResponse({"ok": False, "error": "payload"}, status=400)

    try:
        started_at = datetime.fromisoformat(started_at_raw.replace("Z", "+00:00"))
    except ValueError:
        return JsonResponse({"ok": False, "error": "started_at"}, status=400)
    if timezone.is_naive(started_at):
        started_at = timezone.make_aware(started_at, datetime_timezone.utc)
    started_at = started_at.astimezone(datetime_timezone.utc).replace(microsecond=0)
    agora = timezone.now()
    if started_at > agora + timedelta(minutes=5) or started_at < agora - timedelta(days=1):
        return JsonResponse({"ok": False, "error": "started_at"}, status=400)

    session_hash = hashlib.sha256(
        f"{settings.SECRET_KEY}:{session_id}".encode("utf-8")
    ).hexdigest()
    EstatisticaTempoSite.objects.update_or_create(
        session_hash=session_hash,
        path=path,
        started_at=started_at,
        defaults={
            "last_seen_at": agora,
            "duration_seconds": duration,
        },
    )
    data_evento = timezone.localtime(started_at).date()
    eventos_do_dia = EstatisticaTempoSite.objects.filter(
        path=path,
        started_at__date=data_evento,
        duration_seconds__gte=5,
    )
    agregado = eventos_do_dia.aggregate(
        sessoes=Count("id"),
        tempo_total=Sum("duration_seconds"),
        tempo_medio=Avg("duration_seconds"),
    )
    sessoes = agregado["sessoes"] or 0
    tempo_total = agregado["tempo_total"] or 0
    tempo_medio = int(agregado["tempo_medio"] or 0)
    EstatisticaDiariaSite.objects.update_or_create(
        data=data_evento,
        path=path,
        defaults={
            "sessoes": sessoes,
            "tempo_total_seconds": tempo_total,
            "tempo_medio_seconds": tempo_medio,
        },
    )
    return HttpResponse(status=204)


@csrf_exempt
def registrar_ip_ignorado_estatisticas(request):
    if request.method not in {"GET", "POST"}:
        return JsonResponse({"ok": False, "error": "Método inválido."}, status=405)

    token_configurado = getattr(settings, "OWNPAPER_ANALYTICS_DYNAMIC_EXCLUDE_TOKEN", "")
    token_recebido = request.POST.get("token") or request.GET.get("token") or ""
    if not token_configurado or not secrets.compare_digest(token_configurado, token_recebido):
        return JsonResponse({"ok": False, "error": "Não autorizado."}, status=403)

    ip = ip_da_requisicao(request)
    try:
        socket.inet_pton(socket.AF_INET, ip)
    except OSError:
        try:
            socket.inet_pton(socket.AF_INET6, ip)
        except OSError:
            return JsonResponse({"ok": False, "error": "IP inválido."}, status=400)

    nome_raw = request.POST.get("nome") or request.GET.get("nome") or "rede-local"
    nome = slugify(str(nome_raw))[:80] or "rede-local"
    ttl_horas = max(1, int(getattr(settings, "OWNPAPER_ANALYTICS_DYNAMIC_EXCLUDE_TTL_HOURS", 72)))
    expira_em = timezone.now() + timedelta(hours=ttl_horas)
    registro, criado = IpDinamicoIgnoradoEstatisticas.objects.update_or_create(
        nome=nome,
        defaults={
            "ip": ip,
            "expira_em": expira_em,
        },
    )

    return JsonResponse(
        {
            "ok": True,
            "created": criado,
            "nome": registro.nome,
            "ip": registro.ip,
            "expira_em": registro.expira_em.isoformat(),
        }
    )


def _gerar_codigo_6():
    return f"{secrets.randbelow(1000000):06d}"


def _mascarar_email(email):
    valor = sanitizar_texto(email or "", multiline=False).strip()
    if "@" not in valor:
        return valor
    local, dominio = valor.split("@", 1)
    if len(local) <= 2:
        local_mascarado = f"{local[:1]}***"
    else:
        local_mascarado = f"{local[:2]}***{local[-1]}"
    return f"{local_mascarado}@{dominio}"


def _usuario_por_username_normalizado(username, usuario_atual=None):
    normalizado = normalizar_username_publico(username or "")
    if not normalizado:
        return None
    for usuario in UsuarioComentario.objects.only("id", "username", "email"):
        if usuario_atual and usuario.id == getattr(usuario_atual, "id", None):
            continue
        if normalizar_username_publico(usuario.username) == normalizado:
            return usuario
    return None


def _resolver_conflitos_usuario_comentario(email="", username="", orcid="", usuario_atual=None):
    email_norm = sanitizar_texto(email or "", multiline=False).strip().lower()
    username_norm = normalizar_username_publico(username or "")
    orcid_norm = sanitizar_texto(orcid or "", multiline=False).strip()

    usuario_email = (
        UsuarioComentario.objects.filter(email__iexact=email_norm).first()
        if email_norm else None
    )
    if usuario_atual and usuario_email and usuario_email.id == usuario_atual.id:
        usuario_email = usuario_atual

    usuario_username = _usuario_por_username_normalizado(username_norm, usuario_atual=usuario_atual)
    usuario_orcid = (
        UsuarioComentario.objects.filter(orcid__iexact=orcid_norm).first()
        if orcid_norm else None
    )
    if usuario_atual and usuario_orcid and usuario_orcid.id == usuario_atual.id:
        usuario_orcid = usuario_atual

    ids_encontrados = {
        usuario.id
        for usuario in (usuario_email, usuario_username, usuario_orcid)
        if usuario is not None
    }
    if len(ids_encontrados) > 1:
        return "erro_identidade_conflito", usuario_email, usuario_username, usuario_orcid

    if usuario_atual is not None:
        for usuario in (usuario_email, usuario_username, usuario_orcid):
            if usuario and usuario.id != usuario_atual.id:
                return "erro_identidade_conflito", usuario_email, usuario_username, usuario_orcid
        return "", usuario_email, usuario_username, usuario_orcid

    if usuario_email and username_norm:
        if normalizar_username_publico(usuario_email.username) != username_norm:
            return "erro_usuario_email", usuario_email, usuario_username, usuario_orcid

    if not usuario_email and usuario_username and email_norm:
        if (usuario_username.email or "").strip().lower() != email_norm:
            return "erro_usuario_duplicado", usuario_email, usuario_username, usuario_orcid

    if usuario_orcid:
        usuario_base = usuario_email or usuario_username
        if usuario_base and usuario_orcid.id != usuario_base.id:
            return "erro_identidade_conflito", usuario_email, usuario_username, usuario_orcid
        if not usuario_base:
            return "erro_orcid_duplicado", usuario_email, usuario_username, usuario_orcid

    return "", usuario_email, usuario_username, usuario_orcid


def _acesso_identidade_publicacao_habilitado(publicacao, config_site):
    if not config_site or not getattr(config_site, "comentarios_ativos", False):
        return False
    return bool(publicacao.comentarios_habilitados or publicacao.possui_quiz_publico)


def _obter_configuracao_site_request(request):
    site = getattr(request, "site", None)
    if site is None:
        try:
            site = Site.find_for_request(request)
        except Exception:
            site = None
    if not site:
        return None
    try:
        return ConfiguracaoSite.for_site(site)
    except Exception:
        return None


def _normalizar_idiomas_busca(valores):
    if isinstance(valores, str):
        valores = [valores]
    idiomas = []
    for valor in valores or []:
        normalizado = normalizar_codigo_idioma_manual(valor)
        if normalizado and normalizado not in idiomas:
            idiomas.append(normalizado)
    if not idiomas:
        idiomas = ["pt-br"]
    return idiomas, list(idiomas)


def _construir_filtro_indexador(termos_variantes):
    if not termos_variantes:
        return Q()
    filtro = Q()
    for termo in termos_variantes:
        valor = sanitizar_texto(termo or "", multiline=False)
        if not valor:
            continue
        filtro |= (
            Q(titulo__icontains=valor)
            | Q(resumo__icontains=valor)
            | Q(dados_editoriais__icontains=valor)
            | Q(palavras_chave__icontains=valor)
            | Q(doi__icontains=valor)
            | Q(autores_registro__nome__icontains=valor)
            | Q(autores_registro__orcid__icontains=valor)
        )
    return filtro


def _construir_filtro_publicacoes(termos_variantes, idiomas_busca_efetivos=None):
    if not termos_variantes:
        return Q()
    filtro = Q()
    for termo in termos_variantes:
        valor = sanitizar_texto(termo or "", multiline=False)
        if not valor:
            continue
        filtro |= (
            Q(title__icontains=valor)
            | Q(resumo__icontains=valor)
            | Q(search_description__icontains=valor)
            | Q(palavras_chave__icontains=valor)
            | Q(corpo__icontains=valor)
            | Q(categoria_principal__nome__icontains=valor)
            | Q(autores_publicacao__autor__nome_completo__icontains=valor)
            | Q(autores_publicacao__autor__orcid__icontains=valor)
            | Q(tags__name__icontains=valor)
        )
    return filtro


def _extrair_termos_busca_avancada(request):
    termos = []
    for indice in range(1, 6):
        termo = sanitizar_texto(request.GET.get(f"termo_{indice}", ""), multiline=False)
        operador = sanitizar_texto(
            request.GET.get(f"operador_{indice}", "and"),
            multiline=False,
        ).strip().lower()
        if operador not in {"and", "or"}:
            operador = "and"
        termos.append({
            "indice": indice,
            "termo": termo,
            "operador": operador,
        })
    return termos


def _deduplicar_termos_busca(termos):
    normalizados = {}
    ordem = []
    for termo in termos or []:
        valor = sanitizar_texto(termo or "", multiline=False)
        if not valor:
            continue
        chave = valor.casefold()
        if chave not in normalizados:
            normalizados[chave] = valor
            ordem.append(chave)
            continue
        atual = normalizados[chave]
        if atual != atual.lower() and valor == valor.lower():
            normalizados[chave] = valor
    return [normalizados[chave] for chave in ordem]


def _combinar_filtros_busca(
    termos_configurados,
    idioma_atual,
    idiomas_efetivos,
    builder,
    modo_expansao=None,
):
    filtro_final = None
    houve_termos = False
    for item in termos_configurados:
        termo = item.get("termo", "")
        if not termo:
            continue
        variantes = [sanitizar_texto(termo, multiline=False)]
        filtro_termo = builder(variantes)
        if filtro_final is None:
            filtro_final = filtro_termo
        elif item.get("operador") == "or":
            filtro_final |= filtro_termo
        else:
            filtro_final &= filtro_termo
        houve_termos = True
    return filtro_final if houve_termos else None


def _cookie_secure(request):
    return bool(request.is_secure() or getattr(settings, "SESSION_COOKIE_SECURE", False))


def _usuario_comentario_cookie(request):
    cookie_auth = (request.COOKIES.get("ownpaper_comment_auth") or "").strip()
    if not cookie_auth:
        return None
    try:
        payload = signing.loads(
            cookie_auth,
            salt="ownpaper_comment_auth",
            max_age=60 * 60 * 24 * 30,
        )
        user_id = int((payload or {}).get("uid"))
    except Exception:
        return None
    return UsuarioComentario.objects.filter(id=user_id).first()


def _definir_cookie_usuario_comentario(response, request, usuario):
    token = signing.dumps({"uid": usuario.id}, salt="ownpaper_comment_auth")
    response.set_cookie(
        "ownpaper_comment_auth",
        token,
        max_age=60 * 60 * 24 * 30,
        secure=_cookie_secure(request),
        httponly=True,
        samesite="Lax",
        path="/",
    )
    return response


def _registrar_newsletter_comentario(config_site, email):
    email_norm = sanitizar_texto(email or "", multiline=False).strip().lower()
    if not email_norm or not config_site or not getattr(config_site, "comentarios_auto_newsletter", False):
        return None
    try:
        validate_email(email_norm)
    except ValidationError:
        return None

    inscrito, criado = InscritoNewsletter.objects.get_or_create(
        email=email_norm,
        defaults={
            "ativo": True,
            "consentimento": True,
            "origem": "comentarios",
            "confirmado_em": timezone.now(),
        },
    )
    if criado:
        NewsletterEvento.objects.create(
            inscrito=inscrito,
            email=inscrito.email,
            tipo=NewsletterEvento.TIPO_INSCRICAO_CONFIRMADA,
            origem="comentarios",
            detalhes="Inscrição automática após autenticação/comentário.",
        )
        return inscrito

    updates = []
    if not inscrito.ativo:
        inscrito.ativo = True
        updates.append("ativo")
    if not inscrito.consentimento:
        inscrito.consentimento = True
        updates.append("consentimento")
    if not inscrito.confirmado_em:
        inscrito.confirmado_em = timezone.now()
        updates.append("confirmado_em")
    if not inscrito.origem:
        inscrito.origem = "comentarios"
        updates.append("origem")
    if updates:
        inscrito.save(update_fields=updates + ["atualizado_em"])
    return inscrito


def _texto_suspeito_para_moderacao(texto):
    valor = sanitizar_texto(texto or "", multiline=True)
    if not valor:
        return False
    suspeitos = (
        "http://",
        "https://",
        "www.",
        "[url",
        "href=",
        "telegram.me/",
        "wa.me/",
    )
    valor_lower = valor.lower()
    return any(token in valor_lower for token in suspeitos)


def _texto_publico_contem_risco(texto):
    valor = sanitizar_texto(texto or "", multiline=True)
    if not valor:
        return False
    valor_lower = valor.lower()
    tokens = (
        "<script",
        "javascript:",
        "data:text/html",
        "onerror=",
        "onload=",
        "base64,",
        "union select",
        "../",
        "${",
        "$(",
    )
    return any(token in valor_lower for token in tokens)


PDF_TOKENS_BLOQUEADOS_PUBLICO = [
    b"/JavaScript",
    b"/JS",
    b"/OpenAction",
    b"/AA",
    b"/AcroForm",
    b"/RichMedia",
    b"/Launch",
    b"/EmbeddedFile",
]


def _clamav_publico_ativo():
    return str(os.getenv("OWNPAPER_CLAMAV_ENABLED", "false")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _verificar_clamav_publico_bytes(data):
    if not _clamav_publico_ativo():
        return
    host = os.getenv("OWNPAPER_CLAMAV_HOST", "clamav")
    porta = int(os.getenv("OWNPAPER_CLAMAV_PORT", "3310"))
    timeout = int(os.getenv("OWNPAPER_CLAMAV_TIMEOUT", "30"))
    try:
        with socket.create_connection((host, porta), timeout=timeout) as conexao:
            conexao.settimeout(timeout)
            conexao.sendall(b"zINSTREAM\0")
            stream = io.BytesIO(data)
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                conexao.sendall(struct.pack("!I", len(chunk)))
                conexao.sendall(chunk)
            conexao.sendall(struct.pack("!I", 0))
            resposta = conexao.recv(4096).decode("utf-8", errors="replace").strip("\0\r\n ")
    except Exception as exc:
        raise ValidationError("Antivírus indisponível. Envio bloqueado por segurança.") from exc
    if resposta.endswith(": OK") or resposta == "stream: OK":
        return
    raise ValidationError("Arquivo bloqueado pelo antivírus.")


def _sanitizar_pdf_submissao(uploaded_file, titulo, limite_mb=25):
    limite_bytes = max(1, min(int(limite_mb or 25), 100)) * 1024 * 1024
    tamanho = getattr(uploaded_file, "size", 0) or 0
    if tamanho > limite_bytes:
        raise ValidationError(f"PDF acima do limite de {limite_bytes // 1024 // 1024} MB.")
    nome = (getattr(uploaded_file, "name", "") or "").lower()
    if not nome.endswith(".pdf"):
        raise ValidationError("A submissão aceita apenas arquivo PDF.")
    data = b"".join(uploaded_file.chunks())
    if not data:
        raise ValidationError("Arquivo vazio.")
    if len(data) > limite_bytes:
        raise ValidationError(f"PDF acima do limite de {limite_bytes // 1024 // 1024} MB.")
    _verificar_clamav_publico_bytes(data)
    if not data.startswith(b"%PDF-"):
        raise ValidationError("Documento inválido. Apenas PDF é aceito.")
    for token in PDF_TOKENS_BLOQUEADOS_PUBLICO:
        if token in data:
            raise ValidationError("PDF bloqueado por conter recursos ativos ou anexos.")
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ValidationError("PDF criptografado não é aceito.")
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.add_metadata({"/Producer": "OwnPaper", "/Source": "OwnPaper public submission"})
        saida = io.BytesIO()
        writer.write(saida)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("PDF inválido ou não sanitizável.") from exc
    bytes_sanitizados = saida.getvalue()
    for token in PDF_TOKENS_BLOQUEADOS_PUBLICO:
        if token in bytes_sanitizados:
            raise ValidationError("PDF sanitizado ainda contém recurso bloqueado.")
    return bytes_sanitizados


def _quiz_redirect(page, status):
    return redirect(f"{page.url}?quiz_auth={status}")


def _oauth_redirect_uri(request, route_name, provider):
    return request.build_absolute_uri(reverse(route_name, args=[provider]))


def _resolver_usuario_oauth(profile):
    provider = (profile.get("provider") or "").strip()
    provider_user_id = (profile.get("provider_user_id") or "").strip()
    identidade = None
    if provider and provider_user_id:
        identidade = (
            IdentidadeExternaComentario.objects
            .select_related("usuario")
            .filter(provider=provider, provider_user_id=provider_user_id)
            .first()
        )
    if identidade and identidade.usuario_id:
        return identidade.usuario, identidade

    email = sanitizar_texto(profile.get("email") or "", multiline=False).strip().lower()
    email_verificado = bool(profile.get("email_verified"))
    if email and email_verificado:
        usuario = UsuarioComentario.objects.filter(email__iexact=email).first()
        if usuario:
            return usuario, None

    orcid = sanitizar_texto(profile.get("orcid") or "", multiline=False).strip()
    if orcid:
        usuario = UsuarioComentario.objects.filter(orcid__iexact=orcid).first()
        if usuario:
            return usuario, None

    return None, None


def _salvar_identidade_oauth(usuario, profile):
    identidade, _ = IdentidadeExternaComentario.objects.update_or_create(
        provider=(profile.get("provider") or "").strip(),
        provider_user_id=(profile.get("provider_user_id") or "").strip(),
        defaults={
            "usuario": usuario,
            "provider_username": sanitizar_texto(profile.get("provider_username") or "", multiline=False),
            "nome_exibicao": sanitizar_texto(profile.get("display_name") or "", multiline=False),
            "email_externo": sanitizar_texto(profile.get("email") or "", multiline=False).strip().lower(),
            "email_verificado": bool(profile.get("email_verified")),
            "perfil_url": sanitizar_texto(profile.get("profile_url") or "", multiline=False),
            "avatar_url": sanitizar_texto(profile.get("avatar_url") or "", multiline=False),
            "escopos": sanitizar_texto(profile.get("scopes") or "", multiline=False),
            "payload": profile.get("raw") or {},
        },
    )
    return identidade


def _finalizar_login_oauth(request, publicacao, config_site, usuario, profile):
    _salvar_identidade_oauth(usuario, profile)
    _registrar_newsletter_comentario(config_site, usuario.email)
    request.session.pop("comentario_oauth_pending", None)
    request.session.pop("comentario_oauth_state", None)
    response = render(
        request,
        "conteudo/comentario_oauth_popup.html",
        {
            "status": "ok",
            "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
            "provider_label": oauth_provider_label(profile.get("provider") or "oauth"),
            "publicacao": publicacao,
        },
    )
    return _definir_cookie_usuario_comentario(response, request, usuario)


def _finalizar_login_quiz_oauth(request, page, config_site, usuario, profile):
    _salvar_identidade_oauth(usuario, profile)
    _registrar_newsletter_comentario(config_site, usuario.email)
    request.session.pop("quiz_oauth_pending", None)
    request.session.pop("quiz_oauth_state", None)
    response = render(
        request,
        "conteudo/quiz_oauth_popup.html",
        {
            "status": "ok",
            "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
            "provider_label": oauth_provider_label(profile.get("provider") or "oauth"),
            "page": page,
        },
    )
    return _definir_cookie_usuario_comentario(response, request, usuario)


def _normalizar_data_busca(valor, idioma_site):
    texto = sanitizar_texto(valor or "", multiline=False).strip()
    if not texto:
        return "", ""

    formatos = ["%Y-%m-%d"]
    if (idioma_site or "").strip().lower() == "pt-br":
        formatos = ["%d/%m/%Y"] + formatos
    else:
        formatos = ["%m/%d/%Y"] + formatos

    for formato in formatos:
        try:
            data = datetime.strptime(texto, formato).date()
        except ValueError:
            continue
        exibicao = data.strftime("%d/%m/%Y") if (idioma_site or "").strip().lower() == "pt-br" else data.strftime("%m/%d/%Y")
        return data.isoformat(), exibicao

    return "", texto


def _normalizar_ano_filtro(valor):
    texto = sanitizar_texto(valor or "", multiline=False).strip()
    if not texto:
        return ""
    if re.fullmatch(r"\d{4}", texto):
        return texto
    return ""


def _normalizar_orcid(valor):
    bruto = sanitizar_texto(valor or "", multiline=False).strip()
    if not bruto:
        return ""
    bruto = re.sub(r"^https?://orcid\.org/", "", bruto, flags=re.IGNORECASE).strip()
    compacto = re.sub(r"[^0-9Xx]", "", bruto).upper()
    if not re.fullmatch(r"\d{15}[\dX]", compacto):
        return None

    total = 0
    for digito in compacto[:15]:
        total = (total + int(digito)) * 2
    resto = total % 11
    resultado = (12 - resto) % 11
    verificador = "X" if resultado == 10 else str(resultado)
    if compacto[-1] != verificador:
        return None

    return f"{compacto[0:4]}-{compacto[4:8]}-{compacto[8:12]}-{compacto[12:16]}"


def robots_txt(request):
    linhas = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /django-admin/",
        "Allow: /",
        "",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(linhas), content_type="text/plain")


def categorias_index(request):
    categorias = Categoria.objects.filter(
        aprovacao_status=Categoria.STATUS_APROVADO
    ).order_by("nome")

    return render(
        request,
        "conteudo/categorias_index.html",
        {
            "categorias": categorias,
        },
    )


def validar_turnstile(token, remoteip=None):
    if not settings.TURNSTILE_ENABLED:
        return True

    if not token:
        return False

    data = {
        "secret": settings.TURNSTILE_SECRET_KEY,
        "response": token,
    }

    if remoteip:
        data["remoteip"] = remoteip

    body = urllib.parse.urlencode(data).encode("utf-8")
    request_http = urllib.request.Request(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    with urllib.request.urlopen(request_http, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return bool(payload.get("success"))


def _rate_limit_scope_key(form_name, scope_type, raw_value):
    valor = sanitizar_texto(raw_value or "", multiline=False).strip().lower()
    if not valor:
        valor = "anon"
    valor_hash = hashlib.sha256(valor.encode("utf-8")).hexdigest()[:24]
    return f"ownpaper:form-rate-limit:{form_name}:{scope_type}:{valor_hash}"


def _remaining_block_seconds(cache_key):
    if not cache_key:
        return 0
    registro = cache.get(cache_key) or {}
    bloqueado_ate = registro.get("blocked_until")
    if not bloqueado_ate:
        return 0
    restante = int((bloqueado_ate - timezone.now()).total_seconds())
    if restante <= 0:
        cache.delete(cache_key)
        return 0
    return restante


def _register_failed_attempt(cache_key, max_attempts):
    agora = timezone.now()
    janela = max(60, int(getattr(settings, "FORM_RATE_LIMIT_WINDOW_SECONDS", 600) or 600))
    backoff_base = max(30, int(getattr(settings, "FORM_RATE_LIMIT_BACKOFF_BASE_SECONDS", 120) or 120))
    backoff_max = max(backoff_base, int(getattr(settings, "FORM_RATE_LIMIT_BACKOFF_MAX_SECONDS", 3600) or 3600))

    registro = cache.get(cache_key) or {}
    primeiro_evento = registro.get("first_event_at")
    attempts = int(registro.get("attempts") or 0)

    if not primeiro_evento or (agora - primeiro_evento).total_seconds() > janela:
        attempts = 0
        primeiro_evento = agora

    attempts += 1
    registro = {
        "attempts": attempts,
        "first_event_at": primeiro_evento,
    }

    backoff_seconds = 0
    if attempts >= max_attempts:
        excesso = attempts - max_attempts
        backoff_seconds = min(backoff_base * (2 ** excesso), backoff_max)
        registro["blocked_until"] = agora + timedelta(seconds=backoff_seconds)

    cache.set(cache_key, registro, max(janela, backoff_seconds) + 60)
    return attempts, backoff_seconds


def _clear_rate_limit_scope(cache_key):
    if cache_key:
        cache.delete(cache_key)


def tags_index(request):
    tags = TagPublicacao.objects.filter(
        aprovacao_status=TagPublicacao.STATUS_APROVADO
    ).annotate(
        total_publicacoes=Count("tagged_publicacoes")
    ).order_by("name")

    return render(
        request,
        "conteudo/tags_index.html",
        {
            "tags": tags,
        },
    )


def autores_index(request):
    autores = Autor.objects.all().order_by("nome_completo")

    return render(
        request,
        "conteudo/autores_index.html",
        {
            "autores": autores,
        },
    )


def busca_publicacoes(request):
    import csv

    q = sanitizar_texto(request.GET.get("q", ""), multiline=False)
    categoria_slug = sanitizar_texto(request.GET.get("categoria", ""), multiline=False)
    autor_username = sanitizar_texto(request.GET.get("autor", ""), multiline=False)
    tag_slug = sanitizar_texto(request.GET.get("tag", ""), multiline=False)
    data_de_raw = sanitizar_texto(request.GET.get("data_de", ""), multiline=False)
    data_ate_raw = sanitizar_texto(request.GET.get("data_ate", ""), multiline=False)
    ordenacao = sanitizar_texto(request.GET.get("ordem", "recentes"), multiline=False)
    escopo = "publicacoes"
    exportar_csv = request.GET.get("export") == "csv"
    exportar_tudo = request.GET.get("export") == "csv_all"
    pagina = request.GET.get("page")
    termos_avancados = _extrair_termos_busca_avancada(request)

    categorias = Categoria.objects.all().order_by("nome")
    autores = Autor.objects.all().order_by("nome_completo")
    tags = TagPublicacao.objects.order_by("name")

    ordenacoes_disponiveis = {
        "recentes": ("-data_publicacao", "-first_published_at"),
        "antigos": ("data_publicacao", "first_published_at"),
        "titulo_az": ("title",),
        "titulo_za": ("-title",),
    }

    if ordenacao not in ordenacoes_disponiveis:
        ordenacao = "recentes"
    idioma_busca = (getattr(request, "LANGUAGE_CODE", "") or "pt-br").strip().lower()
    data_de, data_de_exibicao = _normalizar_data_busca(data_de_raw, idioma_busca)
    data_ate, data_ate_exibicao = _normalizar_data_busca(data_ate_raw, idioma_busca)

    termos_configurados = [item for item in termos_avancados if item["termo"]]
    busca_avancada_ativa = bool(termos_configurados)
    if not busca_avancada_ativa and q:
        termos_configurados = [{"indice": 1, "termo": q, "operador": "and"}]

    base_qs = PublicacaoPage.objects.live().select_related(
        "categoria_principal"
    ).prefetch_related(
        "autores_publicacao__autor",
        "tags",
    )

    resultados_qs = base_qs

    filtro_publicacoes = _combinar_filtros_busca(
        termos_configurados,
        idioma_busca,
        ["pt-br"],
        lambda variantes: _construir_filtro_publicacoes(variantes, ["pt-br"]),
    )
    if filtro_publicacoes is not None:
        resultados_qs = resultados_qs.filter(filtro_publicacoes)

    if categoria_slug:
        resultados_qs = resultados_qs.filter(categoria_principal__slug=categoria_slug)

    if autor_username:
        resultados_qs = resultados_qs.filter(autores_publicacao__autor__username=autor_username)
    if tag_slug:
        resultados_qs = resultados_qs.filter(tags__slug=tag_slug)
    if data_de:
        resultados_qs = resultados_qs.filter(data_publicacao__gte=data_de)
    if data_ate:
        resultados_qs = resultados_qs.filter(data_publicacao__lte=data_ate)

    resultados_qs = resultados_qs.distinct().order_by(*ordenacoes_disponiveis[ordenacao])
    base_qs = base_qs.distinct().order_by(*ordenacoes_disponiveis[ordenacao])

    if exportar_tudo:
        export_qs = base_qs
        nome_arquivo = "todas_publicacoes.csv"
    elif exportar_csv:
        export_qs = resultados_qs
        nome_arquivo = "resultados_busca.csv"
    else:
        export_qs = None
        nome_arquivo = None

    if export_qs is not None:
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'

        writer = csv.writer(response)
        writer.writerow([
            "Título",
            "Data de publicação",
            "Data de atualização",
            "Categoria",
            "Autores (nome completo)",
            "Autores (ORCID)",
            "Tags",
            "Palavras-chave",
            "URL",
            "URL PDF",
            "Resumo",
        ])

        for item in export_qs:
            autores_ordenados = list(item.autores_ordenados)
            autores_item = "; ".join([(autor.nome_completo or str(autor)) for autor in autores_ordenados])
            autores_orcid = "; ".join([autor.orcid for autor in autores_ordenados if (autor.orcid or "").strip()])
            tags = "; ".join([tag.name for tag in item.tags.all()])
            categoria = item.categoria_principal.nome if item.categoria_principal else ""
            url = request.build_absolute_uri(item.url) if item.url else ""
            url_pdf = request.build_absolute_uri(reverse("publicacao_pdf", args=[item.id]))
            resumo = strip_tags(item.resumo or "").strip()
            palavras_chave = (item.palavras_chave or "").strip()

            writer.writerow([
                item.title,
                item.data_publicacao.strftime("%d/%m/%Y") if item.data_publicacao else "",
                item.data_atualizacao.strftime("%d/%m/%Y") if item.data_atualizacao else "",
                categoria,
                autores_item,
                autores_orcid,
                tags,
                palavras_chave,
                url,
                url_pdf,
                resumo,
            ])

        return response

    home_page = HomePage.objects.live().public().first()
    try:
        itens_por_pagina_busca = max(1, int(getattr(home_page, "itens_por_pagina_ultimas_home", 10) or 10))
    except (TypeError, ValueError):
        itens_por_pagina_busca = 10

    total_publicacoes = resultados_qs.count()
    total_indexador = 0
    total_resultados = total_publicacoes
    paginador = Paginator(range(total_resultados or 1), itens_por_pagina_busca)
    page_obj = paginador.get_page(pagina)

    resultados_busca = []
    if total_resultados:
        inicio = max(0, page_obj.start_index() - 1)
        fim = min(total_resultados, page_obj.end_index())

        if inicio < total_publicacoes:
            fim_publicacoes = min(total_publicacoes, fim)
            for item in resultados_qs[inicio:fim_publicacoes]:
                resultados_busca.append(
                    {
                        "tipo": "publicacao",
                        "objeto": item,
                    }
                )

    filtros_query = request.GET.copy()
    filtros_query.pop("page", None)
    filtros_query.pop("export", None)
    filtros_query.pop("idioma", None)
    filtros_persistidos = []
    for chave in filtros_query.keys():
        for valor in filtros_query.getlist(chave):
            filtros_persistidos.append((chave, valor))

    return render(
        request,
        "conteudo/busca_publicacoes.html",
        {
            "q": q,
            "categoria_slug": categoria_slug,
            "autor_username": autor_username,
            "tag_slug": tag_slug,
            "data_de": data_de_exibicao,
            "data_ate": data_ate_exibicao,
            "data_de_iso": data_de,
            "data_ate_iso": data_ate,
            "ordenacao": ordenacao,
            "escopo": escopo,
            "termos_avancados": termos_avancados,
            "busca_avancada_ativa": busca_avancada_ativa,
            "categorias": categorias,
            "autores": autores,
            "tags": tags,
            "resultados_busca": resultados_busca,
            "total_publicacoes": total_publicacoes,
            "total_indexador": total_indexador,
            "total_resultados": total_resultados,
            "page_obj": page_obj,
            "filtros_persistidos": filtros_persistidos,
            "filtros_paginacao_querystring": filtros_query.urlencode(),
            "ha_filtros": bool(
                q
                or categoria_slug
                or autor_username
                or tag_slug
                or data_de
                or data_ate
                or busca_avancada_ativa
            ),
        },
    )


def email_open_track(request, token):
    destino = get_object_or_404(DisparoEmailDestino, tracking_token=token)
    agora = timezone.now()
    DisparoEmailDestino.objects.filter(pk=destino.pk).update(
        total_aberturas=F("total_aberturas") + 1,
        aberto_em=agora,
    )
    return HttpResponse(PIXEL_GIF_1X1, content_type="image/gif")


def email_click_track(request, token):
    destino = get_object_or_404(DisparoEmailDestino, tracking_token=token)
    payload = request.GET.get("d", "").strip()
    if not payload:
        return HttpResponseBadRequest("Link de rastreio inválido.")

    try:
        dados = signing.loads(payload, salt="ownpaper_email_click", max_age=60 * 60 * 24 * 90)
    except signing.BadSignature:
        return HttpResponseBadRequest("Link de rastreio inválido.")
    except signing.SignatureExpired:
        return HttpResponseBadRequest("Link de rastreio expirado.")

    url_destino = (dados or {}).get("u", "").strip()
    token_payload = str((dados or {}).get("t", "")).strip()
    if token_payload != str(destino.tracking_token) or not url_destino:
        return HttpResponseBadRequest("Link de rastreio inválido.")

    parsed = urllib.parse.urlparse(url_destino)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return HttpResponseBadRequest("Link de destino inválido.")

    agora = timezone.now()
    with transaction.atomic():
        DisparoEmailClique.objects.create(
            disparo=destino.disparo,
            destino=destino,
            url=url_destino,
        )
        DisparoEmailDestino.objects.filter(pk=destino.pk).update(
            total_cliques=F("total_cliques") + 1,
            ultimo_clique_em=agora,
        )

    return redirect(url_destino)


def publicacoes_por_tag(request, slug):
    tag = get_object_or_404(
        TagPublicacao,
        slug=slug,
        aprovacao_status=TagPublicacao.STATUS_APROVADO,
    )
    publicacoes = PublicacaoPage.objects.live().filter(
        tags__slug=slug,
        tags__aprovacao_status=TagPublicacao.STATUS_APROVADO,
    )

    return render(
        request,
        "conteudo/publicacoes_por_tag.html",
        {
            "tag": tag,
            "publicacoes": publicacoes,
        },
    )

def autor_detalhe(request, username):
    autor = get_object_or_404(Autor, username=username)
    publicacoes = PublicacaoPage.objects.live().filter(
        autores_publicacao__autor=autor
    ).distinct()
    _, config_site = obter_site_e_configuracao(request)

    return render(
        request,
        "conteudo/autor_detalhe.html",
        {
            "autor": autor,
            "publicacoes": publicacoes,
            "config_site": config_site,
        },
    )


def pagina_apoio(request):
    site, config_site = obter_site_e_configuracao(request)
    if not config_site or not config_site.doacoes_ativas:
        return redirect("/")

    return render(
        request,
        "conteudo/pagina_apoio.html",
        {
            "site": site,
            "config_site": config_site,
        },
    )

def categoria_detalhe(request, slug):
    categoria = get_object_or_404(
        Categoria,
        slug=slug,
        aprovacao_status=Categoria.STATUS_APROVADO,
    )
    publicacoes = PublicacaoPage.objects.live().filter(categoria_principal=categoria)

    return render(
        request,
        "conteudo/categoria_detalhe.html",
        {
            "categoria": categoria,
            "publicacoes": publicacoes,
        },
    )

def registrar_evento_newsletter(inscrito, tipo, origem="", detalhes=""):
    NewsletterEvento.objects.create(
        inscrito=inscrito,
        email=inscrito.email,
        tipo=tipo,
        origem=origem,
        detalhes=detalhes,
    )

def gerar_token_privacidade(email, solicitacao_id, page_id, acao):
    return signing.dumps(
        {
            "email": email,
            "solicitacao_id": solicitacao_id,
            "page_id": page_id,
        },
        salt=f"privacidade.{acao}",
    )


def ler_token_privacidade(token, acao, max_age=60 * 60 * 24 * 7):
    return signing.loads(
        token,
        salt=f"privacidade.{acao}",
        max_age=max_age,
    )

def gerar_token_newsletter(email, page_id, acao):
    return signing.dumps(
        {
            "email": email,
            "page_id": page_id,
        },
        salt=f"newsletter.{acao}",
    )


def ler_token_newsletter(token, acao, max_age=60 * 60 * 24 * 7):
    return signing.loads(
        token,
        salt=f"newsletter.{acao}",
        max_age=max_age,
    )


def url_publica(request, path, short_channel="", short_publicacao=None, short_title="", short_tags=None):
    base = getattr(settings, "PUBLIC_BASE_URL", "").strip()
    long_url = ""
    if base:
        long_url = f"{base.rstrip('/')}/{path.lstrip('/')}"
    else:
        long_url = request.build_absolute_uri(path)

    if short_channel:
        try:
            from .shlink_service import LinkCurtoShlink, obter_url_curta

            return obter_url_curta(
                long_url,
                canal=short_channel,
                contexto=LinkCurtoShlink.CONTEXTO_EMAIL,
                publicacao=short_publicacao,
                titulo=short_title,
                tags=short_tags or [],
                request=request,
            )
        except Exception:
            return long_url

    return long_url


def obter_site_e_configuracao(request):
    site = (
        Site.find_for_request(request)
        or Site.objects.filter(is_default_site=True).first()
        or Site.objects.first()
    )
    config_site = ConfiguracaoSite.for_site(site) if site else None
    return site, config_site


def url_publica_absoluta(request, url):
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return url_publica(request, url)


def renderizar_email_html(
    request,
    titulo,
    mensagem_html,
    botao_texto="",
    botao_url="",
):
    _, config_site = obter_site_e_configuracao(request)
    nome_site = (
        (config_site.nome_site or "").strip()
        if config_site
        else ""
    ) or getattr(settings, "WAGTAIL_SITE_NAME", "OwnPaper")
    assinatura = (
        (config_site.copyright_texto or "").strip()
        if config_site
        else ""
    ) or f"Equipe {nome_site}"
    email_contato = (
        (config_site.email_contato or "").strip()
        if config_site
        else ""
    )
    imagem_logo = None
    if config_site:
        imagem_logo = config_site.imagem_compartilhamento_padrao or config_site.favicon
    logo_url = ""
    if imagem_logo and getattr(imagem_logo, "file", None):
        logo_url = url_publica_absoluta(request, imagem_logo.file.url)

    botao_html = ""
    if botao_texto and botao_url:
        botao_html = (
            "<p style='margin:24px 0'>"
            f"<a href='{escape(botao_url)}' "
            "style='display:inline-block;background:#0f766e;color:#fff;text-decoration:none;"
            "padding:12px 18px;border-radius:10px;font-weight:700'>"
            f"{escape(botao_texto)}</a>"
            "</p>"
        )

    logo_html = ""
    if logo_url:
        logo_html = (
            "<p style='margin:0 0 20px 0'>"
            f"<img src='{escape(logo_url)}' alt='{escape(nome_site)}' "
            "style='max-height:44px;max-width:220px;height:auto;width:auto'/>"
            "</p>"
        )

    contato_html = ""
    if email_contato:
        contato_html = (
            "<p style='margin:8px 0 0 0;font-size:12px;color:#64748b'>"
            f"Contato: <a href='mailto:{escape(email_contato)}' style='color:#0f766e'>"
            f"{escape(email_contato)}</a></p>"
        )

    return (
        "<div style='background:#f8fafc;padding:24px'>"
        "<div style='max-width:640px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;"
        "border-radius:14px;padding:26px;font-family:Arial,Helvetica,sans-serif;color:#0f172a'>"
        f"{logo_html}"
        f"<h1 style='margin:0 0 14px 0;font-size:22px;line-height:1.25'>{escape(titulo)}</h1>"
        f"<div style='font-size:15px;line-height:1.6'>{mensagem_html}</div>"
        f"{botao_html}"
        "<hr style='margin:20px 0;border:none;border-top:1px solid #e2e8f0'/>"
        f"<p style='margin:0;font-size:13px;color:#334155'>{escape(assinatura)}</p>"
        f"{contato_html}"
        "</div>"
        "</div>"
    )


def convite_aceitar(request, token):
    User = get_user_model()

    convite = get_object_or_404(
        ConviteUsuario,
        token=token,
    )

    if convite.status == ConviteUsuario.STATUS_ACEITO:
        return render(
            request,
            "conteudo/convite_aceitar.html",
            {
                "convite": convite,
                "sucesso": False,
                "erro_geral": "Este convite já foi utilizado.",
            },
        )

    if convite.status == ConviteUsuario.STATUS_CANCELADO:
        return render(
            request,
            "conteudo/convite_aceitar.html",
            {
                "convite": convite,
                "sucesso": False,
                "erro_geral": "Este convite foi cancelado.",
            },
        )

    if convite.expirado:
        if convite.status != ConviteUsuario.STATUS_EXPIRADO:
            convite.status = ConviteUsuario.STATUS_EXPIRADO
            convite.save(update_fields=["status", "atualizado_em"])
        return render(
            request,
            "conteudo/convite_aceitar.html",
            {
                "convite": convite,
                "sucesso": False,
                "erro_geral": "Este convite expirou. Solicite um novo convite ao administrador.",
            },
        )

    if request.method == "POST":
        nome = sanitizar_texto(request.POST.get("nome", ""))
        username_raw = sanitizar_texto(request.POST.get("username", ""))
        username = re.sub(r"[^a-zA-Z0-9._-]", "", username_raw).lower()
        password = request.POST.get("password", "")
        password_confirmacao = request.POST.get("password_confirmacao", "")

        erros = []
        if not nome:
            erros.append("Informe seu nome.")
        if not username:
            erros.append("Informe um nome de usuário.")
        if username == "admin":
            erros.append("O nome de usuário 'admin' não é permitido. Escolha outro.")
        if User.objects.filter(username=username).exists():
            erros.append("Este nome de usuário já está em uso.")
        if User.objects.filter(email__iexact=convite.email).exists():
            erros.append("Já existe um usuário ativo com este e-mail.")
        if password != password_confirmacao:
            erros.append("A confirmação de senha não confere.")
        if not erros:
            try:
                validate_password(password)
            except ValidationError as exc:
                erros.extend(exc.messages)

        if erros:
            return render(
                request,
                "conteudo/convite_aceitar.html",
                {
                    "convite": convite,
                    "sucesso": False,
                    "erros": erros,
                    "nome": nome,
                    "username": username,
                },
            )

        with transaction.atomic():
            usuario = User(
                username=username,
                email=convite.email,
                first_name=nome,
                is_active=True,
            )
            usuario.set_password(password)
            usuario.save()
            aplicar_papeis_por_convite(usuario, convite, nome=nome)

            convite.status = ConviteUsuario.STATUS_ACEITO
            convite.aceito_em = timezone.now()
            convite.usuario_criado = usuario
            convite.save(
                update_fields=[
                    "status",
                    "aceito_em",
                    "usuario_criado",
                    "atualizado_em",
                ]
            )
        registrar_auditoria(
            request=request,
            usuario=usuario,
            acao="convite_aceito_criou_usuario",
            alvo=usuario,
            detalhes=(
                f"Convite aceito. Papéis: {convite.resumo_papeis}. "
                f"Token convite: {convite.token}."
            ),
        )

        return render(
            request,
            "conteudo/convite_aceitar.html",
            {
                "convite": convite,
                "sucesso": True,
            },
        )

    return render(
        request,
        "conteudo/convite_aceitar.html",
        {
            "convite": convite,
            "sucesso": False,
            "nome": convite.nome_completo,
            "username": convite.username_sugerido,
        },
    )

def contato_form(request, slug):
    pagina = get_object_or_404(ContatoPage.objects.live(), slug=slug)

    if request.method == "POST":
        nome = sanitizar_texto(request.POST.get("nome", ""), multiline=False)
        email = sanitizar_texto(request.POST.get("email", ""), multiline=False).lower()
        mensagem = sanitizar_texto(request.POST.get("mensagem", ""), multiline=True)
        aceitou_privacidade = request.POST.get("aceitou_privacidade") == "on"
        website = sanitizar_texto(request.POST.get("website", ""), multiline=False)
        turnstile_token = request.POST.get("cf-turnstile-response", "").strip()

        ip = _ip_da_requisicao_view(request) or "desconhecido"

        ip_key = _rate_limit_scope_key("contato", "ip", ip)
        email_key = _rate_limit_scope_key("contato", "email", email) if email else None
        blocked_for_ip = _remaining_block_seconds(ip_key)
        blocked_for_email = _remaining_block_seconds(email_key) if email_key else 0
        if blocked_for_ip or blocked_for_email:
            forms_security_logger.warning(
                "form_rate_limited",
                extra={
                    "event": "form_rate_limited",
                    "form": "contato",
                    "ip": ip,
                    "email": email,
                    "blocked_for_seconds": max(blocked_for_ip, blocked_for_email),
                },
            )
            return redirect(f"{pagina.url}?limite=1")

        if website:
            ip_attempts, ip_backoff = _register_failed_attempt(
                ip_key,
                settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_IP,
            )
            if email_key:
                _register_failed_attempt(
                    email_key,
                    settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_EMAIL,
                )
            forms_security_logger.warning(
                "form_honeypot_triggered",
                extra={
                    "event": "form_honeypot_triggered",
                    "form": "contato",
                    "ip": ip,
                    "email": email,
                    "attempts_ip": ip_attempts,
                    "backoff_seconds": ip_backoff,
                },
            )
            return redirect(f"{pagina.url}?enviado=1")

        if not nome or not email or not mensagem or not aceitou_privacidade:
            ip_attempts, ip_backoff = _register_failed_attempt(
                ip_key,
                settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_IP,
            )
            if email_key:
                _register_failed_attempt(
                    email_key,
                    settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_EMAIL,
                )
            forms_security_logger.info(
                "form_validation_failed",
                extra={
                    "event": "form_validation_failed",
                    "form": "contato",
                    "ip": ip,
                    "email": email,
                    "reason": "required_fields",
                    "attempts_ip": ip_attempts,
                    "backoff_seconds": ip_backoff,
                },
            )
            return HttpResponseBadRequest("Preencha todos os campos obrigatórios.")

        if (
            len(nome) > settings.CONTACT_MAX_NOME_LENGTH
            or len(mensagem) > settings.CONTACT_MAX_MENSAGEM_LENGTH
            or len(email) > settings.NEWSLETTER_MAX_EMAIL_LENGTH
        ):
            ip_attempts, ip_backoff = _register_failed_attempt(
                ip_key,
                settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_IP,
            )
            if email_key:
                _register_failed_attempt(
                    email_key,
                    settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_EMAIL,
                )
            forms_security_logger.info(
                "form_validation_failed",
                extra={
                    "event": "form_validation_failed",
                    "form": "contato",
                    "ip": ip,
                    "email": email,
                    "reason": "field_length",
                    "attempts_ip": ip_attempts,
                    "backoff_seconds": ip_backoff,
                },
            )
            return HttpResponseBadRequest("Preencha todos os campos obrigatórios.")

        try:
            validate_email(email)
        except ValidationError:
            ip_attempts, ip_backoff = _register_failed_attempt(
                ip_key,
                settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_IP,
            )
            if email_key:
                _register_failed_attempt(
                    email_key,
                    settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_EMAIL,
                )
            forms_security_logger.info(
                "form_validation_failed",
                extra={
                    "event": "form_validation_failed",
                    "form": "contato",
                    "ip": ip,
                    "email": email,
                    "reason": "invalid_email",
                    "attempts_ip": ip_attempts,
                    "backoff_seconds": ip_backoff,
                },
            )
            return HttpResponseBadRequest("Informe um e-mail válido.")

        if settings.TURNSTILE_ENABLED and not validar_turnstile(turnstile_token, remoteip=ip):
            ip_attempts, ip_backoff = _register_failed_attempt(
                ip_key,
                settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_IP,
            )
            if email_key:
                _register_failed_attempt(
                    email_key,
                    settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_EMAIL,
                )
            forms_security_logger.warning(
                "form_captcha_failed",
                extra={
                    "event": "form_captcha_failed",
                    "form": "contato",
                    "ip": ip,
                    "email": email,
                    "attempts_ip": ip_attempts,
                    "backoff_seconds": ip_backoff,
                },
            )
            return redirect(f"{pagina.url}?captcha=1")

        _clear_rate_limit_scope(ip_key)
        if email_key:
            _clear_rate_limit_scope(email_key)

        sinalizado = _texto_suspeito_para_moderacao(mensagem) or _texto_publico_contem_risco(
            "\n".join([nome, email, mensagem])
        )
        if sinalizado:
            forms_security_logger.warning(
                "form_suspicious_content",
                extra={
                    "event": "form_suspicious_content",
                    "form": "contato",
                    "ip": ip,
                    "email": email,
                },
            )

        mensagem_contato = MensagemContato.objects.create(
            pagina=pagina,
            nome=nome,
            email=email,
            mensagem=mensagem,
            sinalizado_conteudo=sinalizado,
            ip_origem=ip if ip != "desconhecido" else None,
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:500],
        )
        registrar_auditoria(
            request=request,
            acao="contato_mensagem_recebida",
            alvo=mensagem_contato,
            detalhes=f"Mensagem recebida via página de contato: {pagina.slug}.",
        )

        if pagina.email_destino:
            assunto = f"[Contato do site] {pagina.title} - {nome}"
            mensagem_formatada = escape(mensagem).replace("\n", "<br>")
            corpo = renderizar_email_html(
                request=request,
                titulo="Nova mensagem de contato",
                mensagem_html=(
                    f"<p><strong>Página:</strong> {escape(pagina.title)}</p>"
                    f"<p><strong>Nome:</strong> {escape(nome)}</p>"
                    f"<p><strong>E-mail:</strong> {escape(email)}</p>"
                    f"<p><strong>Mensagem:</strong><br>{mensagem_formatada}</p>"
                ),
            )

            try:
                email_msg = EmailMessage(
                    subject=assunto,
                    body=corpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[pagina.email_destino],
                    reply_to=[email],
                )
                email_msg.content_subtype = "html"
                email_msg.send(fail_silently=False)
                return redirect(f"{pagina.url}?enviado=1")
            except Exception:
                forms_security_logger.error(
                    "form_email_send_failed",
                    extra={
                        "event": "form_email_send_failed",
                        "form": "contato",
                        "ip": ip,
                        "email": email,
                    },
                )
                return redirect(f"{pagina.url}?enviado=1&email_falhou=1")

        return redirect(f"{pagina.url}?enviado=1")

    return redirect(pagina.url)


def submissao_publica(request):
    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    config_site = ConfiguracaoSite.for_site(site) if site else None
    if not config_site or not config_site.submissoes_publicas_ativas:
        return render(
            request,
            "conteudo/submissao_publica.html",
            {"config_site": config_site, "indisponivel": True},
            status=404,
        )

    usuario_logado = _usuario_comentario_cookie(request)
    erros = []
    sucesso = False
    valores = {}

    if request.method == "POST":
        titulo = sanitizar_texto(request.POST.get("titulo", ""), multiline=False)[:255]
        resumo = sanitizar_texto(request.POST.get("resumo", ""), multiline=True)[:5000]
        mensagem = sanitizar_texto(request.POST.get("mensagem", ""), multiline=True)[:5000]
        nome = sanitizar_texto(request.POST.get("nome", ""), multiline=False)[:120]
        email = sanitizar_texto(request.POST.get("email", ""), multiline=False).strip().lower()
        username = normalizar_username_publico(request.POST.get("username", ""))
        orcid = sanitizar_texto(request.POST.get("orcid", ""), multiline=False).strip()
        arquivo = request.FILES.get("arquivo_pdf")
        valores = {
            "titulo": titulo,
            "resumo": resumo,
            "mensagem": mensagem,
            "nome": nome,
            "email": email,
            "username": username,
            "orcid": orcid,
        }

        if usuario_logado:
            email = usuario_logado.email
            username = usuario_logado.username
            nome = usuario_logado.nome
            orcid = orcid or usuario_logado.orcid

        if not titulo:
            erros.append("Informe o título.")
        if not resumo:
            erros.append("Informe um resumo.")
        if not arquivo:
            erros.append("Envie o PDF da submissão.")
        if not email:
            erros.append("Informe o e-mail.")
        else:
            try:
                validate_email(email)
            except ValidationError:
                erros.append("Informe um e-mail válido.")
        if not username:
            erros.append("Informe um nome de usuário válido.")
        if config_site.submissoes_exigir_orcid and not orcid:
            erros.append("ORCID é obrigatório para submissões neste projeto.")
        orcid_normalizado = _normalizar_orcid(orcid) if orcid else ""
        if orcid and not orcid_normalizado:
            erros.append("Informe um ORCID válido.")
        if _texto_publico_contem_risco("\n".join([titulo, resumo, mensagem, nome, email, username, orcid])):
            erros.append("O texto contém padrões bloqueados por segurança.")

        erro_conflito = ""
        usuario_email = usuario_username = usuario_orcid = None
        if not erros:
            erro_conflito, usuario_email, usuario_username, usuario_orcid = _resolver_conflitos_usuario_comentario(
                email=email,
                username=username,
                orcid=orcid_normalizado,
                usuario_atual=usuario_logado,
            )
            if erro_conflito:
                erros.append("Este e-mail, nome de usuário ou ORCID já está vinculado a outra identidade pública.")

        if not erros:
            try:
                bytes_pdf = _sanitizar_pdf_submissao(
                    arquivo,
                    titulo,
                    limite_mb=config_site.submissoes_limite_pdf_mb,
                )
            except ValidationError as exc:
                erros.extend(exc.messages)

        if not erros:
            with transaction.atomic():
                usuario = usuario_logado or usuario_email or usuario_username or usuario_orcid
                if usuario:
                    updates = []
                    if nome and not usuario.nome:
                        usuario.nome = nome
                        updates.append("nome")
                    if orcid_normalizado and not usuario.orcid:
                        usuario.orcid = orcid_normalizado
                        updates.append("orcid")
                    if updates:
                        usuario.save(update_fields=updates + ["atualizado_em"])
                else:
                    usuario = UsuarioComentario.objects.create(
                        nome=nome,
                        email=email,
                        username=username,
                        orcid=orcid_normalizado or "",
                    )

                submissao = SubmissaoPublica.objects.create(
                    usuario=usuario,
                    titulo=titulo,
                    resumo=resumo,
                    mensagem=mensagem,
                    arquivo_nome_original=(getattr(arquivo, "name", "") or "")[:255],
                    arquivo_tamanho=len(bytes_pdf),
                    arquivo_sha256=hashlib.sha256(bytes_pdf).hexdigest(),
                    ip_origem=_ip_da_requisicao_view(request) or None,
                    user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:500],
                )
                submissao.arquivo_pdf.save(
                    submissao_publica_upload_to(submissao, f"{titulo}.pdf"),
                    ContentFile(bytes_pdf),
                    save=True,
                )
                registrar_auditoria(
                    request=request,
                    acao="submissao_publica_recebida",
                    alvo=submissao,
                    detalhes=f"Submissão pública recebida: {submissao.titulo}.",
                )
            sucesso = True
            response = render(
                request,
                "conteudo/submissao_publica.html",
                {"config_site": config_site, "sucesso": sucesso, "submissao": submissao},
            )
            return _definir_cookie_usuario_comentario(response, request, usuario)

    return render(
        request,
        "conteudo/submissao_publica.html",
        {
            "config_site": config_site,
            "usuario_publico": usuario_logado,
            "erros": erros,
            "valores": valores,
        },
    )


def submissao_publica_completar(request, token):
    submissao = get_object_or_404(SubmissaoPublica, token_acesso=token)
    if not submissao.pode_complementar_ficha:
        return render(
            request,
            "conteudo/submissao_publica_completar.html",
            {"submissao": submissao, "bloqueada": True},
            status=403,
        )
    erros = []
    sucesso = False
    valores = {
        "nome_completo": submissao.ficha_nome_completo or submissao.usuario.nome,
        "nome_exibicao": submissao.ficha_nome_exibicao or submissao.usuario.nome or submissao.usuario.username,
        "mini_bio": submissao.ficha_mini_bio,
        "instagram": submissao.ficha_instagram,
        "mastodon": submissao.ficha_mastodon,
        "lattes_url": submissao.ficha_lattes_url,
        "texto_final": submissao.texto_final,
    }
    if request.method == "POST":
        valores = {
            "nome_completo": sanitizar_texto(request.POST.get("nome_completo", ""), multiline=False)[:255],
            "nome_exibicao": sanitizar_texto(request.POST.get("nome_exibicao", ""), multiline=False)[:255],
            "mini_bio": sanitizar_texto(request.POST.get("mini_bio", ""), multiline=True)[:5000],
            "instagram": sanitizar_texto(request.POST.get("instagram", ""), multiline=False)[:255],
            "mastodon": sanitizar_texto(request.POST.get("mastodon", ""), multiline=False)[:255],
            "lattes_url": sanitizar_texto(request.POST.get("lattes_url", ""), multiline=False)[:255],
            "texto_final": sanitizar_texto(request.POST.get("texto_final", ""), multiline=True),
        }
        if not valores["nome_completo"]:
            erros.append("Informe seu nome completo.")
        if not valores["mini_bio"]:
            erros.append("Informe uma mini bio.")
        if not valores["texto_final"]:
            erros.append("Cole o texto final para revisão.")
        if _texto_publico_contem_risco("\n".join(valores.values())):
            erros.append("O formulário contém padrões bloqueados por segurança.")
        if not erros:
            submissao.ficha_nome_completo = valores["nome_completo"]
            submissao.ficha_nome_exibicao = valores["nome_exibicao"]
            submissao.ficha_mini_bio = valores["mini_bio"]
            submissao.ficha_instagram = valores["instagram"]
            submissao.ficha_mastodon = valores["mastodon"]
            submissao.ficha_lattes_url = valores["lattes_url"]
            submissao.texto_final = valores["texto_final"]
            submissao.save(
                update_fields=[
                    "ficha_nome_completo",
                    "ficha_nome_exibicao",
                    "ficha_mini_bio",
                    "ficha_instagram",
                    "ficha_mastodon",
                    "ficha_lattes_url",
                    "texto_final",
                    "atualizado_em",
                ]
            )
            registrar_auditoria(
                request=request,
                acao="submissao_publica_ficha_complementada",
                alvo=submissao,
                detalhes=f"Ficha pública complementada: {submissao.titulo}.",
            )
            sucesso = True
    return render(
        request,
        "conteudo/submissao_publica_completar.html",
        {"submissao": submissao, "erros": erros, "valores": valores, "sucesso": sucesso},
    )

def newsletter_form(request, slug):
    pagina = get_object_or_404(NewsletterPage.objects.live(), slug=slug)

    if request.method == "POST":
        email = sanitizar_texto(request.POST.get("email", ""), multiline=False).lower()
        consentimento = request.POST.get("consentimento") == "on"
        website = sanitizar_texto(request.POST.get("website", ""), multiline=False)
        turnstile_token = request.POST.get("cf-turnstile-response", "").strip()

        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        if not ip:
            ip = request.META.get("REMOTE_ADDR", "desconhecido")

        ip_key = _rate_limit_scope_key("newsletter", "ip", ip)
        email_key = _rate_limit_scope_key("newsletter", "email", email) if email else None
        blocked_for_ip = _remaining_block_seconds(ip_key)
        blocked_for_email = _remaining_block_seconds(email_key) if email_key else 0
        if blocked_for_ip or blocked_for_email:
            forms_security_logger.warning(
                "form_rate_limited",
                extra={
                    "event": "form_rate_limited",
                    "form": "newsletter",
                    "ip": ip,
                    "email": email,
                    "blocked_for_seconds": max(blocked_for_ip, blocked_for_email),
                },
            )
            return redirect(f"{pagina.url}?limite=1")

        if website:
            ip_attempts, ip_backoff = _register_failed_attempt(
                ip_key,
                settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_IP,
            )
            if email_key:
                _register_failed_attempt(
                    email_key,
                    settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_EMAIL,
                )
            forms_security_logger.warning(
                "form_honeypot_triggered",
                extra={
                    "event": "form_honeypot_triggered",
                    "form": "newsletter",
                    "ip": ip,
                    "email": email,
                    "attempts_ip": ip_attempts,
                    "backoff_seconds": ip_backoff,
                },
            )
            return redirect(f"{pagina.url}?sucesso=1")

        if not email or not consentimento:
            ip_attempts, ip_backoff = _register_failed_attempt(
                ip_key,
                settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_IP,
            )
            if email_key:
                _register_failed_attempt(
                    email_key,
                    settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_EMAIL,
                )
            forms_security_logger.info(
                "form_validation_failed",
                extra={
                    "event": "form_validation_failed",
                    "form": "newsletter",
                    "ip": ip,
                    "email": email,
                    "reason": "required_fields",
                    "attempts_ip": ip_attempts,
                    "backoff_seconds": ip_backoff,
                },
            )
            return HttpResponseBadRequest("Preencha todos os campos obrigatorios.")

        if len(email) > settings.NEWSLETTER_MAX_EMAIL_LENGTH:
            ip_attempts, ip_backoff = _register_failed_attempt(
                ip_key,
                settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_IP,
            )
            if email_key:
                _register_failed_attempt(
                    email_key,
                    settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_EMAIL,
                )
            forms_security_logger.info(
                "form_validation_failed",
                extra={
                    "event": "form_validation_failed",
                    "form": "newsletter",
                    "ip": ip,
                    "email": email,
                    "reason": "field_length",
                    "attempts_ip": ip_attempts,
                    "backoff_seconds": ip_backoff,
                },
            )
            return HttpResponseBadRequest("Informe um e-mail válido.")

        try:
            validate_email(email)
        except ValidationError:
            ip_attempts, ip_backoff = _register_failed_attempt(
                ip_key,
                settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_IP,
            )
            if email_key:
                _register_failed_attempt(
                    email_key,
                    settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_EMAIL,
                )
            forms_security_logger.info(
                "form_validation_failed",
                extra={
                    "event": "form_validation_failed",
                    "form": "newsletter",
                    "ip": ip,
                    "email": email,
                    "reason": "invalid_email",
                    "attempts_ip": ip_attempts,
                    "backoff_seconds": ip_backoff,
                },
            )
            return HttpResponseBadRequest("Informe um e-mail válido.")

        if settings.TURNSTILE_ENABLED and not validar_turnstile(turnstile_token, remoteip=ip):
            ip_attempts, ip_backoff = _register_failed_attempt(
                ip_key,
                settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_IP,
            )
            if email_key:
                _register_failed_attempt(
                    email_key,
                    settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_EMAIL,
                )
            forms_security_logger.warning(
                "form_captcha_failed",
                extra={
                    "event": "form_captcha_failed",
                    "form": "newsletter",
                    "ip": ip,
                    "email": email,
                    "attempts_ip": ip_attempts,
                    "backoff_seconds": ip_backoff,
                },
            )
            return redirect(f"{pagina.url}?captcha=1")

        _clear_rate_limit_scope(ip_key)
        if email_key:
            _clear_rate_limit_scope(email_key)

        inscrito_existente = InscritoNewsletter.objects.filter(email__iexact=email).first()
        if (
            inscrito_existente
            and inscrito_existente.ativo
            and inscrito_existente.consentimento
            and inscrito_existente.confirmado_em
        ):
            return redirect(f"{pagina.url}?existente=1")

        inscrito, criado = InscritoNewsletter.objects.get_or_create(
            email=email,
            defaults={
                "ativo": True,
                "consentimento": True,
                "origem": f"newsletter:{pagina.slug}",
                "confirmado_em": timezone.now(),
            },
        )

        if criado:
            registrar_evento_newsletter(
                inscrito=inscrito,
                tipo=NewsletterEvento.TIPO_INSCRICAO_CONFIRMADA,
                origem=f"newsletter:{pagina.slug}",
                detalhes="Cadastro direto via formulario publico, sem confirmacao por e-mail.",
            )
        else:
            inscrito.ativo = True
            inscrito.consentimento = True
            inscrito.origem = f"newsletter:{pagina.slug}"
            if not inscrito.confirmado_em:
                inscrito.confirmado_em = timezone.now()
            inscrito.save()

            registrar_evento_newsletter(
                inscrito=inscrito,
                tipo=NewsletterEvento.TIPO_INSCRICAO_CONFIRMADA,
                origem=f"newsletter:{pagina.slug}",
                detalhes="Inscricao reativada ou atualizada via formulario publico, sem confirmacao por e-mail.",
            )

        return redirect(f"{pagina.url}?sucesso=1")

    return redirect(pagina.url)

def newsletter_confirmar(request, slug, token):
    pagina = get_object_or_404(NewsletterPage.objects.live(), slug=slug)

    try:
        payload = ler_token_newsletter(token, "confirmar")
    except signing.SignatureExpired:
        return redirect(f"{pagina.url}?token_expirado=1")
    except signing.BadSignature:
        return redirect(f"{pagina.url}?token_invalido=1")

    if payload.get("page_id") != pagina.id:
        return redirect(f"{pagina.url}?token_invalido=1")

    inscrito = get_object_or_404(InscritoNewsletter, email=payload.get("email", "").lower())

    inscrito.ativo = True
    inscrito.consentimento = True
    inscrito.confirmado_em = timezone.now()
    inscrito.save()

    registrar_evento_newsletter(
        inscrito=inscrito,
        tipo=NewsletterEvento.TIPO_INSCRICAO_CONFIRMADA,
        origem=f"newsletter:{pagina.slug}",
        detalhes="Inscrição confirmada pelo link enviado por e-mail.",
    )

    return redirect(f"{pagina.url}?confirmado=1")


def newsletter_cancelar(request, slug, token):
    pagina = get_object_or_404(NewsletterPage.objects.live(), slug=slug)

    try:
        payload = ler_token_newsletter(token, "cancelar")
    except signing.SignatureExpired:
        return redirect(f"{pagina.url}?token_expirado=1")
    except signing.BadSignature:
        return redirect(f"{pagina.url}?token_invalido=1")

    if payload.get("page_id") != pagina.id:
        return redirect(f"{pagina.url}?token_invalido=1")

    inscrito = get_object_or_404(InscritoNewsletter, email=payload.get("email", "").lower())

    if inscrito:
        inscrito.ativo = False
        inscrito.consentimento = False
        inscrito.save()

        registrar_evento_newsletter(
            inscrito=inscrito,
            tipo=NewsletterEvento.TIPO_CANCELAMENTO_CONFIRMADO,
            origem=f"newsletter:{pagina.slug}",
            detalhes="Cancelamento confirmado por link enviado por e-mail.",
        )

        try:
            url_newsletter = url_publica(
                request,
                f"/newsletter/{pagina.slug}/",
                short_channel="email",
                short_title=f"Newsletter {pagina.title}",
                short_tags=["ownpaper", "newsletter", "email", "retorno"],
            )
            corpo = renderizar_email_html(
                request=request,
                titulo="Inscrição cancelada com sucesso",
                mensagem_html=(
                    "<p>Seu e-mail foi removido da newsletter com sucesso.</p>"
                    "<p>Se quiser voltar a receber novidades, você pode se inscrever novamente a qualquer momento.</p>"
                    f"<p style='word-break:break-word'><strong>Página da newsletter:</strong> "
                    f"<a href='{escape(url_newsletter)}'>{escape(url_newsletter)}</a></p>"
                ),
                botao_texto="Voltar para a newsletter",
                botao_url=url_newsletter,
            )
            email_msg = EmailMessage(
                subject=f"Cancelamento confirmado - {pagina.title}",
                body=corpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[inscrito.email],
            )
            email_msg.content_subtype = "html"
            email_msg.send(fail_silently=False)
        except Exception:
            forms_security_logger.error(
                "form_email_send_failed",
                extra={
                    "event": "form_email_send_failed",
                    "form": "newsletter_cancelamento_confirmado",
                    "email": inscrito.email,
                },
            )

    return redirect(f"{pagina.url}?descadastrado=1")

def newsletter_solicitar_cancelamento(request, slug):
    pagina = get_object_or_404(NewsletterPage.objects.live(), slug=slug)

    if request.method == "POST":
        email = sanitizar_texto(request.POST.get("email_cancelamento", ""), multiline=False).lower()
        turnstile_token = request.POST.get("cf-turnstile-response", "").strip()

        if not email:
            return HttpResponseBadRequest("Informe um e-mail válido.")
        try:
            validate_email(email)
        except ValidationError:
            return HttpResponseBadRequest("Informe um e-mail válido.")

        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        if not ip:
            ip = request.META.get("REMOTE_ADDR", "desconhecido")

        if settings.TURNSTILE_ENABLED and not validar_turnstile(turnstile_token, remoteip=ip):
            return redirect(f"{pagina.url}?captcha=1")

        inscrito = InscritoNewsletter.objects.filter(email__iexact=email).first()

        if inscrito:
            registrar_evento_newsletter(
                inscrito=inscrito,
                tipo=NewsletterEvento.TIPO_CANCELAMENTO_SOLICITADO,
                origem=f"newsletter:{pagina.slug}",
                detalhes="Pedido de cancelamento solicitado pela página pública.",
            )

            token_cancelamento = gerar_token_newsletter(email, pagina.id, "cancelar")
            url_cancelamento = url_publica(
                request,
                f"/newsletter/{pagina.slug}/cancelar/{token_cancelamento}/",
                short_channel="email",
                short_title=f"Cancelamento newsletter {pagina.title}",
                short_tags=["ownpaper", "newsletter", "email", "cancelamento"],
            )

            assunto = f"Cancelar inscrição - {pagina.title}"
            corpo = renderizar_email_html(
                request=request,
                titulo="Confirmação de cancelamento da newsletter",
                mensagem_html=(
                    "<p>Recebemos um pedido para cancelar sua inscrição na newsletter.</p>"
                    "<p>Se você não fez esse pedido, ignore este e-mail.</p>"
                    f"<p style='word-break:break-word'><strong>Link alternativo:</strong> "
                    f"<a href='{escape(url_cancelamento)}'>{escape(url_cancelamento)}</a></p>"
                ),
                botao_texto="Confirmar cancelamento",
                botao_url=url_cancelamento,
            )

            try:
                email_msg = EmailMessage(
                    subject=assunto,
                    body=corpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                email_msg.content_subtype = "html"
                email_msg.send(fail_silently=False)
            except Exception:
                forms_security_logger.error(
                    "form_email_send_failed",
                    extra={
                        "event": "form_email_send_failed",
                        "form": "newsletter_cancelamento",
                        "email": email,
                    },
                )
                return redirect(f"{pagina.url}?cancelamento_email_falhou=1")

        return redirect(f"{pagina.url}?cancelamento_enviado=1")

    return redirect(pagina.url)

def gerar_exportacao_privacidade_newsletter(email):
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(["tipo", "campo_1", "campo_2", "campo_3", "campo_4", "campo_5", "campo_6", "campo_7"])
    for linha in coletar_linhas_privacidade_por_email(email):
        writer.writerow(linha)

    return buffer.getvalue().encode("utf-8")


def _privacy_redirect_url(request, pagina_newsletter):
    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None
    if config_site and config_site.pagina_privacidade:
        return config_site.pagina_privacidade.url
    return pagina_newsletter.url

def newsletter_solicitar_privacidade(request, slug):
    pagina = get_object_or_404(NewsletterPage.objects.live(), slug=slug)
    redirect_base = _privacy_redirect_url(request, pagina)

    if request.method == "POST":
        email = sanitizar_texto(request.POST.get("email_privacidade", ""), multiline=False).lower()
        tipo = sanitizar_texto(request.POST.get("tipo_privacidade", ""), multiline=False)
        website = sanitizar_texto(request.POST.get("website_privacidade", ""), multiline=False)
        turnstile_token = request.POST.get("cf-turnstile-response", "").strip()

        if not email or tipo not in [
            SolicitacaoPrivacidadeNewsletter.TIPO_ACESSO,
            SolicitacaoPrivacidadeNewsletter.TIPO_EXCLUSAO,
        ]:
            return HttpResponseBadRequest("Dados invalidos.")
        try:
            validate_email(email)
        except ValidationError:
            return HttpResponseBadRequest("Dados invalidos.")

        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        if not ip:
            ip = request.META.get("REMOTE_ADDR", "desconhecido")

        ip_key = _rate_limit_scope_key("privacidade", "ip", ip)
        email_key = _rate_limit_scope_key("privacidade", "email", email) if email else None
        blocked_for_ip = _remaining_block_seconds(ip_key)
        blocked_for_email = _remaining_block_seconds(email_key) if email_key else 0
        if blocked_for_ip or blocked_for_email:
            forms_security_logger.warning(
                "form_rate_limited",
                extra={
                    "event": "form_rate_limited",
                    "form": "privacidade",
                    "ip": ip,
                    "email": email,
                    "blocked_for_seconds": max(blocked_for_ip, blocked_for_email),
                },
            )
            return redirect(f"{redirect_base}?limite=1")

        if website:
            ip_attempts, ip_backoff = _register_failed_attempt(
                ip_key,
                settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_IP,
            )
            if email_key:
                _register_failed_attempt(
                    email_key,
                    settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_EMAIL,
                )
            forms_security_logger.warning(
                "form_honeypot_triggered",
                extra={
                    "event": "form_honeypot_triggered",
                    "form": "privacidade",
                    "ip": ip,
                    "email": email,
                    "attempts_ip": ip_attempts,
                    "backoff_seconds": ip_backoff,
                },
            )
            return redirect(f"{redirect_base}?privacidade=1")

        if settings.TURNSTILE_ENABLED and not validar_turnstile(turnstile_token, remoteip=ip):
            ip_attempts, ip_backoff = _register_failed_attempt(
                ip_key,
                settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_IP,
            )
            if email_key:
                _register_failed_attempt(
                    email_key,
                    settings.FORM_RATE_LIMIT_MAX_ATTEMPTS_EMAIL,
                )
            forms_security_logger.warning(
                "form_captcha_failed",
                extra={
                    "event": "form_captcha_failed",
                    "form": "privacidade",
                    "ip": ip,
                    "email": email,
                    "attempts_ip": ip_attempts,
                    "backoff_seconds": ip_backoff,
                },
            )
            return redirect(f"{redirect_base}?captcha=1")

        _clear_rate_limit_scope(ip_key)
        if email_key:
            _clear_rate_limit_scope(email_key)

        solicitacao = SolicitacaoPrivacidadeNewsletter.objects.create(
            email=email,
            tipo=tipo,
            status=SolicitacaoPrivacidadeNewsletter.STATUS_PENDENTE,
        )

        site = Site.find_for_request(request)
        config_site = ConfiguracaoSite.for_site(site) if site else None

        email_destino_admin = settings.DEFAULT_FROM_EMAIL
        if config_site and config_site.email_contato:
            email_destino_admin = config_site.email_contato

        assunto_admin = f"Nova solicitacao de privacidade - {pagina.title}"
        corpo_admin = (
            f"E-mail: {solicitacao.email}\n"
            f"Tipo: {solicitacao.get_tipo_display()}\n"
            f"Data: {solicitacao.criado_em}\n"
        )

        try:
            email_msg = EmailMessage(
                subject=assunto_admin,
                body=corpo_admin,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email_destino_admin],
                reply_to=[email],
            )
            email_msg.send(fail_silently=False)
        except Exception:
            forms_security_logger.error(
                "form_email_send_failed",
                extra={
                    "event": "form_email_send_failed",
                    "form": "newsletter_privacidade_admin",
                    "email": email,
                },
            )
            return redirect(f"{redirect_base}?privacidade_email_falhou=1")

        if tipo == SolicitacaoPrivacidadeNewsletter.TIPO_ACESSO:
            try:
                conteudo = solicitacao.gerar_csv_exportacao()
                nome_arquivo = solicitacao.nome_arquivo_exportacao()

                solicitacao.arquivo_exportacao.save(
                    nome_arquivo,
                    ContentFile(conteudo),
                    save=False,
                )
                solicitacao.status = SolicitacaoPrivacidadeNewsletter.STATUS_ATENDIDA
                solicitacao.atendida_em = timezone.now()
                solicitacao.executada_em = timezone.now()
                solicitacao.save()

                assunto_usuario = "Exportacao dos seus dados da newsletter"
                corpo_usuario = (
                    "O arquivo com os dados solicitados da newsletter segue em anexo.\n\n"
                    "Este arquivo será removido do servidor depois de alguns dias.\n"
                    "Se você precisar dele novamente no futuro, será necessário fazer uma nova solicitação.\n"
                )

                email_msg = EmailMessage(
                    subject=assunto_usuario,
                    body=corpo_usuario,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                email_msg.attach(nome_arquivo, conteudo, "text/csv")
                email_msg.send(fail_silently=False)

                return redirect(f"{redirect_base}?privacidade=1")
            except Exception:
                forms_security_logger.error(
                    "form_email_send_failed",
                    extra={
                        "event": "form_email_send_failed",
                        "form": "newsletter_privacidade_acesso",
                        "email": email,
                    },
                )
                return redirect(f"{redirect_base}?privacidade_email_falhou=1")

        token = gerar_token_privacidade(
            email=email,
            solicitacao_id=solicitacao.id,
            page_id=pagina.id,
            acao="confirmar_exclusao",
        )

        url_confirmacao = url_publica(
            request,
            f"/newsletter/{pagina.slug}/confirmar-exclusao-privacidade/{token}/",
            short_channel="email",
            short_title=f"Confirmação exclusão newsletter {pagina.title}",
            short_tags=["ownpaper", "newsletter", "email", "privacidade", "confirmacao"],
        )

        assunto_usuario = f"Confirme a exclusao dos seus dados - {pagina.title}"
        corpo_usuario = renderizar_email_html(
            request=request,
            titulo="Confirmação de exclusão de dados",
            mensagem_html=(
                "<p>Recebemos um pedido de exclusão dos seus dados da newsletter.</p>"
                f"<p>Após a confirmação, a exclusão ficará agendada por "
                f"{settings.NEWSLETTER_EXCLUSAO_GRACE_DAYS} dia(s), e você poderá cancelar "
                "antes da execução.</p>"
                "<p>Se você não fez esse pedido, ignore esta mensagem.</p>"
                f"<p style='word-break:break-word'><strong>Link alternativo:</strong> "
                f"<a href='{escape(url_confirmacao)}'>{escape(url_confirmacao)}</a></p>"
            ),
            botao_texto="Confirmar exclusão dos dados",
            botao_url=url_confirmacao,
        )

        try:
            email_msg = EmailMessage(
                subject=assunto_usuario,
                body=corpo_usuario,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email],
            )
            email_msg.content_subtype = "html"
            email_msg.send(fail_silently=False)
            return redirect(f"{redirect_base}?privacidade_confirmacao_exclusao_enviada=1")
        except Exception:
            forms_security_logger.error(
                "form_email_send_failed",
                extra={
                    "event": "form_email_send_failed",
                    "form": "newsletter_privacidade_exclusao",
                    "email": email,
                },
            )
            return redirect(f"{redirect_base}?privacidade_confirmacao_exclusao_email_falhou=1")

    return redirect(redirect_base)

def newsletter_confirmar_exclusao_privacidade(request, slug, token):
    pagina = get_object_or_404(NewsletterPage.objects.live(), slug=slug)
    redirect_base = _privacy_redirect_url(request, pagina)

    try:
        payload = ler_token_privacidade(token, "confirmar_exclusao")
    except signing.SignatureExpired:
        return redirect(f"{redirect_base}?privacidade_token_expirado=1")
    except signing.BadSignature:
        return redirect(f"{redirect_base}?privacidade_token_invalido=1")

    if payload.get("page_id") != pagina.id:
        return redirect(f"{redirect_base}?privacidade_token_invalido=1")

    email = (payload.get("email") or "").strip().lower()
    solicitacao_id = payload.get("solicitacao_id")

    if not email or not solicitacao_id:
        return redirect(f"{redirect_base}?privacidade_token_invalido=1")

    solicitacao = SolicitacaoPrivacidadeNewsletter.objects.filter(
        id=solicitacao_id,
        email__iexact=email,
        tipo=SolicitacaoPrivacidadeNewsletter.TIPO_EXCLUSAO,
    ).first()

    if not solicitacao:
        return redirect(f"{redirect_base}?privacidade_token_invalido=1")

    if solicitacao.executada_em:
        return redirect(f"{redirect_base}?privacidade_exclusao_confirmada=1")

    agora = timezone.now()
    executar_apos = agora + timedelta(days=settings.NEWSLETTER_EXCLUSAO_GRACE_DAYS)

    solicitacao.confirmacao_usuario_exclusao = True
    solicitacao.confirmacao_usuario_em = agora
    solicitacao.status = SolicitacaoPrivacidadeNewsletter.STATUS_ATENDIDA
    solicitacao.executar_apos_em = executar_apos

    observacao_confirmacao = "Exclusão confirmada pelo usuário via link enviado por e-mail."
    if solicitacao.observacoes:
        solicitacao.observacoes += f"\n{observacao_confirmacao}"
    else:
        solicitacao.observacoes = observacao_confirmacao

    solicitacao.save()

    token_cancelar = gerar_token_privacidade(
        email=email,
        solicitacao_id=solicitacao.id,
        page_id=pagina.id,
        acao="cancelar_exclusao",
    )
    url_cancelar = url_publica(
        request,
        f"/newsletter/{pagina.slug}/cancelar-exclusao-privacidade/{token_cancelar}/",
        short_channel="email",
        short_title=f"Cancelar exclusão newsletter {pagina.title}",
        short_tags=["ownpaper", "newsletter", "email", "privacidade", "cancelamento"],
    )
    data_limite = timezone.localtime(executar_apos).strftime("%d/%m/%Y %H:%M")

    assunto = f"Exclusao agendada - {pagina.title}"
    corpo = renderizar_email_html(
        request=request,
        titulo="Exclusão agendada",
        mensagem_html=(
            "<p>Seu pedido de exclusão foi confirmado.</p>"
            f"<p>A exclusão está agendada para <strong>{escape(data_limite)}</strong>.</p>"
            "<p>Se quiser cancelar esta solicitação antes da execução, use o botão abaixo.</p>"
            f"<p style='word-break:break-word'><strong>Link alternativo:</strong> "
            f"<a href='{escape(url_cancelar)}'>{escape(url_cancelar)}</a></p>"
        ),
        botao_texto="Cancelar solicitação de exclusão",
        botao_url=url_cancelar,
    )

    try:
        email_msg = EmailMessage(
            subject=assunto,
            body=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        email_msg.content_subtype = "html"
        email_msg.send(fail_silently=False)
        return redirect(f"{redirect_base}?privacidade_exclusao_agendada=1")
    except Exception:
        return redirect(f"{redirect_base}?privacidade_exclusao_agendada_email_falhou=1")


def newsletter_cancelar_exclusao_privacidade(request, slug, token):
    pagina = get_object_or_404(NewsletterPage.objects.live(), slug=slug)
    redirect_base = _privacy_redirect_url(request, pagina)

    try:
        payload = ler_token_privacidade(token, "cancelar_exclusao")
    except signing.SignatureExpired:
        return redirect(f"{redirect_base}?privacidade_token_expirado=1")
    except signing.BadSignature:
        return redirect(f"{redirect_base}?privacidade_token_invalido=1")

    if payload.get("page_id") != pagina.id:
        return redirect(f"{redirect_base}?privacidade_token_invalido=1")

    email = (payload.get("email") or "").strip().lower()
    solicitacao_id = payload.get("solicitacao_id")

    if not email or not solicitacao_id:
        return redirect(f"{redirect_base}?privacidade_token_invalido=1")

    solicitacao = SolicitacaoPrivacidadeNewsletter.objects.filter(
        id=solicitacao_id,
        email__iexact=email,
        tipo=SolicitacaoPrivacidadeNewsletter.TIPO_EXCLUSAO,
    ).first()

    if not solicitacao:
        return redirect(f"{redirect_base}?privacidade_token_invalido=1")

    if solicitacao.executada_em:
        return redirect(f"{redirect_base}?privacidade_exclusao_ja_executada=1")

    solicitacao.status = SolicitacaoPrivacidadeNewsletter.STATUS_NEGADA
    solicitacao.executar_apos_em = None
    observacao_cancelamento = "Solicitação de exclusão cancelada pelo usuário antes da execução."
    if solicitacao.observacoes:
        solicitacao.observacoes += f"\n{observacao_cancelamento}"
    else:
        solicitacao.observacoes = observacao_cancelamento
    solicitacao.save()

    return redirect(f"{redirect_base}?privacidade_exclusao_cancelada=1")

def filtrar_registros_indexador(
    termo="",
    ano_inicial="",
    ano_final="",
    ordenar="recentes",
    idioma_busca="pt-br",
    idiomas_busca_efetivos=None,
    termos_configurados=None,
    modo_expansao=None,
):
    ano_inicial = _normalizar_ano_filtro(ano_inicial)
    ano_final = _normalizar_ano_filtro(ano_final)
    if ano_inicial and ano_final and ano_inicial > ano_final:
        ano_inicial, ano_final = ano_final, ano_inicial

    registros = RegistroIndexador.objects.filter(ativo=True).prefetch_related("autores_registro")
    termos_busca = termos_configurados or []
    if not termos_busca and termo:
        termos_busca = [{"indice": 1, "termo": termo, "operador": "and"}]

    filtro = _combinar_filtros_busca(
        termos_busca,
        idioma_busca,
        ["pt-br"],
        _construir_filtro_indexador,
    )
    if filtro is not None:
        registros = registros.filter(filtro).distinct()

    if ano_inicial:
        registros = registros.filter(ano_publicacao__gte=ano_inicial)

    if ano_final:
        registros = registros.filter(ano_publicacao__lte=ano_final)

    if ordenar == "titulo_az":
        registros = registros.order_by("titulo")
    elif ordenar == "titulo_za":
        registros = registros.order_by("-titulo")
    elif ordenar == "antigos":
        registros = registros.order_by("ano_publicacao", "titulo")
    else:
        registros = registros.order_by("-ano_publicacao", "titulo")

    return registros

def indexador_registro_detalhe(request, page_slug, registro_slug):
    page = get_object_or_404(IndexadorPage.objects.live(), slug=page_slug)
    registro = get_object_or_404(
        RegistroIndexador.objects.prefetch_related("autores_registro"),
        slug=registro_slug,
        ativo=True,
    )

    return render(
        request,
        "conteudo/indexador_registro_detalhe.html",
        {
            "page": page,
            "registro": registro,
        },
    )

def indexador_exportar_csv(request, page_slug):
    page = get_object_or_404(IndexadorPage.objects.live(), slug=page_slug)

    termo = sanitizar_texto(request.GET.get("q", ""), multiline=False)
    ano_inicial = _normalizar_ano_filtro(request.GET.get("ano_inicial", ""))
    ano_final = _normalizar_ano_filtro(request.GET.get("ano_final", ""))
    ordenar = sanitizar_texto(request.GET.get("ordenar", "recentes"), multiline=False)
    escopo = sanitizar_texto(request.GET.get("escopo", "resultados"), multiline=False)
    idioma_busca = (getattr(request, "LANGUAGE_CODE", "") or "pt-br").strip().lower()
    termos_avancados = _extrair_termos_busca_avancada(request)
    termos_configurados = [item for item in termos_avancados if item["termo"]]
    if not termos_configurados and termo:
        termos_configurados = [{"indice": 1, "termo": termo, "operador": "and"}]

    if escopo == "todos":
        registros = RegistroIndexador.objects.filter(ativo=True).prefetch_related("autores_registro").order_by("titulo")
    else:
        registros = filtrar_registros_indexador(
            termo=termo,
            ano_inicial=ano_inicial,
            ano_final=ano_final,
            ordenar=ordenar,
            idioma_busca=idioma_busca,
            termos_configurados=termos_configurados,
        )

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="indexador.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "titulo",
        "ano_publicacao",
        "dados_editoriais",
        "resumo",
        "autores",
        "orcids",
        "palavras_chave",
        "doi",
        "url_acesso",
    ])

    for registro in registros:
        writer.writerow([
            registro.titulo,
            registro.ano_publicacao,
            registro.dados_editoriais,
            registro.resumo,
            registro.autores_formatados,
            registro.orcids_formatados,
            registro.palavras_chave,
            registro.doi,
            registro.url_acesso,
        ])

    return response

def richtext_para_html(valor):
    if not valor:
        return ""

    if hasattr(valor, "source"):
        return expand_db_html(valor.source)

    return str(valor)


def obter_valor_traduzido_para_pdf(page, field_name, idioma="pt-br", *, html=False):
    conteudo = page.resolve_content_language(idioma)
    original = conteudo.get(field_name, getattr(page, field_name, ""))

    if html:
        original_html = richtext_para_html(original)
        return original_html

    original_txt = "" if original is None else str(original)
    return original_txt


def normalizar_html_pdf(html):
    if not html:
        return ""

    # Remove seta de retorno que costuma aparecer em notas/referências
    html = html.replace("↩", "")

    # xhtml2pdf costuma lidar melhor com div do que com figure/figcaption
    html = re.sub(r"<figure([^>]*)>", r"<div\1>", html)
    html = html.replace("</figure>", "</div>")
    html = re.sub(r"<figcaption([^>]*)>", r"<div\1>", html)
    html = html.replace("</figcaption>", "</div>")

    return html


def normalizar_paragrafos_texto_pdf(html):
    if not html:
        return ""

    html = re.sub(r"<p([^>]*)>\s*(?:&nbsp;|\s|<br\s*/?>)*</p>", "", html, flags=re.IGNORECASE)

    def adicionar_recuo(match):
        attrs = match.group(1) or ""
        conteudo = match.group(2) or ""

        if 'class="pdf-nao-indent"' in attrs or "class='pdf-nao-indent'" in attrs:
            return match.group(0)

        sem_ancoras = re.sub(r"(?:\s*<a\s+name=\"[^\"]+\"[^>]*></a>\s*)+", "", conteudo, flags=re.IGNORECASE)
        if not re.sub(r"<[^>]+>", "", sem_ancoras).strip():
            return ""

        prefixo = ""
        restante = conteudo
        ancora_match = re.match(
            r"^((?:\s*<a\s+name=\"[^\"]+\"[^>]*></a>\s*)+)(.*)$",
            conteudo,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if ancora_match:
            prefixo = ancora_match.group(1)
            restante = ancora_match.group(2)
        estilo_recuo = "text-indent: 1.75em; margin-top: 0; margin-bottom: 0;"
        if re.search(r'\sstyle\s*=\s*"[^"]*"', attrs, flags=re.IGNORECASE):
            attrs = re.sub(
                r'(\sstyle\s*=\s*")([^"]*)(")',
                lambda m: f'{m.group(1)}{m.group(2).rstrip()} {estilo_recuo}{m.group(3)}',
                attrs,
                count=1,
                flags=re.IGNORECASE,
            )
        elif re.search(r"\sstyle\s*=\s*'[^']*'", attrs, flags=re.IGNORECASE):
            attrs = re.sub(
                r"(\sstyle\s*=\s*')([^']*)(')",
                lambda m: f"{m.group(1)}{m.group(2).rstrip()} {estilo_recuo}{m.group(3)}",
                attrs,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            attrs = f'{attrs} style="{estilo_recuo}"'

        return f"<p{attrs}>{prefixo}{restante}</p>"

    return re.sub(r"<p([^>]*)>(.*?)</p>", adicionar_recuo, html, flags=re.IGNORECASE | re.DOTALL)


def marcar_primeiro_paragrafo_apos_imagem_pdf(html):
    if not html:
        return ""

    def adicionar_classe(match):
        abertura_p = match.group(1)
        attrs = match.group(2) or ""

        if re.search(r'class\s*=\s*"[^"]*\bpdf-paragrafo-apos-imagem\b', attrs, flags=re.IGNORECASE):
            return abertura_p + attrs + ">"
        if re.search(r"class\s*=\s*'[^']*\bpdf-paragrafo-apos-imagem\b", attrs, flags=re.IGNORECASE):
            return abertura_p + attrs + ">"

        if re.search(r'\sclass\s*=\s*"[^"]*"', attrs, flags=re.IGNORECASE):
            attrs = re.sub(
                r'(\sclass\s*=\s*")([^"]*)(")',
                lambda m: f'{m.group(1)}{m.group(2).rstrip()} pdf-paragrafo-apos-imagem{m.group(3)}',
                attrs,
                count=1,
                flags=re.IGNORECASE,
            )
        elif re.search(r"\sclass\s*=\s*'[^']*'", attrs, flags=re.IGNORECASE):
            attrs = re.sub(
                r"(\sclass\s*=\s*')([^']*)(')",
                lambda m: f"{m.group(1)}{m.group(2).rstrip()} pdf-paragrafo-apos-imagem{m.group(3)}",
                attrs,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            attrs = f'{attrs} class="pdf-paragrafo-apos-imagem"'

        return abertura_p + attrs + ">"

    return re.sub(
        r'(<div class="pdf-imagem"><div class="pdf-imagem-bloco">.*?</div></div>\s*<p)([^>]*)>',
        adicionar_classe,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )


def normalizar_marcador_pdf(valor):
    return str(valor or "").strip().replace(" ", "-")


def converter_marcadores_ancora_pdf(html):
    if not html:
        return ""

    def substituir_ancora(match):
        marcador = normalizar_marcador_pdf(match.group(1))
        if not marcador:
            return ""
        return f'<a name="{marcador}" id="{marcador}"></a>'

    return re.sub(
        r"\[\[\s*a:\s*([^\]\|]+?)\s*\]\]",
        substituir_ancora,
        html,
        flags=re.IGNORECASE,
    )


def converter_urls_html_para_pdf(html, request=None):
    if not html:
        return ""

    media_url = settings.MEDIA_URL.rstrip("/")
    static_url = settings.STATIC_URL.rstrip("/")
    media_root = str(Path(settings.MEDIA_ROOT)).rstrip("/")
    static_root = str(Path(settings.STATIC_ROOT)).rstrip("/")

    html = html.replace(f'src="{media_url}/', f'src="file://{media_root}/')
    html = html.replace(f"src='{media_url}/", f"src='file://{media_root}/")
    html = html.replace(f'href="{media_url}/', f'href="file://{media_root}/')
    html = html.replace(f"href='{media_url}/", f"href='file://{media_root}/")

    html = html.replace(f'src="{static_url}/', f'src="file://{static_root}/')
    html = html.replace(f"src='{static_url}/", f"src='file://{static_root}/")
    html = html.replace(f'href="{static_url}/', f'href="file://{static_root}/')
    html = html.replace(f"href='{static_url}/", f"href='file://{static_root}/")

    if request:
        base_url = request.build_absolute_uri("/")
        html = re.sub(r'href="/(?!/)', f'href="{base_url}', html)
        html = re.sub(r"href='/(?!/)", f"href='{base_url}", html)

    return html


def obter_primeiro_campo_existente(obj, nomes):
    for nome in nomes:
        valor = getattr(obj, nome, "")
        if valor:
            return valor
    return ""


def pdf_link_callback(uri, rel):
    if uri.startswith("file://"):
        return uri.replace("file://", "", 1)

    if uri.startswith(settings.MEDIA_URL):
        return str(Path(settings.MEDIA_ROOT) / uri.replace(settings.MEDIA_URL, "", 1))

    if uri.startswith(settings.STATIC_URL):
        return str(Path(settings.STATIC_ROOT) / uri.replace(settings.STATIC_URL, "", 1))

    return uri


def gerar_qrcode_data_uri(valor):
    texto = (valor or "").strip()
    if not texto:
        return ""

    qr = qrcode.QRCode(
        version=1,
        box_size=6,
        border=2,
    )
    qr.add_data(texto)
    qr.make(fit=True)
    imagem = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    imagem.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def marcador_para_id(prefixo, marcador):
    valor = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(marcador or "").strip()).strip("-")
    if not valor:
        valor = "item"
    return f"{prefixo}-{valor}"


def formatar_referencia_pdf(ref):
    partes = []
    if ref.autores_formatados:
        partes.append(f"{ref.autores_formatados}.")

    titulo = ref.titulo_obra or ""
    if ref.subtitulo:
        titulo = f"{titulo}: {ref.subtitulo}"
    if titulo:
        partes.append(titulo + ".")

    if ref.tipo_midia:
        partes.append(f"{ref.tipo_midia}.")
    if ref.local_publicacao:
        partes.append(f"{ref.local_publicacao}:")
    if ref.editora:
        partes.append(f"{ref.editora},")
    if ref.ano:
        partes.append(f"{ref.ano}.")
    if ref.paginas:
        partes.append(f"{ref.paginas}.")

    texto = " ".join(partes).strip()
    return texto


def construir_corpo_pdf(page, request=None, idioma="pt-br"):
    html = obter_valor_traduzido_para_pdf(page, "corpo", idioma, html=True)
    html = converter_marcadores_ancora_pdf(html)

    notas = page.ordenar_complementos_publicacao(
        page.notas_rodape.all(),
        "n",
        page.ordenacao_notas_rodape,
        page.rotulo_ordenacao_nota,
    )
    refs = page.referencias_ordenadas
    imagens = list(page.imagens_publicacao.all())
    videos = list(page.midias_embed.all())

    notas_map = {}
    for indice, nota in enumerate(notas, start=1):
        marcadores = nota.marcadores_lista or [(nota.marcador or str(indice)).strip()]
        for marcador in marcadores:
            chave = normalizar_marcador_publicacao(marcador).lower()
            if chave:
                notas_map[chave] = marcador

    refs_map = {}
    for indice, ref in enumerate(refs, start=1):
        marcadores = ref.marcadores_lista or [(ref.marcador or str(indice)).strip()]
        for marcador in marcadores:
            chave = normalizar_marcador_publicacao(marcador).lower()
            if chave:
                refs_map[chave] = marcador

    imagens_map = {}
    for item in imagens:
        for marcador in item.marcadores_lista:
            chave = (marcador or "").strip()
            if chave:
                imagens_map[chave] = item

    videos_map = {}
    for item in videos:
        for marcador in item.marcadores_lista:
            chave = (marcador or "").strip()
            if chave:
                videos_map[chave] = item

    imagens_usadas = set()
    videos_usados = set()

    def render_imagem_pdf_por_marcador(marcador):
        item = imagens_map.get((marcador or "").strip())
        if not item:
            return ""

        imagens_usadas.add(item.id)
        if not item.imagem:
            return (
                '<div class="pdf-imagem">'
                '<div class="pdf-imagem-bloco pdf-imagem-pendente">'
                "Imagem aguardando aprovação editorial."
                "</div>"
                "</div>"
            )
        rendition = item.imagem.get_rendition("max-700x394")
        imagem_src = converter_urls_html_para_pdf(
            f'<img src="{rendition.url}" alt="{escape(item.titulo or "")}">',
            request=request,
        )
        legenda = escape(item.legenda or "")
        titulo = escape(item.titulo or "")

        legenda_html = ""
        if titulo or legenda:
            legenda_html = (
                '<div class="pdf-legenda">'
                + (f'<div class="pdf-legenda-titulo"><strong>{titulo}</strong></div>' if titulo else "")
                + (f'<div class="pdf-legenda-texto">{legenda}</div>' if legenda else "")
                + "</div>"
            )

        return f'<div class="pdf-imagem"><div class="pdf-imagem-bloco">{imagem_src}{legenda_html}</div></div>'

    def render_video_pdf_por_marcador(marcador):
        item = videos_map.get((marcador or "").strip())
        if not item:
            return ""

        videos_usados.add(item.id)
        url_bruta = item.video_publico_url(request)
        if not url_bruta:
            return (
                '<div class="pdf-video">'
                f'<div class="pdf-video-titulo">{escape(item.titulo or "Vídeo")}</div>'
                '<div class="pdf-video-url">Vídeo aguardando aprovação editorial.</div>'
                "</div>"
            )
        qr_data_uri = gerar_qrcode_data_uri(url_bruta)
        titulo = escape(item.titulo or "Vídeo")
        url_video = escape(url_bruta or "")
        return (
            '<div class="pdf-video">'
            f'<div class="pdf-video-titulo">{titulo}</div>'
            f'<img src="{qr_data_uri}" alt="QR code do vídeo">'
            f'<div class="pdf-video-url">{url_video}</div>'
            "</div>"
        )

    def sub_nota(match):
        marcador = (match.group(1) or "").strip()
        indice = notas_map.get(normalizar_marcador_publicacao(marcador).lower(), "?")
        if indice == "?":
            return f'<sup class="indice-nota">{indice}</sup>'
        destino = marcador_para_id("nota", indice)
        origem = marcador_para_id("nota-src", indice)
        return (
            f'<a name="{origem}"></a>'
            f'<sup class="indice-nota"><a href="#{destino}">{indice}</a></sup>'
        )

    def sub_ref(match):
        marcador = (match.group(1) or "").strip()
        indice = refs_map.get(normalizar_marcador_publicacao(marcador).lower(), "?")
        if indice == "?":
            return f'<sup class="indice-ref">{indice}</sup>'
        destino = marcador_para_id("ref", indice)
        origem = marcador_para_id("ref-src", indice)
        return (
            f'<a name="{origem}"></a>'
            f'<sup class="indice-ref"><a href="#{destino}">{indice}</a></sup>'
        )

    def sub_imagem(match):
        marcador = (match.group(1) or "").strip()
        return render_imagem_pdf_por_marcador(marcador)

    def sub_video(match):
        marcador = (match.group(1) or "").strip()
        return render_video_pdf_por_marcador(marcador)

    for marcador in imagens_map.keys():
        token = f"[[i:{marcador}]]"
        html = re.sub(
            rf"<p[^>]*>\s*{re.escape(token)}\s*</p>",
            render_imagem_pdf_por_marcador(marcador),
            html,
            flags=re.IGNORECASE,
        )

    for marcador in videos_map.keys():
        token = f"[[v:{marcador}]]"
        html = re.sub(
            rf"<p[^>]*>\s*{re.escape(token)}\s*</p>",
            render_video_pdf_por_marcador(marcador),
            html,
            flags=re.IGNORECASE,
        )

    html = re.sub(r"\[\[\s*n:\s*([^\]]+)\s*\]\]", sub_nota, html)
    html = re.sub(r"\[\[\s*r:\s*([^\]]+)\s*\]\]", sub_ref, html)
    html = re.sub(r"\[\[\s*i:\s*([^\]]+)\s*\]\]", sub_imagem, html)
    html = re.sub(r"\[\[\s*v:\s*([^\]]+)\s*\]\]", sub_video, html)

    corpo_html = converter_urls_html_para_pdf(normalizar_html_pdf(html), request=request)
    corpo_html = normalizar_paragrafos_texto_pdf(corpo_html)
    corpo_html = marcar_primeiro_paragrafo_apos_imagem_pdf(corpo_html)
    return mark_safe(corpo_html), imagens_usadas, videos_usados

def publicacao_pdf(request, page_id):
    page = get_object_or_404(
        PublicacaoPage.objects.live().public(),
        id=page_id,
    )
    site_lang = normalizar_codigo_idioma_manual(request.GET.get("idioma") or "pt-br")
    conteudo = page.resolve_content_language(site_lang)
    site_lang = conteudo["lang"]

    translated_page_title = conteudo["title"]
    translated_page_resumo = richtext_para_html(conteudo["resumo"])
    translated_page_palavras_chave = conteudo["palavras_chave"]

    resumo_html = converter_urls_html_para_pdf(
        normalizar_html_pdf(converter_marcadores_ancora_pdf(translated_page_resumo)),
        request=request,
    )
    resumo_html = normalizar_paragrafos_texto_pdf(resumo_html)
    corpo_html, imagens_usadas, videos_usados = construir_corpo_pdf(page, request=request, idioma=site_lang)

    referencias = page.referencias_ordenadas
    notas_rodape = page.resolve_footnotes_language(site_lang)
    imagens = list(page.imagens_publicacao.all())
    videos = list(page.midias_embed.all())

    imagens_adicionais = [item for item in imagens if item.id not in imagens_usadas]
    videos_adicionais = [item for item in videos if item.id not in videos_usados]

    for video in videos_adicionais:
        video_pdf_url = video.video_publico_url(request)
        video.qr_data_uri = gerar_qrcode_data_uri(video_pdf_url) if video_pdf_url else ""
        video.pdf_url = video_pdf_url

    notas_formatadas = []
    for indice, nota in enumerate(notas_rodape, start=1):
        marcador_display = str(nota.get("marker") or "").strip()
        marcador_base = marcador_display or str(indice)
        notas_formatadas.append(
            {
                "marcador_display": marcador_display,
                "marcador_base": marcador_base,
                "marcadores": nota.get("markers") or [marcador_base],
                "marcadores_display": nota.get("markers_display") or marcador_display,
                "anchor_id": marcador_para_id("nota", marcador_base),
                "anchor_src_id": marcador_para_id("nota-src", marcador_base),
                "conteudo_html": mark_safe(
                    converter_urls_html_para_pdf(
                        normalizar_html_pdf(richtext_para_html(nota.get("content"))),
                        request=request,
                    )
                ),
            }
        )

    referencias_formatadas = []
    for indice, ref in enumerate(referencias, start=1):
        marcadores = ref.marcadores_lista
        marcador_display = (marcadores[0] if marcadores else ref.marcador or "").strip()
        marcador_base = marcador_display or str(indice)
        referencias_formatadas.append(
            {
                "marcador_display": marcador_display,
                "marcador_base": marcador_base,
                "marcadores": marcadores or [marcador_base],
                "marcadores_display": ref.marcadores_display or marcador_display,
                "anchor_id": marcador_para_id("ref", marcador_base),
                "anchor_src_id": marcador_para_id("ref-src", marcador_base),
                "texto": formatar_referencia_pdf(ref),
                "url": ref.url,
                "observacoes": ref.observacoes,
            }
        )

    creditos_videos = page.videos_com_credito
    creditos_imagens = page.imagens_com_credito

    html = render_to_string(
        "conteudo/publicacao_pdf.html",
        {
            "page": page,
            "site_lang": site_lang,
            "translated_page_title": translated_page_title,
            "translated_page_palavras_chave": translated_page_palavras_chave,
            "url_publica": request.build_absolute_uri(page.url),
            "site_base_url": request.build_absolute_uri("/").rstrip("/"),
            "qr_publicacao_data_uri": gerar_qrcode_data_uri(request.build_absolute_uri(page.url)),
            "resumo_html": mark_safe(resumo_html),
            "corpo_html": corpo_html,
            "imagens_adicionais": imagens_adicionais,
            "videos_adicionais": videos_adicionais,
            "notas_rodape": notas_formatadas,
            "referencias": referencias_formatadas,
            "creditos_videos": creditos_videos,
            "creditos_imagens": creditos_imagens,
            "autores": page.autores_ordenados,
        },
        request=request,
    )

    resultado = BytesIO()
    pdf = pisa.CreatePDF(
        html,
        dest=resultado,
        link_callback=pdf_link_callback,
    )

    if pdf.err:
        return HttpResponse("Erro ao gerar PDF.", status=500)

    response = HttpResponse(
        resultado.getvalue(),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'inline; filename="publicacao-{page.id}.pdf"'
    return response


def _quiz_usuario_autenticado(request):
    return _usuario_comentario_cookie(request)


def comentario_login_solicitar_codigo(request, page_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Método inválido.")

    publicacao = get_object_or_404(PublicacaoPage.objects.live(), id=page_id)
    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None
    if not _acesso_identidade_publicacao_habilitado(publicacao, config_site):
        return redirect(f"{publicacao.url}#comentarios")

    email = sanitizar_texto(request.POST.get("email", ""), multiline=False).lower()
    if not email:
        return redirect(f"{publicacao.url}?comentario=login_campos#comentarios")
    try:
        validate_email(email)
    except ValidationError:
        return redirect(f"{publicacao.url}?comentario=erro_email#comentarios")

    usuario = UsuarioComentario.objects.filter(email__iexact=email).first()
    if not usuario:
        return redirect(f"{publicacao.url}?comentario=login_nao_encontrado#comentarios")

    codigo = _gerar_codigo_6()
    acesso = ComentarioAcessoCodigo.objects.create(
        publicacao=publicacao,
        fluxo=ComentarioAcessoCodigo.FLUXO_LOGIN,
        codigo=codigo,
        email=usuario.email,
        username=usuario.username,
        nome=usuario.nome,
        orcid=usuario.orcid,
        usuario=usuario,
        expira_em=timezone.now() + timedelta(minutes=15),
    )
    assunto = f"Código de acesso para comentários - {(getattr(config_site, 'nome_site', '') or 'OwnPaper')}"
    corpo = (
        f"Seu código de acesso é: {codigo}\n\n"
        "Esse código expira em 15 minutos.\n"
        "Se você não solicitou, ignore este e-mail.\n"
    )
    try:
        EmailMessage(
            subject=assunto,
            body=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[usuario.email],
        ).send(fail_silently=False)
    except Exception:
        acesso.delete()
        return redirect(f"{publicacao.url}?comentario=erro_envio_email#comentarios")

    request.session["comentario_auth_pending"] = {
        "token": str(acesso.token),
        "flow": "login",
        "masked_email": _mascarar_email(usuario.email),
        "page_id": publicacao.id,
    }
    return redirect(f"{publicacao.url}?comentario=codigo_enviado#comentarios")


def comentario_cadastro_solicitar_codigo(request, page_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Método inválido.")

    publicacao = get_object_or_404(PublicacaoPage.objects.live(), id=page_id)
    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None
    if not _acesso_identidade_publicacao_habilitado(publicacao, config_site):
        return redirect(f"{publicacao.url}#comentarios")

    nome = sanitizar_texto(request.POST.get("nome", ""), multiline=False)
    sobrenome = sanitizar_texto(request.POST.get("sobrenome", ""), multiline=False)
    nome_completo = _montar_nome_completo(nome, sobrenome)
    username = normalizar_username_publico(request.POST.get("username", ""))
    email = sanitizar_texto(request.POST.get("email", ""), multiline=False).lower()
    orcid = sanitizar_texto(request.POST.get("orcid", ""), multiline=False).strip()
    aceitou_privacidade = str(request.POST.get("aceitou_privacidade_cadastro", "")).strip().lower() in {"1", "true", "on"}

    if not nome or not sobrenome or not username or not email:
        return redirect(f"{publicacao.url}?comentario=cadastro_campos#comentarios")
    if not aceitou_privacidade:
        return redirect(f"{publicacao.url}?comentario=privacidade#comentarios")
    try:
        validate_email(email)
    except ValidationError:
        return redirect(f"{publicacao.url}?comentario=erro_email#comentarios")

    orcid_normalizado = _normalizar_orcid(orcid) if orcid else ""
    if orcid and not orcid_normalizado:
        return redirect(f"{publicacao.url}?comentario=erro_orcid#comentarios")

    erro_conflito, _usuario_email, _usuario_username, _usuario_orcid = _resolver_conflitos_usuario_comentario(
        email=email,
        username=username,
        orcid=orcid_normalizado,
    )
    if erro_conflito:
        if erro_conflito in {"erro_usuario_email", "erro_usuario_duplicado", "erro_identidade_conflito", "erro_orcid_duplicado"}:
            return redirect(f"{publicacao.url}?comentario={erro_conflito}#comentarios")
        return redirect(f"{publicacao.url}?comentario=erro_orcid#comentarios")

    codigo = _gerar_codigo_6()
    acesso = ComentarioAcessoCodigo.objects.create(
        publicacao=publicacao,
        fluxo=ComentarioAcessoCodigo.FLUXO_CADASTRO,
        codigo=codigo,
        email=email,
        username=username,
        nome=nome_completo,
        orcid=orcid_normalizado or "",
        expira_em=timezone.now() + timedelta(minutes=15),
    )
    assunto = f"Código de confirmação do cadastro - {(getattr(config_site, 'nome_site', '') or 'OwnPaper')}"
    corpo = (
        f"Seu código de confirmação é: {codigo}\n\n"
        "Esse código expira em 15 minutos.\n"
        "Após confirmar, você poderá comentar com seu usuário.\n"
    )
    try:
        EmailMessage(
            subject=assunto,
            body=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        ).send(fail_silently=False)
    except Exception:
        acesso.delete()
        return redirect(f"{publicacao.url}?comentario=erro_envio_email#comentarios")

    request.session["comentario_auth_pending"] = {
        "token": str(acesso.token),
        "flow": "cadastro",
        "masked_email": _mascarar_email(email),
        "page_id": publicacao.id,
    }
    return redirect(f"{publicacao.url}?comentario=cadastro_codigo_enviado#comentarios")


def comentario_confirmar_codigo(request, page_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Método inválido.")

    publicacao = get_object_or_404(PublicacaoPage.objects.live(), id=page_id)
    pending = request.session.get("comentario_auth_pending") or {}
    if str(pending.get("page_id")) != str(publicacao.id):
        return redirect(f"{publicacao.url}?comentario=token_invalido#comentarios")

    token = str((pending.get("token") or "")).strip()
    codigo = sanitizar_texto(request.POST.get("codigo", ""))
    if not token or not codigo:
        return redirect(f"{publicacao.url}?comentario=codigo_invalido#comentarios")

    acesso = ComentarioAcessoCodigo.objects.filter(token=token).first()
    if not acesso or not acesso.valido or acesso.publicacao_id != publicacao.id:
        request.session.pop("comentario_auth_pending", None)
        return redirect(f"{publicacao.url}?comentario=token_invalido#comentarios")
    if acesso.codigo != codigo:
        return redirect(f"{publicacao.url}?comentario=codigo_invalido#comentarios")

    if acesso.fluxo == ComentarioAcessoCodigo.FLUXO_LOGIN:
        usuario = acesso.usuario
    else:
        usuario = UsuarioComentario.objects.filter(email__iexact=acesso.email).first()
        if not usuario:
            usuario = UsuarioComentario.objects.create(
                nome=acesso.nome,
                email=(acesso.email or "").lower(),
                username=acesso.username,
                orcid=acesso.orcid,
            )
        site = Site.find_for_request(request)
        config_site = ConfiguracaoSite.for_site(site) if site else None
        _registrar_newsletter_comentario(config_site, usuario.email)

    if not usuario:
        return redirect(f"{publicacao.url}?comentario=token_invalido#comentarios")

    acesso.usado_em = timezone.now()
    acesso.save(update_fields=["usado_em"])
    request.session.pop("comentario_auth_pending", None)
    response = redirect(f"{publicacao.url}?comentario=login_ok#comentarios")
    _definir_cookie_usuario_comentario(response, request, usuario)
    return response


def comentario_enviar(request, page_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Método inválido.")

    publicacao = get_object_or_404(PublicacaoPage.objects.live(), id=page_id)
    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None
    if not config_site or not config_site.comentarios_ativos or not publicacao.comentarios_habilitados:
        return redirect(f"{publicacao.url}#comentarios")

    usuario = _usuario_comentario_cookie(request)
    if not usuario:
        return redirect(f"{publicacao.url}?comentario=login_necessario#comentarios")

    texto = sanitizar_texto(request.POST.get("texto", ""), multiline=True)
    if not texto:
        return redirect(f"{publicacao.url}?comentario=erro_campos#comentarios")

    comentario_pai = None
    comentario_pai_id = (request.POST.get("comentario_pai") or "").strip()
    if comentario_pai_id:
        comentario_pai = ComentarioPublicacao.objects.filter(
            publicacao=publicacao,
            id=comentario_pai_id,
            status=ComentarioPublicacao.STATUS_APROVADO,
        ).first()
        if not comentario_pai:
            return redirect(f"{publicacao.url}?comentario=erro_comentario_pai#comentarios")

    sinalizado = _texto_suspeito_para_moderacao(texto) or _texto_publico_contem_risco(texto)
    status = ComentarioPublicacao.STATUS_PENDENTE if sinalizado else ComentarioPublicacao.STATUS_APROVADO
    ComentarioPublicacao.objects.create(
        publicacao=publicacao,
        usuario=usuario,
        comentario_pai=comentario_pai,
        texto=texto,
        status=status,
        sinalizado_conteudo=sinalizado,
        ip_origem=_ip_da_requisicao_view(request) or None,
    )
    _registrar_newsletter_comentario(config_site, usuario.email)
    resultado = "enviado_moderacao" if status == ComentarioPublicacao.STATUS_PENDENTE else "enviado_publicado"
    return redirect(f"{publicacao.url}?comentario={resultado}#comentarios")


def comentario_logout(request, page_id):
    publicacao = get_object_or_404(PublicacaoPage.objects.live(), id=page_id)
    request.session.pop("comentario_auth_pending", None)
    response = redirect(f"{publicacao.url}#comentarios")
    response.delete_cookie("ownpaper_comment_auth", path="/")
    return response


def comentario_oauth_iniciar(request, page_id, provider):
    publicacao = get_object_or_404(PublicacaoPage.objects.live(), id=page_id)
    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None
    if not _acesso_identidade_publicacao_habilitado(publicacao, config_site):
        return redirect(f"{publicacao.url}#comentarios")
    if not oauth_provider_enabled(config_site, provider):
        return redirect(f"{publicacao.url}?comentario=oauth_nao_configurado#comentarios")

    state = secrets.token_urlsafe(24)
    request.session["comentario_oauth_state"] = {
        "provider": provider,
        "state": state,
        "page_id": publicacao.id,
    }
    url = oauth_build_authorize_url(
        config_site,
        provider,
        _oauth_redirect_uri(request, "comentario_oauth_callback", provider),
        state,
    )
    return HttpResponseRedirect(url)


def comentario_oauth_callback(request, provider):
    state_data = request.session.get("comentario_oauth_state") or {}
    page_id = state_data.get("page_id")
    if not page_id or state_data.get("provider") != provider:
        return render(
            request,
            "conteudo/comentario_oauth_popup.html",
            {
                "status": "erro",
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "mensagem": "Estado OAuth inválido.",
                "publicacao": None,
            },
            status=400,
        )

    publicacao = get_object_or_404(PublicacaoPage.objects.live(), id=page_id)
    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None
    if not oauth_provider_enabled(config_site, provider):
        return render(
            request,
            "conteudo/comentario_oauth_popup.html",
            {
                "status": "erro",
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "mensagem": "Provider OAuth não configurado.",
                "publicacao": publicacao,
            },
            status=400,
        )

    recebido_state = (request.GET.get("state") or "").strip()
    code = (request.GET.get("code") or "").strip()
    provider_error = (request.GET.get("error") or "").strip()
    if recebido_state != (state_data.get("state") or "") or provider_error or not code:
        request.session.pop("comentario_oauth_state", None)
        return render(
            request,
            "conteudo/comentario_oauth_popup.html",
            {
                "status": "erro",
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "mensagem": "Não foi possível concluir a autenticação externa.",
                "publicacao": publicacao,
            },
            status=400,
        )

    try:
        token_data = oauth_exchange_code(
            config_site,
            provider,
            code,
            _oauth_redirect_uri(request, "comentario_oauth_callback", provider),
        )
        profile = oauth_fetch_profile(config_site, provider, token_data)
    except Exception:
        request.session.pop("comentario_oauth_state", None)
        return render(
            request,
            "conteudo/comentario_oauth_popup.html",
            {
                "status": "erro",
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "mensagem": "Falha ao obter os dados do provedor.",
                "publicacao": publicacao,
            },
            status=400,
        )

    if not (profile.get("provider_user_id") or "").strip():
        request.session.pop("comentario_oauth_state", None)
        return render(
            request,
            "conteudo/comentario_oauth_popup.html",
            {
                "status": "erro",
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "mensagem": "O provedor não retornou um identificador válido.",
                "publicacao": publicacao,
            },
            status=400,
        )

    usuario, _identidade = _resolver_usuario_oauth(profile)
    if usuario:
        return _finalizar_login_oauth(request, publicacao, config_site, usuario, profile)

    pending = {
        "page_id": publicacao.id,
        "provider": provider,
        "provider_user_id": profile.get("provider_user_id") or "",
        "provider_username": profile.get("provider_username") or "",
        "display_name": profile.get("display_name") or "",
        "email": profile.get("email") or "",
        "email_verified": bool(profile.get("email_verified")),
        "profile_url": profile.get("profile_url") or "",
        "avatar_url": profile.get("avatar_url") or "",
        "scopes": profile.get("scopes") or "",
        "orcid": profile.get("orcid") or "",
        "suggested_username": profile.get("suggested_username") or "",
        "raw": profile.get("raw") or {},
    }
    request.session["comentario_oauth_pending"] = pending
    nome_default, sobrenome_default = _split_nome_partes(profile.get("display_name") or "")
    return render(
        request,
        "conteudo/comentario_oauth_concluir.html",
        {
            "publicacao": publicacao,
            "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
            "provider_label": oauth_provider_label(provider),
            "pending": pending,
            "config_site": config_site,
            "valores": {
                "nome": nome_default,
                "sobrenome": sobrenome_default,
                "username": profile.get("suggested_username") or "",
                "email": profile.get("email") or "",
            },
        },
    )


def comentario_oauth_concluir(request, page_id):
    publicacao = get_object_or_404(PublicacaoPage.objects.live(), id=page_id)
    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None
    pending = request.session.get("comentario_oauth_pending") or {}
    provider = pending.get("provider") or "oauth"
    if str(pending.get("page_id")) != str(publicacao.id):
        return render(
            request,
            "conteudo/comentario_oauth_popup.html",
            {
                "status": "erro",
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "mensagem": "Sessão de vínculo expirada.",
                "publicacao": publicacao,
            },
            status=400,
        )

    nome_default, sobrenome_default = _split_nome_partes(pending.get("display_name") or "")
    if request.method != "POST":
        return render(
            request,
            "conteudo/comentario_oauth_concluir.html",
            {
                "publicacao": publicacao,
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "pending": pending,
                "config_site": config_site,
                "valores": {
                    "nome": nome_default,
                    "sobrenome": sobrenome_default,
                    "username": pending.get("suggested_username") or "",
                    "email": pending.get("email") or "",
                },
            },
        )

    nome = sanitizar_texto(request.POST.get("nome", ""), multiline=False)
    sobrenome = sanitizar_texto(request.POST.get("sobrenome", ""), multiline=False)
    nome_completo = _montar_nome_completo(nome, sobrenome)
    username = normalizar_username_publico(request.POST.get("username", ""))
    email_padrao = sanitizar_texto(pending.get("email") or "", multiline=False).lower()
    email = sanitizar_texto(request.POST.get("email", email_padrao), multiline=False).lower()
    orcid = sanitizar_texto(request.POST.get("orcid", pending.get("orcid") or ""), multiline=False).strip()
    aceitou_privacidade = str(request.POST.get("aceitou_privacidade_cadastro", "")).strip().lower() in {"1", "true", "on"}

    erro = ""
    valores = {
        "nome": nome,
        "sobrenome": sobrenome,
        "username": username,
        "email": email,
        "orcid": orcid,
    }
    if not nome or not sobrenome or not username or not email:
        erro = "campos"
    elif not aceitou_privacidade:
        erro = "privacidade"
    else:
        try:
            validate_email(email)
        except ValidationError:
            erro = "email"

    orcid_normalizado = _normalizar_orcid(orcid) if orcid else ""
    if not erro and orcid and not orcid_normalizado:
        erro = "usuario"

    erro_conflito, usuario_email, usuario_username, usuario_orcid = ("", None, None, None)
    if not erro:
        erro_conflito, usuario_email, usuario_username, usuario_orcid = _resolver_conflitos_usuario_comentario(
            email=email,
            username=username,
            orcid=orcid_normalizado,
        )
        if erro_conflito:
            erro = "usuario"

    if erro:
        return render(
            request,
            "conteudo/comentario_oauth_concluir.html",
            {
                "publicacao": publicacao,
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "pending": pending,
                "erro": erro,
                "config_site": config_site,
                "valores": valores,
            },
        )

    usuario = usuario_email or usuario_username or usuario_orcid
    if usuario:
        alterou = False
        if nome_completo and usuario.nome != nome_completo:
            usuario.nome = nome_completo
            alterou = True
        if orcid_normalizado and usuario.orcid != orcid_normalizado:
            usuario.orcid = orcid_normalizado
            alterou = True
        if alterou:
            usuario.save(update_fields=["nome", "orcid", "atualizado_em"])
    else:
        usuario = UsuarioComentario.objects.create(
            nome=nome_completo,
            email=email,
            username=username,
            orcid=orcid_normalizado or "",
        )

    profile = {
        "provider": provider,
        "provider_user_id": pending.get("provider_user_id") or "",
        "provider_username": pending.get("provider_username") or "",
        "display_name": pending.get("display_name") or nome_completo,
        "email": email,
        "email_verified": bool(pending.get("email_verified")),
        "profile_url": pending.get("profile_url") or "",
        "avatar_url": pending.get("avatar_url") or "",
        "scopes": pending.get("scopes") or "",
        "orcid": pending.get("orcid") or "",
        "raw": pending.get("raw") or {},
    }
    return _finalizar_login_oauth(request, publicacao, config_site, usuario, profile)


def comentario_solicitar_verificacao(request, page_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Método inválido.")

    publicacao = get_object_or_404(PublicacaoPage.objects.live(), id=page_id)
    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None
    if not config_site or not config_site.comentarios_ativos or not publicacao.comentarios_habilitados:
        return redirect(f"{publicacao.url}#comentarios")

    email = sanitizar_texto(request.POST.get("email", ""), multiline=False).lower()
    username = normalizar_username_publico(request.POST.get("username", ""))
    orcid = sanitizar_texto(request.POST.get("orcid", ""), multiline=False).strip()
    texto = sanitizar_texto(request.POST.get("texto", ""), multiline=True)
    if not email or not username or not texto:
        return redirect(f"{publicacao.url}?comentario=erro_campos#comentarios")
    try:
        validate_email(email)
    except ValidationError:
        return redirect(f"{publicacao.url}?comentario=erro_email#comentarios")

    orcid_normalizado = _normalizar_orcid(orcid) if orcid else ""
    if orcid and not orcid_normalizado:
        return redirect(f"{publicacao.url}?comentario=erro_orcid#comentarios")

    erro_conflito, _usuario_email, _usuario_username, _usuario_orcid = _resolver_conflitos_usuario_comentario(
        email=email,
        username=username,
        orcid=orcid_normalizado,
    )
    if erro_conflito:
        return redirect(f"{publicacao.url}?comentario={erro_conflito}#comentarios")

    token = ComentarioVerificacaoToken.objects.create(
        publicacao=publicacao,
        email=email,
        username=username,
        orcid=orcid_normalizado or "",
        texto=texto,
        expira_em=timezone.now() + timedelta(minutes=30),
    )
    link = request.build_absolute_uri(f"/comentarios/confirmar/{token.token}/")
    assunto = f"Confirme seu comentário em {(getattr(config_site, 'nome_site', '') or 'OwnPaper')}"
    corpo = (
        "Recebemos sua solicitação de comentário.\n\n"
        f"Para confirmar, clique no link abaixo (válido por 30 minutos):\n{link}\n\n"
        "Após confirmação, o comentário ficará pendente de moderação.\n"
    )
    try:
        EmailMessage(
            subject=assunto,
            body=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        ).send(fail_silently=False)
    except Exception:
        token.delete()
        return redirect(f"{publicacao.url}?comentario=erro_envio_email#comentarios")
    return redirect(f"{publicacao.url}?comentario=verificacao_enviada#comentarios")


def comentario_confirmar_verificacao(request, token):
    token_obj = get_object_or_404(ComentarioVerificacaoToken, token=token)
    if token_obj.usado_em or token_obj.expira_em < timezone.now():
        return redirect(f"{token_obj.publicacao.url}?comentario=token_invalido#comentarios")

    with transaction.atomic():
        usuario, criado = UsuarioComentario.objects.get_or_create(
            email=token_obj.email.lower(),
            defaults={
                "username": token_obj.username,
                "orcid": token_obj.orcid,
            },
        )
        alterou = False
        if not criado and token_obj.orcid and usuario.orcid != token_obj.orcid:
            usuario.orcid = token_obj.orcid
            alterou = True
        if alterou:
            usuario.save(update_fields=["orcid", "atualizado_em"])

        sinalizado = _texto_suspeito_para_moderacao(token_obj.texto) or _texto_publico_contem_risco(token_obj.texto)
        status = ComentarioPublicacao.STATUS_PENDENTE if sinalizado else ComentarioPublicacao.STATUS_APROVADO
        ComentarioPublicacao.objects.create(
            publicacao=token_obj.publicacao,
            usuario=usuario,
            texto=token_obj.texto,
            status=status,
            sinalizado_conteudo=sinalizado,
            ip_origem=_ip_da_requisicao_view(request) or None,
        )

        site = Site.find_for_request(request)
        config_site = ConfiguracaoSite.for_site(site) if site else None
        if config_site and config_site.comentarios_auto_newsletter:
            inscrito, _ = InscritoNewsletter.objects.update_or_create(
                email=token_obj.email.lower(),
                defaults={
                    "ativo": True,
                    "consentimento": True,
                    "origem": "comentarios",
                    "confirmado_em": timezone.now(),
                },
            )
            if inscrito.ativo and inscrito.consentimento:
                pass

        token_obj.usado_em = timezone.now()
        token_obj.save(update_fields=["usado_em"])

    resultado = "enviado_moderacao" if status == ComentarioPublicacao.STATUS_PENDENTE else "enviado_publicado"
    return redirect(f"{token_obj.publicacao.url}?comentario={resultado}#comentarios")


def quiz_login_solicitar_codigo(request, page_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Método inválido.")

    page = get_object_or_404(QuizEstudoPage.objects.live().public(), id=page_id)
    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None

    email = sanitizar_texto(request.POST.get("email", ""), multiline=False).lower()
    if not email:
        return _quiz_redirect(page, "login_campos")
    try:
        validate_email(email)
    except ValidationError:
        return _quiz_redirect(page, "erro_email")

    usuario = UsuarioComentario.objects.filter(email__iexact=email).first()
    if not usuario:
        return _quiz_redirect(page, "login_nao_encontrado")

    codigo = _gerar_codigo_6()
    acesso = QuizAcessoCodigo.objects.create(
        pagina=page,
        codigo=codigo,
        email=usuario.email,
        usuario=usuario,
        expira_em=timezone.now() + timedelta(minutes=15),
    )
    assunto = f"Código de acesso ao quiz - {(getattr(config_site, 'nome_site', '') or 'OwnPaper')}"
    corpo = (
        f"Seu código de acesso é: {codigo}\n\n"
        "Esse código expira em 15 minutos.\n"
        "Se você não solicitou, ignore este e-mail.\n"
    )
    try:
        EmailMessage(
            subject=assunto,
            body=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[usuario.email],
        ).send(fail_silently=False)
    except Exception:
        acesso.delete()
        return _quiz_redirect(page, "erro_envio_email")

    request.session["quiz_auth_pending"] = {
        "token": str(acesso.token),
        "flow": "login",
        "masked_email": _mascarar_email(usuario.email),
        "page_id": page.id,
    }
    return _quiz_redirect(page, "codigo_enviado")


def quiz_cadastro_solicitar_codigo(request, page_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Método inválido.")

    page = get_object_or_404(QuizEstudoPage.objects.live().public(), id=page_id)
    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None

    nome = sanitizar_texto(request.POST.get("nome", ""), multiline=False)
    sobrenome = sanitizar_texto(request.POST.get("sobrenome", ""), multiline=False)
    nome_completo = _montar_nome_completo(nome, sobrenome)
    username = normalizar_username_publico(request.POST.get("username", ""))
    email = sanitizar_texto(request.POST.get("email", ""), multiline=False).lower()
    orcid = sanitizar_texto(request.POST.get("orcid", ""), multiline=False).strip()
    aceitou_privacidade = str(request.POST.get("aceitou_privacidade_cadastro", "")).strip().lower() in {"1", "true", "on"}

    if not nome or not sobrenome or not username or not email:
        return _quiz_redirect(page, "cadastro_campos")
    if not aceitou_privacidade:
        return _quiz_redirect(page, "privacidade")
    try:
        validate_email(email)
    except ValidationError:
        return _quiz_redirect(page, "erro_email")

    orcid_normalizado = _normalizar_orcid(orcid) if orcid else ""
    if orcid and not orcid_normalizado:
        return _quiz_redirect(page, "erro_orcid")

    erro_conflito, _usuario_email, _usuario_username, _usuario_orcid = _resolver_conflitos_usuario_comentario(
        email=email,
        username=username,
        orcid=orcid_normalizado,
    )
    if erro_conflito:
        return _quiz_redirect(page, erro_conflito)

    codigo = _gerar_codigo_6()
    acesso = QuizAcessoCodigo.objects.create(
        pagina=page,
        codigo=codigo,
        email=email,
        usuario=None,
        expira_em=timezone.now() + timedelta(minutes=15),
    )
    assunto = f"Código de confirmação do cadastro do quiz - {(getattr(config_site, 'nome_site', '') or 'OwnPaper')}"
    corpo = (
        f"Seu código de confirmação é: {codigo}\n\n"
        "Esse código expira em 15 minutos.\n"
        "Após confirmar, você poderá salvar seu histórico do quiz.\n"
    )
    try:
        EmailMessage(
            subject=assunto,
            body=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        ).send(fail_silently=False)
    except Exception:
        acesso.delete()
        return _quiz_redirect(page, "erro_envio_email")

    request.session["quiz_auth_pending"] = {
        "token": str(acesso.token),
        "flow": "cadastro",
        "masked_email": _mascarar_email(email),
        "page_id": page.id,
        "nome": nome_completo,
        "username": username,
        "orcid": orcid_normalizado or "",
        "email": email,
    }
    return _quiz_redirect(page, "cadastro_codigo_enviado")


def quiz_confirmar_codigo(request, page_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Método inválido.")

    page = get_object_or_404(QuizEstudoPage.objects.live().public(), id=page_id)
    pending = request.session.get("quiz_auth_pending") or {}
    if str(pending.get("page_id")) != str(page.id):
        return _quiz_redirect(page, "token_invalido")

    token = str((pending.get("token") or "")).strip()
    codigo = sanitizar_texto(request.POST.get("codigo", ""))
    if not token or not codigo:
        return _quiz_redirect(page, "codigo_invalido")

    acesso = QuizAcessoCodigo.objects.filter(token=token).first()
    if not acesso or not acesso.valido or acesso.pagina_id != page.id:
        request.session.pop("quiz_auth_pending", None)
        return _quiz_redirect(page, "token_invalido")
    if acesso.codigo != codigo:
        return _quiz_redirect(page, "codigo_invalido")

    if pending.get("flow") == "cadastro":
        usuario = UsuarioComentario.objects.filter(email__iexact=pending.get("email") or "").first()
        if not usuario:
            usuario = UsuarioComentario.objects.create(
                nome=pending.get("nome") or "",
                email=(pending.get("email") or "").lower(),
                username=pending.get("username") or "",
                orcid=pending.get("orcid") or "",
            )
    else:
        usuario = acesso.usuario

    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None
    _registrar_newsletter_comentario(config_site, usuario.email)

    acesso.usado_em = timezone.now()
    acesso.save(update_fields=["usado_em"])
    request.session.pop("quiz_auth_pending", None)
    response = _quiz_redirect(page, "login_ok")
    _definir_cookie_usuario_comentario(response, request, usuario)
    return response


def quiz_logout(request, page_id):
    page = get_object_or_404(QuizEstudoPage.objects.live().public(), id=page_id)
    request.session.pop("quiz_auth_pending", None)
    response = redirect(page.url)
    response.delete_cookie("ownpaper_comment_auth", path="/")
    return response


def quiz_oauth_iniciar(request, page_id, provider):
    page = get_object_or_404(QuizEstudoPage.objects.live().public(), id=page_id)
    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None
    if not oauth_provider_enabled(config_site, provider):
        return _quiz_redirect(page, "oauth_nao_configurado")

    state = secrets.token_urlsafe(24)
    request.session["quiz_oauth_state"] = {
        "provider": provider,
        "state": state,
        "page_id": page.id,
    }
    url = oauth_build_authorize_url(
        config_site,
        provider,
        _oauth_redirect_uri(request, "quiz_oauth_callback", provider),
        state,
    )
    return redirect(url)


def quiz_oauth_callback(request, provider):
    state_data = request.session.get("quiz_oauth_state") or {}
    page_id = state_data.get("page_id")
    if not page_id or state_data.get("provider") != provider:
        return render(
            request,
            "conteudo/quiz_oauth_popup.html",
            {
                "status": "erro",
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "mensagem": "Estado OAuth inválido.",
                "page": None,
            },
            status=400,
        )

    page = get_object_or_404(QuizEstudoPage.objects.live().public(), id=page_id)
    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None
    if not oauth_provider_enabled(config_site, provider):
        return render(
            request,
            "conteudo/quiz_oauth_popup.html",
            {
                "status": "erro",
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "mensagem": "OAuth não configurado para este provedor.",
                "page": page,
            },
            status=400,
        )

    recebido_state = (request.GET.get("state") or "").strip()
    code = (request.GET.get("code") or "").strip()
    provider_error = (request.GET.get("error") or "").strip()
    if recebido_state != (state_data.get("state") or "") or provider_error or not code:
        request.session.pop("quiz_oauth_state", None)
        return render(
            request,
            "conteudo/quiz_oauth_popup.html",
            {
                "status": "erro",
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "mensagem": "Não foi possível concluir a autenticação externa.",
                "page": page,
            },
            status=400,
        )

    try:
        token_data = oauth_exchange_code(
            config_site,
            provider,
            code,
            _oauth_redirect_uri(request, "quiz_oauth_callback", provider),
        )
        profile = oauth_fetch_profile(config_site, provider, token_data)
    except Exception:
        request.session.pop("quiz_oauth_state", None)
        return render(
            request,
            "conteudo/quiz_oauth_popup.html",
            {
                "status": "erro",
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "mensagem": "Falha ao obter os dados do provedor.",
                "page": page,
            },
            status=400,
        )

    if not (profile.get("provider_user_id") or "").strip():
        request.session.pop("quiz_oauth_state", None)
        return render(
            request,
            "conteudo/quiz_oauth_popup.html",
            {
                "status": "erro",
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "mensagem": "O provedor não retornou um identificador válido.",
                "page": page,
            },
            status=400,
        )

    usuario, _identidade = _resolver_usuario_oauth(profile)
    if usuario:
        return _finalizar_login_quiz_oauth(request, page, config_site, usuario, profile)

    pending = {
        "page_id": page.id,
        "provider": provider,
        "provider_user_id": profile.get("provider_user_id") or "",
        "provider_username": profile.get("provider_username") or "",
        "display_name": profile.get("display_name") or "",
        "email": profile.get("email") or "",
        "email_verified": bool(profile.get("email_verified")),
        "profile_url": profile.get("profile_url") or "",
        "avatar_url": profile.get("avatar_url") or "",
        "scopes": profile.get("scopes") or "",
        "orcid": profile.get("orcid") or "",
        "suggested_username": profile.get("suggested_username") or "",
        "raw": profile.get("raw") or {},
    }
    request.session["quiz_oauth_pending"] = pending
    nome_default, sobrenome_default = _split_nome_partes(profile.get("display_name") or "")
    return render(
        request,
        "conteudo/quiz_oauth_concluir.html",
        {
            "page": page,
            "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
            "provider_label": oauth_provider_label(provider),
            "pending": pending,
            "config_site": config_site,
            "valores": {
                "nome": nome_default,
                "sobrenome": sobrenome_default,
                "username": profile.get("suggested_username") or "",
                "email": profile.get("email") or "",
            },
        },
    )


def quiz_oauth_concluir(request, page_id):
    page = get_object_or_404(QuizEstudoPage.objects.live().public(), id=page_id)
    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None
    pending = request.session.get("quiz_oauth_pending") or {}
    provider = pending.get("provider") or "oauth"
    if str(pending.get("page_id")) != str(page.id):
        return render(
            request,
            "conteudo/quiz_oauth_popup.html",
            {
                "status": "erro",
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "mensagem": "Sessão de vínculo expirada.",
                "page": page,
            },
            status=400,
        )

    nome_default, sobrenome_default = _split_nome_partes(pending.get("display_name") or "")
    if request.method != "POST":
        return render(
            request,
            "conteudo/quiz_oauth_concluir.html",
            {
                "page": page,
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "pending": pending,
                "config_site": config_site,
                "valores": {
                    "nome": nome_default,
                    "sobrenome": sobrenome_default,
                    "username": pending.get("suggested_username") or "",
                    "email": pending.get("email") or "",
                },
            },
        )

    nome = sanitizar_texto(request.POST.get("nome", ""), multiline=False)
    sobrenome = sanitizar_texto(request.POST.get("sobrenome", ""), multiline=False)
    nome_completo = _montar_nome_completo(nome, sobrenome)
    username = normalizar_username_publico(request.POST.get("username", ""))
    email_padrao = sanitizar_texto(pending.get("email") or "", multiline=False).lower()
    email = sanitizar_texto(request.POST.get("email", email_padrao), multiline=False).lower()
    orcid = sanitizar_texto(request.POST.get("orcid", pending.get("orcid") or ""), multiline=False).strip()
    aceitou_privacidade = str(request.POST.get("aceitou_privacidade_cadastro", "")).strip().lower() in {"1", "true", "on"}

    erro = ""
    valores = {
        "nome": nome,
        "sobrenome": sobrenome,
        "username": username,
        "email": email,
        "orcid": orcid,
    }
    if not nome or not sobrenome or not username or not email:
        erro = "campos"
    elif not aceitou_privacidade:
        erro = "privacidade"
    else:
        try:
            validate_email(email)
        except ValidationError:
            erro = "email"

    orcid_normalizado = _normalizar_orcid(orcid) if orcid else ""
    if not erro and orcid and not orcid_normalizado:
        erro = "usuario"

    erro_conflito, usuario_email, usuario_username, usuario_orcid = ("", None, None, None)
    if not erro:
        erro_conflito, usuario_email, usuario_username, usuario_orcid = _resolver_conflitos_usuario_comentario(
            email=email,
            username=username,
            orcid=orcid_normalizado,
        )
        if erro_conflito:
            erro = "usuario"

    if erro:
        return render(
            request,
            "conteudo/quiz_oauth_concluir.html",
            {
                "page": page,
                "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br") or "pt-br",
                "provider_label": oauth_provider_label(provider),
                "pending": pending,
                "erro": erro,
                "config_site": config_site,
                "valores": valores,
            },
        )

    usuario = usuario_email or usuario_username or usuario_orcid
    if usuario:
        alterou = False
        if nome_completo and usuario.nome != nome_completo:
            usuario.nome = nome_completo
            alterou = True
        if orcid_normalizado and usuario.orcid != orcid_normalizado:
            usuario.orcid = orcid_normalizado
            alterou = True
        if alterou:
            usuario.save(update_fields=["nome", "orcid", "atualizado_em"])
    else:
        usuario = UsuarioComentario.objects.create(
            nome=nome_completo,
            email=email,
            username=username,
            orcid=orcid_normalizado or "",
        )

    profile = {
        "provider": provider,
        "provider_user_id": pending.get("provider_user_id") or "",
        "provider_username": pending.get("provider_username") or "",
        "display_name": pending.get("display_name") or nome_completo,
        "email": email,
        "email_verified": bool(pending.get("email_verified")),
        "profile_url": pending.get("profile_url") or "",
        "avatar_url": pending.get("avatar_url") or "",
        "scopes": pending.get("scopes") or "",
        "orcid": pending.get("orcid") or "",
        "raw": pending.get("raw") or {},
    }
    return _finalizar_login_quiz_oauth(request, page, config_site, usuario, profile)


def quiz_tema_detalhe(request, page_id, slug):
    page = get_object_or_404(QuizEstudoPage.objects.live().public(), id=page_id)
    return redirect(f"{page.url}?tema={slug}")


def quiz_tag_detalhe(request, page_id, slug):
    page = get_object_or_404(QuizEstudoPage.objects.live().public(), id=page_id)
    return redirect(f"{page.url}?tag={slug}")


def _publicacao_contem_pergunta_catalogo(publicacao, pergunta):
    return PublicacaoPerguntaQuizCatalogo.objects.filter(
        publicacao=publicacao,
        pergunta=pergunta,
    ).exists()


def quiz_sessao_salvar(request, page_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método inválido."}, status=405)

    page = get_object_or_404(QuizEstudoPage, id=page_id)
    usuario = _quiz_usuario_autenticado(request)
    if not usuario:
        return JsonResponse({"ok": False, "auth": False}, status=401)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "payload"}, status=400)

    perguntas_payload = payload.get("perguntas") or payload.get("questions") or []
    if not isinstance(perguntas_payload, list):
        return JsonResponse({"ok": False, "error": "payload"}, status=400)

    perguntas_normalizadas = []
    respondidas = corretas = erradas = puladas = 0

    for item in perguntas_payload:
        if not isinstance(item, dict):
            continue

        correta_valor = item.get("correta")
        pulada_valor = item.get("pulada")
        correta = True if correta_valor is True else False if correta_valor is False else None
        pulada_flag = bool(pulada_valor is True)

        if correta is not None:
            respondidas += 1
            if correta:
                corretas += 1
            else:
                erradas += 1
        elif pulada_flag:
            puladas += 1

        perguntas_normalizadas.append(
            {
                "question_key": sanitizar_texto(item.get("question_key", ""), multiline=False),
                "question_id": int(item.get("question_id") or 0) if str(item.get("question_id") or "").isdigit() else 0,
                "correta": correta,
                "pulada": pulada_flag,
                "selecionadas": [
                    int(valor)
                    for valor in (item.get("selecionadas") or [])
                    if isinstance(valor, int) or (isinstance(valor, str) and valor.isdigit())
                ],
            }
        )

    consideradas = respondidas
    media = int(round((corretas / consideradas) * 100)) if consideradas else 0

    sessao = QuizSessaoUsuario.objects.create(
        usuario=usuario,
        pagina=page,
        respondidas=respondidas,
        corretas=corretas,
        erradas=erradas,
        puladas=puladas,
        consideradas=consideradas,
        media_percentual=media,
        detalhes={
            "perguntas": perguntas_normalizadas,
            "tema": sanitizar_texto(payload.get("tema", ""), multiline=False),
            "tag": sanitizar_texto(payload.get("tag", ""), multiline=False),
        },
    )

    return JsonResponse(
        {
            "ok": True,
            "session": {
                "id": sessao.id,
                "respondidas": respondidas,
                "corretas": corretas,
                "erradas": erradas,
                "puladas": puladas,
                "consideradas": consideradas,
                "media_percentual": media,
            },
        }
    )


def quiz_resposta_salvar(request, page_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método inválido."}, status=405)

    publicacao = get_object_or_404(PublicacaoPage, id=page_id)
    usuario = _quiz_usuario_autenticado(request)
    if not usuario:
        return JsonResponse({"ok": False, "auth": False}, status=401)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "payload"}, status=400)

    question_kind = sanitizar_texto(payload.get("question_kind", ""), multiline=False).lower()
    question_id = int(payload.get("question_id") or 0) if str(payload.get("question_id") or "").isdigit() else 0
    correta = bool(payload.get("correta") is True)
    selecionadas_raw = payload.get("selecionadas") or []

    if question_kind != "catalogo" or not question_id:
        return JsonResponse({"ok": False, "error": "question_kind"}, status=400)

    pergunta = get_object_or_404(PerguntaQuizCatalogo.objects.all(), id=question_id, ativa=True)
    if not _publicacao_contem_pergunta_catalogo(publicacao, pergunta):
        return JsonResponse({"ok": False, "error": "question_scope"}, status=400)

    selecionadas = []
    for item in selecionadas_raw:
        if isinstance(item, int):
            selecionadas.append(item)
        elif isinstance(item, str) and item.isdigit():
            selecionadas.append(int(item))

    defaults = {
        "publicacao": publicacao,
        "ultima_correta": correta,
        "selecionadas": selecionadas,
    }
    resposta, _ = QuizRespostaUsuario.objects.update_or_create(
        usuario=usuario,
        pergunta_catalogo=pergunta,
        defaults=defaults,
    )

    question_key = pergunta.quiz_dom_id
    return JsonResponse(
        {
            "ok": True,
            "answer": {
                "question_key": question_key,
                "correta": bool(resposta.ultima_correta),
                "selecionadas": list(resposta.selecionadas or []),
            },
        }
    )


def duvida_quiz_enviar(request, page_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Método inválido.")

    publicacao = get_object_or_404(PublicacaoPage, id=page_id)
    site = Site.find_for_request(request)
    config_site = ConfiguracaoSite.for_site(site) if site else None
    usuario = _quiz_usuario_autenticado(request)

    if not usuario:
        return redirect(f"{publicacao.url}?comentario=login_necessario#comentarios")

    mensagem = sanitizar_texto(request.POST.get("mensagem", ""), multiline=True)
    pergunta_quiz_id = request.POST.get("pergunta_quiz_id", "")
    pergunta_quiz_tipo = sanitizar_texto(request.POST.get("pergunta_quiz_tipo", ""), multiline=False).lower()
    permitir_publicacao = str(request.POST.get("permitir_publicacao_comentarios", "")).strip().lower() in {"1", "true", "on"}

    if not mensagem or not pergunta_quiz_id.isdigit() or pergunta_quiz_tipo != "catalogo":
        return redirect(f"{publicacao.url}?duvida=erro_campos#quiz-publicacao")

    pergunta_catalogo = PerguntaQuizCatalogo.objects.filter(id=int(pergunta_quiz_id), ativa=True).first()
    if not pergunta_catalogo or not _publicacao_contem_pergunta_catalogo(publicacao, pergunta_catalogo):
        return redirect(f"{publicacao.url}?duvida=erro_pergunta#quiz-publicacao")

    duvida = DuvidaQuizPublicacao.objects.create(
        publicacao=publicacao,
        pergunta_catalogo=pergunta_catalogo,
        usuario=usuario,
        mensagem=mensagem,
        permitir_publicacao_comentarios=permitir_publicacao,
    )

    destinatarios = []
    if config_site and config_site.email_contato:
        destinatarios.append(config_site.email_contato)
    elif settings.DEFAULT_FROM_EMAIL:
        destinatarios.append(settings.DEFAULT_FROM_EMAIL)

    if destinatarios:
        assunto = f"Dúvida do quiz · {publicacao.title}"
        corpo = (
            f"Publicação: {publicacao.title}\n"
            f"Pergunta: {pergunta_catalogo.pergunta}\n"
            f"Usuário: {usuario.username} ({usuario.email})\n\n"
            f"Mensagem:\n{mensagem}\n"
        )
        try:
            EmailMessage(
                subject=assunto,
                body=corpo,
                to=destinatarios,
            ).send(fail_silently=True)
        except Exception:
            pass

    return redirect(f"{publicacao.url}?duvida=enviada#quiz-publicacao")


def avaliacao_publicacao_enviar(request, page_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Método inválido.")

    publicacao = get_object_or_404(PublicacaoPage.objects.live().public(), id=page_id)
    try:
        valor = Decimal(str(request.POST.get("valor", "0")).replace(",", "."))
        valor_meio = int((valor * 2).quantize(Decimal("1")))
        if valor_meio < 1 or valor_meio > 10:
            raise InvalidOperation
    except (InvalidOperation, TypeError):
        return redirect(f"{publicacao.url}#avaliacao-publicacao")

    cookie_id = (request.COOKIES.get("ownpaper_rating_id") or "").strip()
    if not cookie_id:
        cookie_id = uuid.uuid4().hex

    with transaction.atomic():
        avaliacao = (
            AvaliacaoPublicacao.objects
            .select_for_update()
            .filter(publicacao=publicacao, cookie_id=cookie_id)
            .first()
        )
        if avaliacao:
            diferenca = valor_meio - avaliacao.valor_meio
            if diferenca:
                avaliacao.valor_meio = valor_meio
                avaliacao.ip_origem = request.META.get("REMOTE_ADDR", "") or ""
                avaliacao.save(update_fields=["valor_meio", "ip_origem", "atualizado_em"])
                PublicacaoPage.objects.filter(pk=publicacao.pk).update(
                    soma_avaliacoes_meio=F("soma_avaliacoes_meio") + diferenca,
                )
                publicacao.soma_avaliacoes_meio += diferenca
        else:
            AvaliacaoPublicacao.objects.create(
                publicacao=publicacao,
                cookie_id=cookie_id,
                valor_meio=valor_meio,
                ip_origem=request.META.get("REMOTE_ADDR", "") or "",
            )
            PublicacaoPage.objects.filter(pk=publicacao.pk).update(
                total_avaliacoes=F("total_avaliacoes") + 1,
                soma_avaliacoes_meio=F("soma_avaliacoes_meio") + valor_meio,
            )
            publicacao.total_avaliacoes += 1
            publicacao.soma_avaliacoes_meio += valor_meio

    response = redirect(f"{publicacao.url}#avaliacao-publicacao")
    response.set_cookie(
        "ownpaper_rating_id",
        cookie_id,
        max_age=94608000,
        secure=_cookie_secure(request),
        httponly=True,
        samesite="Lax",
        path="/",
    )
    return response
