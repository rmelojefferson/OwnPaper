from django import template
from django.urls import reverse
from wagtail.admin.views.pages.utils import get_breadcrumbs_items_for_page
from wagtail.models import Site


register = template.Library()


def _resolver_site(request):
    return (
        Site.find_for_request(request)
        or Site.objects.filter(is_default_site=True).first()
        or Site.objects.first()
    )


@register.simple_tag(takes_context=True)
def ownpaper_explorer_title(context, page, fallback_title):
    request = context.get("request")
    site = _resolver_site(request) if request is not None else None
    if site is not None and page is not None and page.id == site.root_page_id:
        return "Páginas"
    return fallback_title


@register.simple_tag(takes_context=True)
def ownpaper_explorer_breadcrumbs(context, page):
    request = context.get("request")
    site = _resolver_site(request) if request is not None else None
    if site is not None and page is not None and page.id == site.root_page_id:
        return [{"label": "Páginas"}]
    return None


@register.simple_tag
def ownpaper_is_publicacoes_index(page):
    return bool(
        page
        and getattr(getattr(page, "content_type", None), "model", "") == "publicacoesindexpage"
    )


@register.simple_tag
def ownpaper_is_publicacao(page):
    return bool(
        page
        and getattr(getattr(page, "content_type", None), "model", "") == "publicacaopage"
    )


@register.simple_tag(takes_context=True)
def ownpaper_page_breadcrumbs(context, page):
    request = context.get("request")
    if request is None or page is None:
        return []

    items = get_breadcrumbs_items_for_page(page, request.user)
    pages = list(
        page.get_ancestors(inclusive=True)
        .specific(defer=True)
    )

    for item, page_item in zip(items, pages):
        if ownpaper_is_publicacoes_index(page_item):
            item["url"] = reverse("admin_publicacoes_lista")
            item["label"] = "Publicações"

    return items
