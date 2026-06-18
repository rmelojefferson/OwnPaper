from django.db import models
from django.db.models import Count, Q
from django.core.paginator import Paginator

from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.models import Page
from modelcluster.fields import ParentalKey
from wagtail.models import Orderable
from wagtail.admin.panels import InlinePanel
from conteudo.models import PublicacaoPage

PROMOTE_PANELS_SEM_MENU_SITE = [
    MultiFieldPanel(
        ["slug", "seo_title", "search_description"],
        heading="Para motores de busca",
        classname="collapsed",
    )
]

class HomePageCarrosselItem(Orderable):
    home_page = ParentalKey(
        "home.HomePage",
        related_name="itens_carrossel_home",
        on_delete=models.CASCADE,
    )
    publicacao = models.ForeignKey(
        "conteudo.PublicacaoPage",
        verbose_name="Publicação",
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
        verbose_name="Publicação",
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
        "Título do carrossel",
        max_length=255,
        default="Publicações em destaque",
        blank=True,
    )
    quantidade_itens_carrossel_home = models.PositiveIntegerField(
        "Quantidade de itens do carrossel",
        default=3,
    )

    tempo_transicao_carrossel_home = models.PositiveIntegerField(
        "Tempo de transição do carrossel em segundos",
        default=5,
    )

    mostrar_destaques_home = models.BooleanField(
        "Mostrar destaques na home",
        default=True,
    )
    titulo_destaques_home = models.CharField(
        "Título da seção de destaques",
        max_length=255,
        default="Destaques",
        blank=True,
    )

    mostrar_ultimas_publicacoes_home = models.BooleanField(
        "Mostrar últimas publicações na home",
        default=True,
    )
    titulo_ultimas_publicacoes_home = models.CharField(
        "Título da seção de últimas publicações",
        max_length=255,
        default="Últimas publicações",
        blank=True,
    )
    quantidade_ultimas_publicacoes_home = models.PositiveIntegerField(
        "Quantidade de últimas publicações",
        default=5,
    )
    itens_por_pagina_ultimas_home = models.PositiveIntegerField(
        "Itens por página (últimas publicações)",
        default=10,
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
        FieldPanel("itens_por_pagina_ultimas_home"),
    ]
    promote_panels = PROMOTE_PANELS_SEM_MENU_SITE

    def get_context(self, request):
        context = super().get_context(request)

        publicacoes_metricas_qs = (
            PublicacaoPage.objects.live()
            .public()
            .annotate(
                comentarios_aprovados_total=Count(
                    "comentarios_publicacao",
                    filter=Q(
                        comentarios_publicacao__status="aprovado",
                    ),
                    distinct=True,
                )
            )
        )
        publicacoes_metricas_map = {
            item.id: item
            for item in publicacoes_metricas_qs
        }

        itens_carrossel_home = [
            item
            for item in self.itens_carrossel_home.select_related("publicacao", "imagem").all()
            if item.publicacao and item.publicacao.live and item.publicacao.id in publicacoes_metricas_map
        ]
        for item in itens_carrossel_home:
            item.publicacao = publicacoes_metricas_map[item.publicacao.id]

        if self.quantidade_itens_carrossel_home:
            itens_carrossel_home = itens_carrossel_home[: self.quantidade_itens_carrossel_home]

        destaques_publicacoes = [
            publicacoes_metricas_map[item.publicacao.id]
            for item in self.itens_destaque_home.select_related("publicacao").all()
            if item.publicacao and item.publicacao.live and item.publicacao.id in publicacoes_metricas_map
        ]

        ids_destaques_home = [publicacao.id for publicacao in destaques_publicacoes]

        todas_ultimas_publicacoes_home_qs = (
            publicacoes_metricas_qs
            .exclude(id__in=ids_destaques_home)
            .order_by("-first_published_at")
        )

        quantidade_inicial = self.quantidade_ultimas_publicacoes_home or 5
        ultimas_publicacoes_home = list(todas_ultimas_publicacoes_home_qs[:quantidade_inicial])
        pagina_ultimas = (request.GET.get("pagina_ultimas") or "").strip()
        try:
            itens_por_pagina = max(1, int(self.itens_por_pagina_ultimas_home or 10))
        except (TypeError, ValueError):
            itens_por_pagina = 10
        paginador_ultimas = Paginator(todas_ultimas_publicacoes_home_qs, itens_por_pagina)
        page_obj_ultimas = paginador_ultimas.get_page(pagina_ultimas)
        mostrar_destaques_na_home = page_obj_ultimas.number == 1

        context["itens_carrossel_home"] = itens_carrossel_home
        context["destaques_publicacoes"] = (
            destaques_publicacoes if mostrar_destaques_na_home else []
        )
        context["ultimas_publicacoes_home"] = ultimas_publicacoes_home
        context["todas_ultimas_publicacoes_home"] = list(page_obj_ultimas.object_list)
        context["quantidade_inicial_ultimas_home"] = quantidade_inicial
        context["ultimas_home_paginacao"] = page_obj_ultimas
        context["mostrar_destaques_na_home"] = mostrar_destaques_na_home

        return context
