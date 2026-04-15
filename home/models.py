from django.db import models

from wagtail.admin.panels import FieldPanel
from wagtail.models import Page
from modelcluster.fields import ParentalKey
from wagtail.models import Orderable
from wagtail.admin.panels import InlinePanel
from conteudo.models import PublicacaoPage

class HomePageCarrosselItem(Orderable):
    home_page = ParentalKey(
        "home.HomePage",
        related_name="itens_carrossel_home",
        on_delete=models.CASCADE,
    )
    publicacao = models.ForeignKey(
        "conteudo.PublicacaoPage",
        verbose_name="Publicacao",
        on_delete=models.CASCADE,
        related_name="+",
    )
    imagem = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Imagem do carrossel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    panels = [
        FieldPanel("publicacao"),
        FieldPanel("imagem"),
    ]

    @property
    def imagem_exibicao(self):
        if self.imagem:
            return self.imagem

        if self.publicacao and getattr(self.publicacao, "imagem_capa", None):
            return self.publicacao.imagem_capa

        return None

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Item do carrossel da home"
        verbose_name_plural = "Itens do carrossel da home"

    def __str__(self):
        return self.publicacao.title if self.publicacao else "Item do carrossel"


class HomePageDestaqueItem(Orderable):
    home_page = ParentalKey(
        "home.HomePage",
        related_name="itens_destaque_home",
        on_delete=models.CASCADE,
    )
    publicacao = models.ForeignKey(
        "conteudo.PublicacaoPage",
        verbose_name="Publicacao",
        on_delete=models.CASCADE,
        related_name="+",
    )

    panels = [
        FieldPanel("publicacao"),
    ]

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Item de destaque da home"
        verbose_name_plural = "Itens de destaque da home"

    def __str__(self):
        return self.publicacao.title if self.publicacao else "Item de destaque"

class HomePage(Page):
    mostrar_carrossel_home = models.BooleanField(
        "Mostrar carrossel na home",
        default=True,
    )
    titulo_carrossel_home = models.CharField(
        "Titulo do carrossel",
        max_length=255,
        default="Publicacoes em destaque",
        blank=True,
    )
    quantidade_itens_carrossel_home = models.PositiveIntegerField(
        "Quantidade de itens do carrossel",
        default=3,
    )

    tempo_transicao_carrossel_home = models.PositiveIntegerField(
        "Tempo de transicao do carrossel em segundos",
        default=5,
    )

    mostrar_destaques_home = models.BooleanField(
        "Mostrar destaques na home",
        default=True,
    )
    titulo_destaques_home = models.CharField(
        "Titulo da secao de destaques",
        max_length=255,
        default="Destaques",
        blank=True,
    )

    mostrar_ultimas_publicacoes_home = models.BooleanField(
        "Mostrar ultimas publicacoes na home",
        default=True,
    )
    titulo_ultimas_publicacoes_home = models.CharField(
        "Titulo da secao de ultimas publicacoes",
        max_length=255,
        default="Ultimas publicacoes",
        blank=True,
    )
    quantidade_ultimas_publicacoes_home = models.PositiveIntegerField(
        "Quantidade de ultimas publicacoes",
        default=5,
    )

    max_count = 1

    content_panels = Page.content_panels + [
        FieldPanel("mostrar_carrossel_home"),
        FieldPanel("titulo_carrossel_home"),
        FieldPanel("quantidade_itens_carrossel_home"),
        FieldPanel("tempo_transicao_carrossel_home"),

        InlinePanel("itens_carrossel_home", label="Itens do carrossel da home"),

        FieldPanel("mostrar_destaques_home"),
        FieldPanel("titulo_destaques_home"),
        InlinePanel("itens_destaque_home", label="Itens de destaque da home"),

        FieldPanel("mostrar_ultimas_publicacoes_home"),
        FieldPanel("titulo_ultimas_publicacoes_home"),
        FieldPanel("quantidade_ultimas_publicacoes_home"),
    ]

    def get_context(self, request):
        context = super().get_context(request)

        itens_carrossel_home = [
            item
            for item in self.itens_carrossel_home.select_related("publicacao", "imagem").all()
            if item.publicacao and item.publicacao.live
        ]

        if self.quantidade_itens_carrossel_home:
            itens_carrossel_home = itens_carrossel_home[: self.quantidade_itens_carrossel_home]

        destaques_publicacoes = [
            item.publicacao
            for item in self.itens_destaque_home.select_related("publicacao").all()
            if item.publicacao and item.publicacao.live
        ]

        ids_destaques_home = [publicacao.id for publicacao in destaques_publicacoes]

        todas_ultimas_publicacoes_home = list(
            PublicacaoPage.objects.live()
            .public()
            .exclude(id__in=ids_destaques_home)
            .order_by("-first_published_at")
        )

        quantidade_inicial = self.quantidade_ultimas_publicacoes_home or 5
        ultimas_publicacoes_home = todas_ultimas_publicacoes_home[:quantidade_inicial]

        context["itens_carrossel_home"] = itens_carrossel_home
        context["destaques_publicacoes"] = destaques_publicacoes
        context["ultimas_publicacoes_home"] = ultimas_publicacoes_home
        context["todas_ultimas_publicacoes_home"] = todas_ultimas_publicacoes_home
        context["quantidade_inicial_ultimas_home"] = quantidade_inicial

        return context
