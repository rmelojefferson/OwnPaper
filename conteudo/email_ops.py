from datetime import timedelta
import re
import urllib.parse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.mail import EmailMessage
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Site

from .html_safety import sanitize_email_html
from .roles import AUTHOR_GROUP_NAME
from .models import (
    ConfiguracaoSite,
    DisparoEmail,
    DisparoEmailDestino,
    InscritoNewsletter,
    PublicacaoPage,
)


def _particionar(lista, tamanho):
    for i in range(0, len(lista), tamanho):
        yield lista[i : i + tamanho]


HREF_RE = re.compile(r"""href=(["'])(.*?)\1""", flags=re.IGNORECASE)


def _resolver_site_disparo(disparo):
    site_id = int((disparo.metadata or {}).get("site_id") or 0)
    if site_id:
        site = Site.objects.filter(id=site_id).first()
        if site:
            return site
    return Site.objects.filter(is_default_site=True).first() or Site.objects.first()


def _base_publica_disparo(disparo):
    base_cfg = (getattr(settings, "PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    if base_cfg:
        return base_cfg

    site = _resolver_site_disparo(disparo)
    if not site:
        return ""
    try:
        return site.root_url.rstrip("/")
    except Exception:
        return ""


def _url_destino_absoluta(base_publica, href):
    href = (href or "").strip()
    if not href:
        return ""
    href_lower = href.lower()
    if (
        href_lower.startswith("#")
        or href_lower.startswith("mailto:")
        or href_lower.startswith("tel:")
        or href_lower.startswith("javascript:")
        or href_lower.startswith("data:")
    ):
        return ""
    if href_lower.startswith("http://") or href_lower.startswith("https://"):
        return href
    if href.startswith("/"):
        if not base_publica:
            return ""
        return f"{base_publica}{href}"
    return ""


def _corpo_com_rastreio(disparo, destino):
    base_publica = _base_publica_disparo(disparo)
    corpo = sanitize_email_html(disparo.corpo_html or "")

    if not corpo:
        return corpo

    def _substituir_link(match):
        aspas = match.group(1)
        href_original = match.group(2)
        href_destino = _url_destino_absoluta(base_publica, href_original)
        if not href_destino:
            return match.group(0)
        payload = {"t": str(destino.tracking_token), "u": href_destino}
        dado_assinado = signing.dumps(payload, salt="ownpaper_email_click")
        rota = reverse("email_click_track", kwargs={"token": str(destino.tracking_token)})
        href_track = f"{base_publica}{rota}?d={urllib.parse.quote(dado_assinado, safe='')}"
        return f"href={aspas}{href_track}{aspas}"

    corpo_track = HREF_RE.sub(_substituir_link, corpo)
    rota_open = reverse("email_open_track", kwargs={"token": str(destino.tracking_token)})
    pixel_url = f"{base_publica}{rota_open}"
    pixel = (
        '<img src="{url}" alt="" width="1" height="1" '
        'style="display:block;border:0;outline:none;text-decoration:none;">'
    ).format(url=pixel_url)
    return f"{corpo_track}{pixel}"


def destinatarios_por_segmento(segmento):
    User = get_user_model()
    if segmento == DisparoEmail.SEG_TODOS_USUARIOS:
        return list(
            User.objects.filter(is_active=True)
            .exclude(email__isnull=True)
            .exclude(email__exact="")
            .values_list("email", flat=True)
            .distinct()
        )
    if segmento == DisparoEmail.SEG_APENAS_ADMINS:
        return list(
            User.objects.filter(is_active=True, is_superuser=True)
            .exclude(email__isnull=True)
            .exclude(email__exact="")
            .values_list("email", flat=True)
            .distinct()
        )
    if segmento == DisparoEmail.SEG_APENAS_AUTORES:
        return list(
            User.objects.filter(
                is_active=True,
                is_superuser=False,
                groups__name=AUTHOR_GROUP_NAME,
            )
            .exclude(email__isnull=True)
            .exclude(email__exact="")
            .values_list("email", flat=True)
            .distinct()
        )
    if segmento == DisparoEmail.SEG_NEWSLETTER:
        return list(
            InscritoNewsletter.objects.filter(ativo=True)
            .exclude(email__isnull=True)
            .exclude(email__exact="")
            .values_list("email", flat=True)
            .distinct()
        )
    return []


def executar_disparo(disparo):
    emails = destinatarios_por_segmento(disparo.segmento)
    emails_unicos = sorted(set([email.strip().lower() for email in emails if email]))
    disparo.status = DisparoEmail.STATUS_ENVIANDO
    disparo.total_destinatarios = len(emails_unicos)
    disparo.total_enviados = 0
    disparo.total_falhas = 0
    disparo.erro = ""
    disparo.save(
        update_fields=[
            "status",
            "total_destinatarios",
            "total_enviados",
            "total_falhas",
            "erro",
        ]
    )

    disparo.destinos.all().delete()
    DisparoEmailDestino.objects.bulk_create(
        [
            DisparoEmailDestino(
                disparo=disparo,
                email=email,
                status=DisparoEmailDestino.STATUS_PENDENTE,
            )
            for email in emails_unicos
        ],
        batch_size=500,
    )

    if not emails_unicos:
        disparo.status = DisparoEmail.STATUS_CONCLUIDO
        disparo.enviado_em = timezone.now()
        disparo.save(update_fields=["status", "enviado_em"])
        return disparo

    enviados = 0
    falhas = 0
    ultimo_erro = ""
    for destino in disparo.destinos.all().order_by("id"):
        msg = EmailMessage(
            subject=disparo.assunto,
            body=_corpo_com_rastreio(disparo, destino),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[destino.email],
        )
        msg.content_subtype = "html"
        try:
            msg.send(fail_silently=False)
            enviados += 1
            destino.status = DisparoEmailDestino.STATUS_ENVIADO
            destino.enviado_em = timezone.now()
            destino.erro = ""
            destino.save(update_fields=["status", "enviado_em", "erro"])
        except Exception as exc:
            falhas += 1
            ultimo_erro = str(exc)
            destino.status = DisparoEmailDestino.STATUS_FALHOU
            destino.erro = ultimo_erro[:5000]
            destino.save(update_fields=["status", "erro"])

    disparo.total_enviados = enviados
    disparo.total_falhas = falhas
    disparo.enviado_em = timezone.now()
    if falhas > 0 and enviados == 0:
        disparo.status = DisparoEmail.STATUS_FALHOU
        disparo.erro = ultimo_erro[:5000]
    else:
        disparo.status = DisparoEmail.STATUS_CONCLUIDO
        disparo.erro = ultimo_erro[:5000] if ultimo_erro else ""
    disparo.save(
        update_fields=[
            "total_enviados",
            "total_falhas",
            "enviado_em",
            "status",
            "erro",
        ]
    )
    return disparo


def _resumo_publicacoes_html(publicacoes):
    base_url = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
    blocos = []
    for p in publicacoes:
        data = p.data_publicacao.strftime("%d/%m/%Y") if p.data_publicacao else ""
        resumo = (p.search_description or "").strip()
        url = p.url or "/"
        if base_url and url.startswith("/"):
            url = f"{base_url}{url}"
        bloco = (
            f"<h3 style='margin:0 0 6px 0;'><a href='{url}'>{p.title}</a></h3>"
            f"<p style='margin:0 0 8px 0;color:#64748b'>Data: {data}</p>"
        )
        if resumo:
            bloco += f"<p style='margin:0 0 12px 0'>{resumo}</p>"
        blocos.append(bloco)
    return "".join(blocos)


def criar_disparo_publicacoes(site, publicacoes, tipo):
    if not publicacoes:
        return None

    if tipo == DisparoEmail.TIPO_PUBLICACOES_IMEDIATA:
        assunto = f"Nova publicação: {publicacoes[0].title}"
    else:
        assunto = "Últimas publicações no site"

    corpo = (
        "<p>Confira as últimas publicações:</p>"
        f"{_resumo_publicacoes_html(publicacoes)}"
    )
    disparo = DisparoEmail.objects.create(
        tipo=tipo,
        segmento=DisparoEmail.SEG_NEWSLETTER,
        assunto=assunto,
        corpo_html=corpo,
        metadata={"site_id": site.id, "publicacoes_ids": [p.id for p in publicacoes]},
    )
    return executar_disparo(disparo)


def enviar_publicacoes_imediata(site, publicacao):
    config = ConfiguracaoSite.for_site(site)
    if (
        config.notificacao_publicacoes_modo
        != ConfiguracaoSite.NOTIFICACAO_PUBLICACOES_IMEDIATA
    ):
        return None
    disparo = criar_disparo_publicacoes(
        site,
        [publicacao],
        DisparoEmail.TIPO_PUBLICACOES_IMEDIATA,
    )
    if disparo:
        config.notificacao_publicacoes_ultimo_envio_em = timezone.now()
        config.save(update_fields=["notificacao_publicacoes_ultimo_envio_em"])
    return disparo


def enviar_publicacoes_periodicas(site, forcar=False):
    config = ConfiguracaoSite.for_site(site)
    if (
        config.notificacao_publicacoes_modo
        != ConfiguracaoSite.NOTIFICACAO_PUBLICACOES_PERIODICA
        and not forcar
    ):
        return None

    agora = timezone.now()
    ultimo = config.notificacao_publicacoes_ultimo_envio_em
    periodo_horas = max(1, int(config.notificacao_publicacoes_periodo_horas or 168))

    if not forcar and ultimo:
        proximo = ultimo + timedelta(hours=periodo_horas)
        if agora < proximo:
            return None

    inicio = ultimo or (agora - timedelta(hours=periodo_horas))
    publicacoes = PublicacaoPage.objects.live().public().order_by("-data_publicacao", "-first_published_at")
    if inicio:
        publicacoes = publicacoes.filter(first_published_at__gt=inicio)
    publicacoes = list(publicacoes[:20])

    if not publicacoes:
        if forcar:
            config.notificacao_publicacoes_ultimo_envio_em = agora
            config.save(update_fields=["notificacao_publicacoes_ultimo_envio_em"])
        return None

    disparo = criar_disparo_publicacoes(
        site,
        publicacoes,
        DisparoEmail.TIPO_PUBLICACOES_PERIODICA,
    )
    if disparo:
        meta = dict(disparo.metadata or {})
        meta["janela_inicio"] = inicio.isoformat() if inicio else ""
        meta["janela_fim"] = agora.isoformat()
        disparo.metadata = meta
        disparo.save(update_fields=["metadata"])
    if disparo:
        config.notificacao_publicacoes_ultimo_envio_em = agora
        config.save(update_fields=["notificacao_publicacoes_ultimo_envio_em"])
    return disparo


def enviar_publicacoes_periodicas_todos_sites():
    resultados = []
    for site in Site.objects.all():
        disparo = enviar_publicacoes_periodicas(site, forcar=False)
        if disparo:
            resultados.append(disparo)
    return resultados
