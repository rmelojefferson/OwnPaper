from django.conf import settings
from django.urls import include, path
from django.contrib.sitemaps.views import sitemap
from conteudo.sitemaps import sitemaps
from django.contrib import admin
from two_factor.urls import urlpatterns as tf_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls
from search import views as search_views
from django.views.generic import RedirectView

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path(
        "admin/login/",
        RedirectView.as_view(url="/account/login/", permanent=False),
    ),
    path("admin/", include(wagtailadmin_urls)),
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
