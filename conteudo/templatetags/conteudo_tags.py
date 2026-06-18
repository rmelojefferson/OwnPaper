import re
import urllib.parse

from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

register = template.Library()

MENU_LABELS = {
    "home": {"pt-br": "Início"},
    "categorias": {"pt-br": "Categorias"},
    "tags": {"pt-br": "Tags"},
    "autores": {"pt-br": "Autores"},
    "busca": {"pt-br": "Busca"},
    "destaques": {"pt-br": "Destaques"},
    "ultimas": {"pt-br": "Últimas publicações"},
    "contato": {"pt-br": "Contato"},
    "newsletter": {"pt-br": "Newsletter"},
    "indexador": {"pt-br": "Indexador"},
    "quiz": {"pt-br": "Quiz"},
}


def _normalize_lang(lang):
    return "pt-br"

def _translate_plain_label(texto, lang):
    return str(texto or "").strip()


def _menu_label_by_shortcut(shortcut, lang, fallback=""):
    key = (shortcut or "").strip().lower()
    mapa = MENU_LABELS.get(key)
    if not mapa:
        return fallback or ""
    idioma = _normalize_lang(lang)
    return mapa.get(idioma) or mapa.get("pt-br") or fallback or ""


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
def exibir_documentos_pendentes(html):
    padrao = re.compile(r"\[\[\s*documento-pendente:\s*(\d+)\s*\]\]", re.IGNORECASE)

    def substituir(match):
        return (
            '<span class="documento-pendente">'
            "Documento aguardando aprovação editorial."
            "</span>"
        )

    return mark_safe(padrao.sub(substituir, str(html or "")))


@register.filter
def dict_get(mapping, key):
    if not isinstance(mapping, dict):
        return None
    return mapping.get(key)


@register.simple_tag
def translated(obj, field_name, lang="pt-br"):
    if obj is None:
        return ""
    return getattr(obj, field_name, "")


@register.simple_tag
def menu_item_label(item, lang="pt-br"):
    if item is None:
        return ""

    atalho = getattr(item, "atalho", "")
    titulo = str(getattr(item, "titulo", "") or "").strip()

    if atalho:
        label_atalho = _menu_label_by_shortcut(atalho, lang, "")
        if label_atalho:
            # Se o usuário customizou o título do atalho, prioriza tradução do próprio texto.
            rotulo_padrao_pt = (
                (MENU_LABELS.get((atalho or "").strip().lower()) or {}).get("pt-br", "")
            ).strip()
            if titulo and titulo != rotulo_padrao_pt:
                return _translate_plain_label(titulo, lang)
            return label_atalho
        return _translate_plain_label(titulo, lang)

    tipo = getattr(item, "tipo", "")
    pagina = getattr(item, "pagina", None)
    if tipo == "pagina" and pagina is not None:
        getter = getattr(pagina, "get_translated_value", None)
        if callable(getter):
            traduzido = getter("title", lang)
            if traduzido:
                return traduzido
        return _translate_plain_label(getattr(pagina, "title", "") or titulo, lang)

    return _translate_plain_label(titulo, lang)


@register.simple_tag
def menu_shortcut_label(shortcut, lang="pt-br", fallback=""):
    idioma = _normalize_lang(lang)
    fallback_limpo = str(fallback or "").strip()
    label_atalho = _menu_label_by_shortcut(shortcut, idioma, "")
    if fallback_limpo:
        rotulo_padrao_pt = (
            (MENU_LABELS.get((shortcut or "").strip().lower()) or {}).get("pt-br", "")
        ).strip()
        if fallback_limpo != rotulo_padrao_pt:
            if idioma != "pt-br":
                return _translate_plain_label(fallback_limpo, idioma)
            return fallback_limpo
        if label_atalho:
            return label_atalho
        return fallback_limpo
    return label_atalho


@register.simple_tag
def translate_label(texto, lang="pt-br"):
    return _translate_plain_label(texto, lang)


@register.simple_tag
def translate_copyright(texto, lang="pt-br"):
    return str(texto or "").strip()


@register.simple_tag
def translate_text_content(value, lang="pt-br"):
    return str(value or "")


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

    def substituir_ancora(match):
        marcador_original = match.group(1).strip()
        marcador = normalizar_marcador(marcador_original)
        return f'<span id="{marcador}" class="ancora-interna-publicacao" aria-hidden="true"></span>'

    html = re.sub(r"\[\[\s*a:\s*([^\]\|]+?)\s*\]\]", substituir_ancora, html, flags=re.IGNORECASE)

    html = re.sub(r"\[\[\s*n:\s*([^\]]+?)\s*\]\]", substituir_nota, html, flags=re.IGNORECASE)
    html = re.sub(r"\[\[\s*r:\s*([^\]]+?)\s*\]\]", substituir_referencia, html, flags=re.IGNORECASE)

    return mark_safe(html)


@register.filter
def desembrulhar_paragrafo_externo(html):
    if not html:
        return ""

    html = str(html)
    match = re.match(r"^\s*<p\b[^>]*>(?P<conteudo>.*)</p>\s*$", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return mark_safe(html)

    conteudo = match.group("conteudo")
    return mark_safe(conteudo)


@register.filter
def inserir_videos_no_corpo(html, page):
    if not html:
        return ""

    html = str(html)

    for midia in page.midias_embed.all():
        marcadores = list(getattr(midia, "marcadores_lista", []) or [])
        if not marcadores:
            continue
        bloco_video = render_to_string(
            "includes/bloco_video_publicacao.html",
            {"midia": midia},
        )
        for marcador in marcadores:
            token = f"[[v:{marcador.strip()}]]"
            html = re.sub(
                rf"<p[^>]*>\s*{re.escape(token)}\s*</p>",
                bloco_video,
                html,
                flags=re.IGNORECASE,
            )
            html = html.replace(token, bloco_video)

    return mark_safe(html)


@register.filter
def inserir_imagens_no_corpo(html, page):
    if not html:
        return ""

    html = str(html)

    for item in page.imagens_publicacao.all():
        marcadores = list(getattr(item, "marcadores_lista", []) or [])
        if not marcadores:
            continue
        bloco_imagem = render_to_string(
            "includes/bloco_imagem_publicacao.html",
            {"item": item},
        )
        for marcador in marcadores:
            token = f"[[i:{marcador.strip()}]]"
            html = re.sub(
                rf"<p[^>]*>\s*{re.escape(token)}\s*</p>",
                bloco_imagem,
                html,
                flags=re.IGNORECASE,
            )
            html = html.replace(token, bloco_imagem)

    return mark_safe(html)
