from django.contrib.syndication.views import Feed
from django.utils.html import strip_tags
from django.utils.feedgenerator import Rss201rev2Feed

from .models import PublicacaoPage


class UTF8RssFeed(Rss201rev2Feed):
    content_type = "application/rss+xml; charset=utf-8"


class PublicacoesRSSFeed(Feed):
    feed_type = UTF8RssFeed
    title = "OwnPaper - Publicações"
    description = "Publicações mais recentes do site."
    link = "/"

    def items(self):
        return (
            PublicacaoPage.objects.live()
            .public()
            .order_by("-data_publicacao", "-first_published_at")[:30]
        )

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return strip_tags(item.resumo or "")[:1200]

    def item_link(self, item):
        return item.url

    def item_pubdate(self, item):
        return item.first_published_at

    def item_author_name(self, item):
        nomes = [str(autor) for autor in item.autores_ordenados]
        return "; ".join(nomes)[:255] if nomes else ""
