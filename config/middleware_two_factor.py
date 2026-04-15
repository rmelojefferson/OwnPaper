from django.shortcuts import redirect
from django.urls import reverse
from django_otp import devices_for_user


class PanelTwoFactorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Deixa o proprio fluxo do two-factor funcionar sem interferencia
        if path.startswith("/account/"):
            return self.get_response(request)

        # Se nao esta autenticado, nao decide nada aqui
        if not request.user.is_authenticated:
            return self.get_response(request)

        acessando_wagtail_admin = path.startswith("/admin/")
        acessando_django_admin = path.startswith("/django-admin/")

        pode_acessar_wagtail_admin = (
            request.user.is_superuser
            or request.user.has_perm("wagtailadmin.access_admin")
        )

        pode_acessar_django_admin = (
            request.user.is_superuser
            or request.user.is_staff
        )

        # Protege qualquer acesso ao painel do Wagtail
        if acessando_wagtail_admin and pode_acessar_wagtail_admin:
            if getattr(request.user, "is_verified", lambda: False)():
                return self.get_response(request)

            possui_dispositivo = any(devices_for_user(request.user, confirmed=True))

            if possui_dispositivo:
                return redirect(reverse("two_factor:login"))

            return redirect(reverse("two_factor:profile"))

        # Protege tambem o admin classico do Django
        if acessando_django_admin and pode_acessar_django_admin:
            if getattr(request.user, "is_verified", lambda: False)():
                return self.get_response(request)

            possui_dispositivo = any(devices_for_user(request.user, confirmed=True))

            if possui_dispositivo:
                return redirect(reverse("two_factor:login"))

            return redirect(reverse("two_factor:profile"))

        return self.get_response(request)
