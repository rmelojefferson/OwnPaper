import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from django.contrib.sites.shortcuts import get_current_site
from django.utils import timezone
from django.utils.text import slugify
from wagtail.models import Site

from .models import ConfiguracaoSite, LinkCurtoShlink


logger = logging.getLogger(__name__)


CANAL_SIGLAS_SHLINK = {
    LinkCurtoShlink.CANAL_WHATSAPP: "w",
    LinkCurtoShlink.CANAL_TELEGRAM: "t",
    LinkCurtoShlink.CANAL_LINKEDIN: "l",
    LinkCurtoShlink.CANAL_MASTODON: "m",
    LinkCurtoShlink.CANAL_BLUESKY: "b",
    LinkCurtoShlink.CANAL_X: "x",
    LinkCurtoShlink.CANAL_EMAIL: "e",
    LinkCurtoShlink.CANAL_COPIA: "c",
    LinkCurtoShlink.CANAL_MANUAL: "n",
}


def _base36(value):
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    value = int(value or 0)
    if value == 0:
        return "0"
    out = []
    while value:
        value, remainder = divmod(value, 36)
        out.append(digits[remainder])
    return "".join(reversed(out))


def _site_e_config(site=None, request=None):
    resolved_site = site
    if request is not None and resolved_site is None:
        try:
            resolved_site = Site.find_for_request(request)
        except Exception:
            resolved_site = None
    if resolved_site is None:
        resolved_site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    config = ConfiguracaoSite.for_site(resolved_site) if resolved_site else None
    return resolved_site, config


def _config_value(config, field_name, default=""):
    if not config:
        return default
    if hasattr(config, "get_runtime_setting"):
        value = config.get_runtime_setting(field_name, default=default)
    else:
        value = getattr(config, field_name, default)
    return value.strip() if isinstance(value, str) else value


def shlink_habilitado(site=None, request=None):
    _, config = _site_e_config(site=site, request=request)
    return bool(
        config
        and config.shlink_ativo
        and _config_value(config, "shlink_base_url")
        and _config_value(config, "shlink_api_key")
    )


def _api_request(config, method, path, payload=None):
    base_url = (_config_value(config, "shlink_base_url") or "").rstrip("/")
    if not base_url:
        raise ValueError("Shlink sem URL base configurada.")

    body = None
    headers = {
        "Accept": "application/json",
        "X-Api-Key": _config_value(config, "shlink_api_key"),
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request_http = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        headers=headers,
        method=method.upper(),
    )
    with urllib.request.urlopen(request_http, timeout=15) as response:
        raw = response.read().decode("utf-8") or "{}"
    return json.loads(raw)


def _slug_compartilhamento(publicacao, canal, long_url):
    canal_sigla = CANAL_SIGLAS_SHLINK.get(canal, "lnk")
    assinatura = hashlib.sha1(long_url.encode("utf-8")).hexdigest()[:4]
    return f"o{_base36(publicacao.id)}{canal_sigla}{assinatura}"[:255]


def _payload_shlink(config, long_url, titulo="", tags=None, publicacao=None, canal="", contexto="manual"):
    payload = {
        "longUrl": long_url,
        "tags": tags or [],
        "validateUrl": False,
    }
    domain = (config.shlink_default_domain or "").strip()
    if domain:
        payload["domain"] = domain
    if titulo:
        payload["title"] = titulo[:255]
    if publicacao and contexto == LinkCurtoShlink.CONTEXTO_PUBLICACAO and canal:
        payload["customSlug"] = _slug_compartilhamento(publicacao, canal, long_url)
    else:
        payload["findIfExists"] = True
    return payload


def _hidratar_link_por_short_code(config, link, short_code):
    payload = _api_request(config, "GET", f"/rest/v3/short-urls/{urllib.parse.quote(short_code)}")
    visits_summary = payload.get("visitsSummary") or {}
    link.short_url = (payload.get("shortUrl") or link.short_url or "").strip()
    link.short_code = (payload.get("shortCode") or short_code or "").strip()
    link.dominio = (payload.get("domain") or link.dominio or "").strip()
    link.visits_total = int(payload.get("visitsCount") or visits_summary.get("total") or 0)
    link.visits_non_bots = int(visits_summary.get("nonBots") or 0)
    link.visits_bots = int(visits_summary.get("bots") or 0)
    link.ultimo_sync_em = timezone.now()
    link.ultimo_erro = ""
    link.save()
    return link


def sincronizar_metricas_link(link, site=None, request=None):
    _, config = _site_e_config(site=site, request=request)
    if not (
        config
        and config.shlink_ativo
        and link.short_code
        and _config_value(config, "shlink_base_url")
        and _config_value(config, "shlink_api_key")
    ):
        return link

    try:
        payload = _api_request(config, "GET", f"/rest/v3/short-urls/{urllib.parse.quote(link.short_code)}")
        visits_summary = payload.get("visitsSummary") or {}
        link.short_url = (payload.get("shortUrl") or link.short_url or "").strip()
        link.dominio = (payload.get("domain") or link.dominio or "").strip()
        link.visits_total = int(payload.get("visitsCount") or visits_summary.get("total") or 0)
        link.visits_non_bots = int(visits_summary.get("nonBots") or 0)
        link.visits_bots = int(visits_summary.get("bots") or 0)
        link.ultimo_sync_em = timezone.now()
        link.ultimo_erro = ""
        link.save(update_fields=[
            "short_url",
            "dominio",
            "visits_total",
            "visits_non_bots",
            "visits_bots",
            "ultimo_sync_em",
            "ultimo_erro",
            "atualizado_em",
        ])
    except Exception as exc:
        logger.warning("Falha ao sincronizar métricas Shlink: %s", exc)
        link.ultimo_erro = str(exc)
        link.save(update_fields=["ultimo_erro", "atualizado_em"])
    return link


def obter_ou_criar_link_curto(
    long_url,
    *,
    canal,
    contexto=LinkCurtoShlink.CONTEXTO_MANUAL,
    publicacao=None,
    titulo="",
    tags=None,
    site=None,
    request=None,
):
    _, config = _site_e_config(site=site, request=request)
    if not (
        config
        and config.shlink_ativo
        and _config_value(config, "shlink_base_url")
        and _config_value(config, "shlink_api_key")
    ):
        return None

    qs = LinkCurtoShlink.objects.filter(
        long_url=long_url,
        canal=canal,
        contexto=contexto,
        publicacao=publicacao,
    )
    slug_desejado = ""
    if publicacao and contexto == LinkCurtoShlink.CONTEXTO_PUBLICACAO and canal:
        slug_desejado = _slug_compartilhamento(publicacao, canal, long_url)
    link_ok = qs.exclude(short_url="").order_by("-atualizado_em", "-criado_em").first()
    if link_ok:
        if not slug_desejado or link_ok.short_code == slug_desejado:
            if not link_ok.ultimo_sync_em or link_ok.ultimo_sync_em < timezone.now() - timedelta(hours=6):
                sincronizar_metricas_link(link_ok, site=site, request=request)
            return link_ok
    link = qs.order_by("-atualizado_em", "-criado_em").first()

    tags = list(tags or [])
    payload = _payload_shlink(
        config,
        long_url,
        titulo=titulo,
        tags=tags,
        publicacao=publicacao,
        canal=canal,
        contexto=contexto,
    )
    slug_customizado = payload.get("customSlug", "")

    if link is None:
        link = LinkCurtoShlink(
            publicacao=publicacao,
            contexto=contexto,
            canal=canal,
            titulo=titulo[:255],
            long_url=long_url,
            slug_customizado=slug_customizado,
            tags=tags,
        )
    else:
        link.titulo = titulo[:255]
        link.slug_customizado = slug_customizado
        link.tags = tags

    try:
        payload_resp = _api_request(config, "POST", "/rest/v3/short-urls", payload)
        visits_summary = payload_resp.get("visitsSummary") or {}
        link.short_url = (payload_resp.get("shortUrl") or "").strip()
        link.short_code = (payload_resp.get("shortCode") or "").strip()
        link.dominio = (payload_resp.get("domain") or "").strip()
        link.visits_total = int(payload_resp.get("visitsCount") or visits_summary.get("total") or 0)
        link.visits_non_bots = int(visits_summary.get("nonBots") or 0)
        link.visits_bots = int(visits_summary.get("bots") or 0)
        link.ultimo_sync_em = timezone.now()
        link.ultimo_erro = ""
        link.save()
        return link
    except Exception as exc:
        if slug_customizado:
            try:
                return _hidratar_link_por_short_code(config, link, slug_customizado)
            except Exception:
                pass
        logger.warning("Falha ao criar link curto no Shlink: %s", exc)
        link.ultimo_erro = str(exc)
        link.save()
        return link if link.short_url else None


def obter_url_curta(
    long_url,
    *,
    canal,
    contexto=LinkCurtoShlink.CONTEXTO_MANUAL,
    publicacao=None,
    titulo="",
    tags=None,
    site=None,
    request=None,
):
    link = obter_ou_criar_link_curto(
        long_url,
        canal=canal,
        contexto=contexto,
        publicacao=publicacao,
        titulo=titulo,
        tags=tags,
        site=site,
        request=request,
    )
    return (link.short_url or "").strip() if link else long_url


def obter_url_curta_cache(
    long_url,
    *,
    canal,
    contexto=LinkCurtoShlink.CONTEXTO_MANUAL,
    publicacao=None,
):
    """Retorna apenas o link curto já persistido, sem chamar a API externa.

    Esta função existe para fluxos de renderização pública, onde bloquear a
    resposta em uma chamada remota pode derrubar workers do Gunicorn.
    """
    link = (
        LinkCurtoShlink.objects.filter(
            long_url=long_url,
            canal=canal,
            contexto=contexto,
            publicacao=publicacao,
        )
        .exclude(short_url="")
        .order_by("-atualizado_em", "-criado_em")
        .first()
    )
    return (link.short_url or "").strip() if link else ""


def gerar_links_compartilhamento_publicacao(request, publicacao, titulo=""):
    long_url = request.build_absolute_uri(publicacao.url)
    canais = [
        LinkCurtoShlink.CANAL_WHATSAPP,
        LinkCurtoShlink.CANAL_TELEGRAM,
        LinkCurtoShlink.CANAL_LINKEDIN,
        LinkCurtoShlink.CANAL_MASTODON,
        LinkCurtoShlink.CANAL_BLUESKY,
        LinkCurtoShlink.CANAL_X,
        LinkCurtoShlink.CANAL_COPIA,
    ]
    saida = {}
    for canal in canais:
        saida[canal] = obter_url_curta_cache(
            long_url,
            canal=canal,
            contexto=LinkCurtoShlink.CONTEXTO_PUBLICACAO,
            publicacao=publicacao,
        ) or long_url
    return saida
