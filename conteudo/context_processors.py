from django.conf import settings
from wagtail.models import Site

from .models import Categoria, ConfiguracaoSite


def menu_categorias(request):
    return {
        "categorias_menu": Categoria.objects.all().order_by("nome"),
    }


def configuracao_site(request):
    try:
        site = Site.find_for_request(request)
        if not site:
            config_site = None
        else:
            config_site = ConfiguracaoSite.for_site(site)
    except Exception:
        config_site = None

    return {
        "config_site": config_site,
        "site_lang": getattr(request, "LANGUAGE_CODE", "pt-br"),
        "TURNSTILE_ENABLED": settings.TURNSTILE_ENABLED,
        "TURNSTILE_SITE_KEY": settings.TURNSTILE_SITE_KEY,
    }
