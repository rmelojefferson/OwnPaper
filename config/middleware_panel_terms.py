from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from conteudo.models import UsuarioPainelPerfil


class PanelTermsConsentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "OWNPAPER_PANEL_TERMS_REQUIRED", True):
            return self.get_response(request)

        path = request.path or ""
        if not path.startswith(("/admin/", "/django-admin/")):
            return self.get_response(request)

        allowed_prefixes = (
            "/admin/aceite-termos-painel/",
            "/admin/logout/",
            "/admin/login/",
            "/account/",
        )
        if path.startswith(allowed_prefixes):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return self.get_response(request)

        if not user.is_staff:
            return self.get_response(request)

        perfil, _ = UsuarioPainelPerfil.objects.get_or_create(usuario=user)
        if perfil.aceitou_termos_painel_atuais():
            return self.get_response(request)

        return redirect(f"{reverse('admin_aceite_termos_painel')}?next={path}")
