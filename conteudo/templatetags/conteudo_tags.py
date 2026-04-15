import re
import urllib.parse

from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

register = template.Library()


def _parsed_url(value):
    raw = str(value or "").strip()
    if not raw:
        return "", None

    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return raw, None

    if not (parsed.scheme and parsed.netloc):
        return raw, None

    return raw, parsed


def _looks_like_url(value):
    _, parsed = _parsed_url(value)
    return bool(parsed)


def _extract_instagram_handle(url):
    _, parsed = _parsed_url(url)
    if not parsed:
        return ""

    host = (parsed.netloc or "").lower()
    if "instagram.com" not in host:
        return ""

    parts = [p for p in (parsed.path or "").split("/") if p]
    if not parts:
        return ""

    reserved = {"p", "reel", "tv", "stories", "explore"}
    username = parts[0].lstrip("@")
    if not username or username.lower() in reserved:
        return ""

    return f"@{username}"


def _extract_youtube_handle(url):
    _, parsed = _parsed_url(url)
    if not parsed:
        return ""

    host = (parsed.netloc or "").lower()
    if "youtube.com" not in host and "youtu.be" not in host:
        return ""

    parts = [p for p in (parsed.path or "").split("/") if p]
    if not parts:
        return ""

    first = parts[0]
    if first.startswith("@"):
        return first

    if first in {"channel", "c", "user"} and len(parts) > 1:
        return f"@{parts[1].lstrip('@')}"

    return ""


def _extract_profile_handle(url):
    handle = _extract_instagram_handle(url)
    if handle:
        return handle

    _, parsed = _parsed_url(url)
    if not parsed:
        return ""

    parts = [p for p in (parsed.path or "").split("/") if p]
    if not parts:
        return ""

    first = parts[0]
    if first.startswith("@"):
        return first

    reserved = {"p", "reel", "tv", "stories", "explore", "watch", "shorts"}
    if first.lower() in reserved:
        return ""

    return f"@{first.lstrip('@')}" if first else ""


def normalizar_marcador(valor):
    return str(valor).strip().replace(" ", "-")


@register.filter
def id_marcador(valor):
    return normalizar_marcador(valor)


@register.filter
def url_display(url, max_len=48):
    if not url:
        return ""

    raw = str(url).strip()
    try:
        parsed = urllib.parse.urlparse(raw)
        host = parsed.netloc or ""
        path = parsed.path or ""
        display = host + (path if path and path != "/" else "")
        display = display.lstrip("/")
    except Exception:
        display = raw

    if len(display) > int(max_len):
        display = display[: int(max_len) - 1] + "…"

    return display or raw


@register.filter
def credit_text_display(texto, max_len=48):
    if not texto:
        return ""

    raw = str(texto).strip()
    if not _looks_like_url(raw):
        return raw

    return url_display(raw, max_len)


@register.filter
def is_url(value):
    return _looks_like_url(value)


@register.filter
def instagram_handle(url):
    return _extract_profile_handle(url) or "Instagram"


@register.simple_tag
def video_credit_label(item):
    credito_texto = str(getattr(item, "credito_texto", "") or "").strip()
    credito_url = str(getattr(item, "credito_url", "") or "").strip()
    fonte_url = str(getattr(item, "fonte_url", "") or "").strip()
    titulo = str(getattr(item, "titulo", "") or "").strip()

    handle = _extract_youtube_handle(credito_url) or _extract_youtube_handle(fonte_url)
    if handle:
        return handle

    if credito_texto and not _looks_like_url(credito_texto):
        return credito_texto

    if titulo:
        return titulo

    return "Canal no YouTube"


@register.filter
def linkar_marcadores(html):
    if not html:
        return ""

    html = str(html)

    notas_primeira_ocorrencia = set()
    refs_primeira_ocorrencia = set()

    def substituir_nota(match):
        marcador_original = match.group(1).strip()
        marcador = normalizar_marcador(marcador_original)

        if marcador not in notas_primeira_ocorrencia:
            notas_primeira_ocorrencia.add(marcador)
            return (
                f'<sup id="nota-src-{marcador}">'
                f'<a href="#nota-{marcador}">{marcador_original}</a>'
                f"</sup>"
            )

        return f'<sup><a href="#nota-{marcador}">{marcador_original}</a></sup>'

    def substituir_referencia(match):
        marcador_original = match.group(1).strip()
        marcador = normalizar_marcador(marcador_original)

        if marcador not in refs_primeira_ocorrencia:
            refs_primeira_ocorrencia.add(marcador)
            return (
                f'<sup id="ref-src-{marcador}">'
                f'<a href="#ref-{marcador}">{marcador_original}</a>'
                f"</sup>"
            )

        return f'<sup><a href="#ref-{marcador}">{marcador_original}</a></sup>'

    html = re.sub(r"\[\[n:([^\]]+)\]\]", substituir_nota, html)
    html = re.sub(r"\[\[r:([^\]]+)\]\]", substituir_referencia, html)

    return mark_safe(html)


@register.filter
def inserir_videos_no_corpo(html, page):
    if not html:
        return ""

    html = str(html)

    for midia in page.midias_embed.all():
        if not midia.marcador:
            continue

        token = f"[[v:{midia.marcador.strip()}]]"
        bloco_video = render_to_string(
            "includes/bloco_video_publicacao.html",
            {"midia": midia},
        )
        html = html.replace(token, bloco_video)

    return mark_safe(html)


@register.filter
def inserir_imagens_no_corpo(html, page):
    if not html:
        return ""

    html = str(html)

    for item in page.imagens_publicacao.all():
        if not item.marcador:
            continue

        token = f"[[i:{item.marcador.strip()}]]"
        bloco_imagem = render_to_string(
            "includes/bloco_imagem_publicacao.html",
            {"item": item},
        )
        html = html.replace(token, bloco_imagem)

    return mark_safe(html)
