from django.contrib.sitemaps import Sitemap

from home.models import HomePage

from .models import Autor, Categoria, PublicacaoPage, TagPublicacao


def normalizar_para_data(valor):
    if not valor:
        return None

    if hasattr(valor, "date"):
        try:
            return valor.date()
        except TypeError:
            return valor

    return valor


class HomePageSitemap(Sitemap):
    changefreq = "weekly"
    priority = 1.0

    def items(self):
        return HomePage.objects.live()

    def location(self, obj):
        return obj.url

    def lastmod(self, obj):
        return normalizar_para_data(obj.last_published_at or obj.first_published_at)


class PublicacaoPageSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return PublicacaoPage.objects.live().order_by("-data_publicacao", "-first_published_at")

    def location(self, obj):
        return obj.url

    def lastmod(self, obj):
        return normalizar_para_data(
            obj.data_atualizacao or obj.data_publicacao or obj.last_published_at or obj.first_published_at
        )


class CategoriaSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Categoria.objects.all().order_by("nome")

    def location(self, obj):
        return f"/categorias/{obj.slug}/"

    def lastmod(self, obj):
        return None


class TagPublicacaoSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return TagPublicacao.objects.all().order_by("name")

    def location(self, obj):
        return f"/tags/{obj.slug}/"

    def lastmod(self, obj):
        return None


class AutorSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Autor.objects.all().order_by("nome_completo")

    def location(self, obj):
        return f"/autores/{obj.username}/"

    def lastmod(self, obj):
        return None


sitemaps = {
    "home": HomePageSitemap,
    "publicacoes": PublicacaoPageSitemap,
    "categorias": CategoriaSitemap,
    "tags": TagPublicacaoSitemap,
    "autores": AutorSitemap,
}
