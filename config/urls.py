from django.conf import settings
from django.urls import include, path
from django.contrib.sitemaps.views import sitemap
from conteudo.sitemaps import sitemaps
from django.contrib import admin
from django.contrib.auth import views as auth_views
from two_factor.urls import urlpatterns as tf_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls
from django.views.generic import RedirectView
from conteudo import views as conteudo_views

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path(
        "admin/login/",
        RedirectView.as_view(url="/account/login/", permanent=False),
    ),
    path("admin/pages/", conteudo_views.admin_pages_redirect_view),
    path("admin/pages/<int:page_id>/", conteudo_views.admin_publicacoes_index_redirect_view),
    path("admin/sites/", conteudo_views.admin_sites_redirect_view),
    path("admin/sites/<path:subpath>/", conteudo_views.admin_sites_redirect_view),
    path(
        "admin/settings/conteudo/configuracaosite/<int:site_id>/",
        RedirectView.as_view(url="/admin/configuracoes-site/", permanent=False),
    ),
    path(
        "admin/users/",
        RedirectView.as_view(pattern_name="admin_usuarios_lista", permanent=False),
    ),
    path(
        "admin/users/<path:subpath>/",
        RedirectView.as_view(pattern_name="admin_usuarios_lista", permanent=False),
    ),
    path(
        "admin/snippets/conteudo/perguntaquizcatalogo/",
        RedirectView.as_view(pattern_name="admin_quiz_catalogo_lista", permanent=False),
    ),
    path(
        "admin/aceite-termos-painel/",
        conteudo_views.admin_aceite_termos_painel_view,
        name="admin_aceite_termos_painel",
    ),
    path("admin/", include(wagtailadmin_urls)),
    path(
        "account/password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.txt",
            html_email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "account/password-reset/enviado/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "account/password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
        ),
        name="password_reset_confirm",
    ),
    path(
        "account/password-reset/completo/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path("documents/", include(wagtaildocs_urls)),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("",include(tf_urls)),
    path("", include("conteudo.urls")),
    path("", include(wagtail_urls)),
]

if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Serve static and media files from development server
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
