from django.shortcuts import render
from wagtail.models import Site

from conteudo.models import ConfiguracaoSite


class PublicMaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Rotas internas e tecnicas que nao devem ser bloqueadas
        caminhos_liberados = (
            "/admin/",
            "/django-admin/",
            "/documents/",
            "/account/",
            "/static/",
            "/media/",
            "/favicon.ico",
        )

        if path.startswith(caminhos_liberados):
            return self.get_response(request)

        site = Site.find_for_request(request)
        if not site:
            return self.get_response(request)

        config_site = ConfiguracaoSite.for_site(site)
        if not config_site or not config_site.modo_manutencao_ativo:
            return self.get_response(request)

        return render(
            request,
            "manutencao_site.html",
            {
                "config_site": config_site,
            },
            status=503,
        )
