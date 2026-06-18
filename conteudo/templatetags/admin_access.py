from django import template
from django.urls import reverse


register = template.Library()


@register.filter
def user_in_group(user, group_name):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return user.groups.filter(name=group_name).exists()


@register.simple_tag
def admin_site_pages_url(request):
    from wagtail.models import Site

    site = (
        getattr(request, "site", None)
        or Site.find_for_request(request)
        or Site.objects.filter(is_default_site=True).first()
        or Site.objects.first()
    )
    if site and site.root_page_id:
        return reverse("wagtailadmin_explore", args=[site.root_page_id])
    return reverse("wagtailadmin_explore_root")


@register.simple_tag
def admin_dashboard_context(user):
    if not user or not getattr(user, "is_authenticated", False):
        return {}

    from django.contrib.auth import get_user_model
    from django.db.models import Avg, Sum

    from conteudo.access import is_admin, is_operator
    from wagtail.documents import get_document_model
    from wagtail.images import get_image_model
    from wagtail.models import Page

    from conteudo.models import (
        Autor,
        ComentarioPublicacao,
        EstatisticaTempoSite,
        MensagemContato,
        PublicacaoComentarioRevisao,
        PublicacaoPage,
    )

    dashboard = {
        "pode_ver_contato": False,
        "mensagens_pendentes": 0,
        "comentarios_pendentes": 0,
        "publicacoes_ajustes_autor": 0,
        "comentarios_revisao_abertos": 0,
        "pode_ver_comentarios": False,
        "estatisticas": None,
    }

    autor = Autor.objects.filter(usuario_admin=user).first()
    if autor:
        publicacoes_autor = PublicacaoPage.objects.filter(autores_publicacao__autor=autor).distinct()
        dashboard["publicacoes_ajustes_autor"] = publicacoes_autor.filter(
            status_editorial=PublicacaoPage.STATUS_EDITORIAL_AJUSTES
        ).count()
        dashboard["comentarios_revisao_abertos"] = PublicacaoComentarioRevisao.objects.filter(
            publicacao__in=publicacoes_autor,
            resolvido=False,
        ).count()

    if is_admin(user) or is_operator(user):
        mensagens = MensagemContato.objects.filter(
            status__in=[
                MensagemContato.STATUS_NOVO,
                MensagemContato.STATUS_EM_ANDAMENTO,
            ]
        )
        if not is_admin(user):
            mensagens = mensagens.filter(atribuido_para=user)
        dashboard["pode_ver_contato"] = True
        dashboard["mensagens_pendentes"] = mensagens.count()

    if is_admin(user):
        comentarios_pendentes = ComentarioPublicacao.objects.filter(
            status=ComentarioPublicacao.STATUS_PENDENTE
        ).count()
        total_leituras = PublicacaoPage.objects.aggregate(
            total=Sum("total_visualizacoes")
        )["total"] or 0
        tempo_medio = EstatisticaTempoSite.objects.filter(duration_seconds__gte=5).aggregate(
            media=Avg("duration_seconds")
        )["media"] or 0
        User = get_user_model()
        Image = get_image_model()
        Document = get_document_model()
        dashboard.update(
            {
                "pode_ver_comentarios": True,
                "comentarios_pendentes": comentarios_pendentes,
                "estatisticas": {
                    "leituras": total_leituras,
                    "publicacoes": PublicacaoPage.objects.filter(live=True).count(),
                    "comentarios": ComentarioPublicacao.objects.count(),
                    "comentarios_pendentes": comentarios_pendentes,
                    "mensagens": MensagemContato.objects.count(),
                    "mensagens_pendentes": dashboard["mensagens_pendentes"],
                    "usuarios": User.objects.filter(is_active=True).count(),
                    "tempo_medio": _format_duration(tempo_medio),
                },
                "resumo": {
                    "paginas": Page.objects.live().count(),
                    "imagens": Image.objects.count(),
                    "documentos": Document.objects.count(),
                },
            }
        )

    return dashboard


def _format_duration(seconds):
    seconds = int(seconds or 0)
    minutes, rest = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}min"
    if minutes:
        return f"{minutes}min {rest}s"
    return f"{rest}s"
