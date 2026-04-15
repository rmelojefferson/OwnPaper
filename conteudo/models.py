import csv
import io


from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from modelcluster.models import ClusterableModel
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from modelcluster.contrib.taggit import ClusterTaggableManager
from taggit.models import ItemBase, TagBase
from wagtail.admin.panels import FieldPanel, HelpPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page, Orderable
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting

@register_setting
class ConfiguracaoSite(BaseSiteSetting):
    nome_site = models.CharField("Nome do site", max_length=255, blank=True)
    seo_title_padrao = models.CharField("Título SEO padrão", max_length=255, blank=True)
    descricao_padrao = models.TextField("Descrição padrão", blank=True)
    imagem_compartilhamento_padrao = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Imagem padrão de compartilhamento",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    favicon = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Favicon",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    texto_rodape = models.TextField("Texto do rodapé", blank=True)
    email_contato = models.EmailField("E-mail de contato", blank=True)
    copyright_texto = models.CharField("Texto de copyright", max_length=255, blank=True)

    pagina_sobre = models.ForeignKey(
        "wagtailcore.Page",
        verbose_name="Página Sobre",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    pagina_privacidade = models.ForeignKey(
        "wagtailcore.Page",
        verbose_name="Página de Privacidade e Dados",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    pagina_cookies = models.ForeignKey(
        "wagtailcore.Page",
        verbose_name="Página de Cookies",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    pagina_contato = models.ForeignKey(
        "wagtailcore.Page",
        verbose_name="Página de Contato",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    pagina_newsletter = models.ForeignKey(
        "wagtailcore.Page",
        verbose_name="Página de Newsletter",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    pagina_indexador = models.ForeignKey(
        "wagtailcore.Page",
        verbose_name="Pagina do Indexador",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    rotulo_indexador = models.CharField(
        "Rotulo do link do indexador",
        max_length=255,
        default="Indexador",
        blank=True,
    )

    modo_manutencao_ativo = models.BooleanField(
        "Modo manutencao ativo",
        default=False,
    )
    modo_manutencao_titulo = models.CharField(
        "Titulo da manutencao",
        max_length=255,
        default="Site em manutencao",
    )
    modo_manutencao_mensagem = models.TextField(
        "Mensagem da manutencao",
        default="Estamos realizando uma manutenção no momento. Tente novamente em alguns minutos.",
        blank=True,
    )

    google_search_console_verification = models.CharField(
        "Google Search Console verification",
        max_length=255,
        blank=True,
        help_text="Conteúdo do meta tag `google-site-verification` (somente o valor).",
    )
    meta_domain_verification = models.CharField(
        "Meta domain verification",
        max_length=255,
        blank=True,
        help_text="Conteúdo do meta tag `facebook-domain-verification` (somente o valor).",
    )
    google_analytics_id = models.CharField(
        "Google Analytics ID",
        max_length=32,
        blank=True,
        help_text="Exemplo: G-XXXXXXXXXX.",
    )
    google_tag_manager_id = models.CharField(
        "Google Tag Manager ID",
        max_length=32,
        blank=True,
        help_text="Exemplo: GTM-XXXXXXX.",
    )
    meta_pixel_id = models.CharField(
        "Meta Pixel ID",
        max_length=32,
        blank=True,
        help_text="Exemplo: 1234567890.",
    )
    usar_menu_customizado = models.BooleanField(
        "Usar menu customizado",
        default=False,
        help_text="Quando ativo, o menu principal passa a usar os grupos e subitens configurados abaixo.",
    )
    menu_home_exibir = models.BooleanField(
        "Exibir item Home no menu",
        default=True,
    )
    menu_home_primeiro_fixo = models.BooleanField(
        "Fixar Home sempre no primeiro item",
        default=True,
        help_text="Desative para ordenar a Home manualmente via Menu principal.",
    )
    menu_home_rotulo = models.CharField(
        "Rótulo da Home no menu",
        max_length=120,
        default="Início",
        blank=True,
    )
    menu_home_imagem = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Imagem/logo da Home no menu",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    menu_home_imagem_escala = models.PositiveSmallIntegerField(
        "Escala da imagem/logo da Home",
        default=1,
        choices=[(1, "1x"), (2, "2x"), (3, "3x"), (4, "4x"), (5, "5x")],
        help_text="Aplica aumento proporcional quando a Home usa imagem/logo no menu.",
    )

    panels = [
        FieldPanel("nome_site"),
        FieldPanel("seo_title_padrao"),
        FieldPanel("descricao_padrao"),
        FieldPanel("imagem_compartilhamento_padrao"),
        FieldPanel("favicon"),
        FieldPanel("texto_rodape"),
        FieldPanel("email_contato"),
        FieldPanel("copyright_texto"),
        FieldPanel("pagina_sobre"),
        FieldPanel("pagina_privacidade"),
        FieldPanel("pagina_cookies"),
	FieldPanel("pagina_contato"),
	FieldPanel("pagina_newsletter"),
        FieldPanel("pagina_indexador"),
        FieldPanel("rotulo_indexador"),
        FieldPanel("modo_manutencao_ativo"),
        FieldPanel("modo_manutencao_titulo"),
        FieldPanel("modo_manutencao_mensagem"),
        MultiFieldPanel(
            [
                FieldPanel("google_search_console_verification"),
                FieldPanel("meta_domain_verification"),
                FieldPanel("google_analytics_id"),
                FieldPanel("google_tag_manager_id"),
                FieldPanel("meta_pixel_id"),
            ],
            heading="Rastreamento e verificação",
        ),
        MultiFieldPanel(
            [
                FieldPanel("usar_menu_customizado"),
                FieldPanel("menu_home_exibir"),
                FieldPanel("menu_home_primeiro_fixo"),
                FieldPanel("menu_home_rotulo"),
                FieldPanel("menu_home_imagem"),
                FieldPanel("menu_home_imagem_escala"),
                HelpPanel(
                    content="Gerencie os grupos e subitens em Menu principal, no painel administrativo."
                ),
            ],
            heading="Menu customizado",
        ),
    ]

    class Meta:
        verbose_name = "Configuração do site"
        verbose_name_plural = "Configurações do site"


class MenuPrincipalGrupo(ClusterableModel):
    TIPO_AGRUPADOR = "agrupador"
    TIPO_PAGINA = "pagina"
    TIPO_URL = "url"
    TIPO_ATALHO = "atalho"
    TIPO_CHOICES = [
        (TIPO_AGRUPADOR, "Apenas agrupador"),
        (TIPO_PAGINA, "Página interna"),
        (TIPO_URL, "URL externa"),
        (TIPO_ATALHO, "Atalho do site"),
    ]
    ATALHO_HOME = "home"
    ATALHO_CATEGORIAS = "categorias"
    ATALHO_TAGS = "tags"
    ATALHO_AUTORES = "autores"
    ATALHO_BUSCA = "busca"
    ATALHO_DESTAQUES = "destaques"
    ATALHO_ULTIMAS = "ultimas"
    ATALHO_CONTATO = "contato"
    ATALHO_NEWSLETTER = "newsletter"
    ATALHO_INDEXADOR = "indexador"
    ATALHO_CHOICES = [
        (ATALHO_HOME, "Home"),
        (ATALHO_CATEGORIAS, "Categorias"),
        (ATALHO_TAGS, "Tags"),
        (ATALHO_AUTORES, "Autores"),
        (ATALHO_BUSCA, "Busca"),
        (ATALHO_DESTAQUES, "Âncora: Destaques"),
        (ATALHO_ULTIMAS, "Âncora: Últimas publicações"),
        (ATALHO_CONTATO, "Contato"),
        (ATALHO_NEWSLETTER, "Newsletter"),
        (ATALHO_INDEXADOR, "Indexador"),
    ]

    configuracao_site = models.ForeignKey(
        "conteudo.ConfiguracaoSite",
        related_name="menu_grupos",
        on_delete=models.CASCADE,
    )
    sort_order = models.PositiveIntegerField("Ordem", default=0)
    titulo = models.CharField("Título", max_length=120)
    tipo = models.CharField("Tipo", max_length=20, choices=TIPO_CHOICES, default=TIPO_AGRUPADOR)
    pagina = models.ForeignKey(
        "wagtailcore.Page",
        verbose_name="Página interna",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    url_externa = models.URLField("URL externa", blank=True)
    atalho = models.CharField("Atalho do site", max_length=30, choices=ATALHO_CHOICES, blank=True)
    abrir_nova_aba = models.BooleanField("Abrir em nova aba", default=False)

    panels = [
        FieldPanel("configuracao_site"),
        FieldPanel("sort_order"),
        FieldPanel("titulo"),
        FieldPanel("tipo"),
        FieldPanel("pagina"),
        FieldPanel("url_externa"),
        FieldPanel("atalho"),
        FieldPanel("abrir_nova_aba"),
        InlinePanel("subitens", label="Subitens"),
    ]

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Grupo do menu principal"
        verbose_name_plural = "Grupos do menu principal"

    def __str__(self):
        return self.titulo

    @property
    def url_resolvida(self):
        if self.tipo == self.TIPO_PAGINA and self.pagina:
            return self.pagina.url
        if self.tipo == self.TIPO_URL and self.url_externa:
            return self.url_externa
        if self.tipo == self.TIPO_ATALHO and self.atalho:
            return resolver_atalho_menu(self.configuracao_site, self.atalho)
        return ""

    @property
    def tem_link(self):
        return bool(self.url_resolvida)


class MenuPrincipalSubitem(Orderable):
    TIPO_PAGINA = "pagina"
    TIPO_URL = "url"
    TIPO_ATALHO = "atalho"
    TIPO_CHOICES = [
        (TIPO_PAGINA, "Página interna"),
        (TIPO_URL, "URL externa"),
        (TIPO_ATALHO, "Atalho do site"),
    ]

    grupo = ParentalKey(
        "conteudo.MenuPrincipalGrupo",
        related_name="subitens",
        on_delete=models.CASCADE,
    )
    titulo = models.CharField("Título", max_length=120)
    tipo = models.CharField("Tipo", max_length=20, choices=TIPO_CHOICES, default=TIPO_PAGINA)
    pagina = models.ForeignKey(
        "wagtailcore.Page",
        verbose_name="Página interna",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    url_externa = models.URLField("URL externa", blank=True)
    atalho = models.CharField(
        "Atalho do site",
        max_length=30,
        choices=MenuPrincipalGrupo.ATALHO_CHOICES,
        blank=True,
    )
    abrir_nova_aba = models.BooleanField("Abrir em nova aba", default=False)

    panels = [
        FieldPanel("titulo"),
        FieldPanel("tipo"),
        FieldPanel("pagina"),
        FieldPanel("url_externa"),
        FieldPanel("atalho"),
        FieldPanel("abrir_nova_aba"),
    ]

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Subitem do menu principal"
        verbose_name_plural = "Subitens do menu principal"

    def __str__(self):
        return self.titulo

    @property
    def url_resolvida(self):
        if self.tipo == self.TIPO_PAGINA and self.pagina:
            return self.pagina.url
        if self.tipo == self.TIPO_URL and self.url_externa:
            return self.url_externa
        if self.tipo == self.TIPO_ATALHO and self.atalho:
            return resolver_atalho_menu(self.grupo.configuracao_site, self.atalho)
        return ""

    @property
    def tem_link(self):
        return bool(self.url_resolvida)


class MenuPrincipalGrupoViewSet(SnippetViewSet):
    model = MenuPrincipalGrupo
    icon = "list-ul"
    menu_label = "Menu principal"
    menu_name = "menu-principal"
    list_display = ["titulo", "tipo", "configuracao_site", "sort_order"]
    search_fields = ["titulo", "url_externa"]
    ordering = ["configuracao_site", "sort_order", "titulo"]


register_snippet(MenuPrincipalGrupoViewSet)


def resolver_atalho_menu(config_site, atalho):
    if atalho == MenuPrincipalGrupo.ATALHO_HOME:
        return "/"
    if atalho == MenuPrincipalGrupo.ATALHO_CATEGORIAS:
        return "/categorias/"
    if atalho == MenuPrincipalGrupo.ATALHO_TAGS:
        return "/tags/"
    if atalho == MenuPrincipalGrupo.ATALHO_AUTORES:
        return "/autores/"
    if atalho == MenuPrincipalGrupo.ATALHO_BUSCA:
        return "/busca/"
    if atalho == MenuPrincipalGrupo.ATALHO_DESTAQUES:
        return "/#destaques"
    if atalho == MenuPrincipalGrupo.ATALHO_ULTIMAS:
        return "/#ultimas-publicacoes"
    if atalho == MenuPrincipalGrupo.ATALHO_CONTATO and config_site and config_site.pagina_contato:
        return config_site.pagina_contato.url
    if atalho == MenuPrincipalGrupo.ATALHO_NEWSLETTER and config_site and config_site.pagina_newsletter:
        return config_site.pagina_newsletter.url
    if atalho == MenuPrincipalGrupo.ATALHO_INDEXADOR and config_site and config_site.pagina_indexador:
        return config_site.pagina_indexador.url
    return ""

@register_snippet
class Autor(models.Model):
    nome_completo = models.CharField("Nome completo", max_length=255)
    nome_exibicao = models.CharField("Nome de exibição", max_length=255, blank=True)
    username = models.SlugField("Nome de usuário", max_length=80, unique=True)
    usuario_admin = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="Usuário admin vinculado",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="autor_vinculado",
        limit_choices_to={"is_staff": True},
        help_text="Opcional. Vincule um usuário administrador a este autor para controle editorial por autor.",
    )
    orcid = models.CharField("ORCID", max_length=19, blank=True)
    email = models.EmailField("E-mail", blank=True)
    instagram = models.CharField("Instagram", max_length=255, blank=True)
    foto = models.ForeignKey(
       "wagtailimages.Image",
        verbose_name="Foto",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    mini_bio = models.TextField("Mini bio", blank=True)
    lattes_url = models.URLField("Link do Lattes", blank=True)

    panels = [
        FieldPanel("nome_completo"),
        FieldPanel("nome_exibicao"),
        FieldPanel("username"),
        FieldPanel("usuario_admin"),
        FieldPanel("orcid"),
        FieldPanel("email"),
        FieldPanel("instagram"),
	FieldPanel("foto"),
        FieldPanel("mini_bio"),
        FieldPanel("lattes_url"),
    ]

    class Meta:
        verbose_name = "Autor"
        verbose_name_plural = "Autores"
        ordering = ["nome_completo"]

    def __str__(self):
        return self.nome_exibicao or self.nome_completo

    @property
    def instagram_url(self):
        if not self.instagram:
            return ""
        if self.instagram.startswith(("http://", "https://")):
            return self.instagram
        username = self.instagram.lstrip("@").strip()
        return f"https://www.instagram.com/{username}/" if username else ""

    @property
    def orcid_url(self):
        if not self.orcid:
            return ""
        if self.orcid.startswith(("http://", "https://")):
            return self.orcid
        return f"https://orcid.org/{self.orcid}"

@register_snippet
class Categoria(models.Model):
    nome = models.CharField("Nome", max_length=255)
    slug = models.SlugField("Slug", max_length=255, unique=True)
    descricao = models.TextField("Descrição", blank=True)

    panels = [
        FieldPanel("nome"),
        FieldPanel("slug"),
        FieldPanel("descricao"),
    ]

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

@register_snippet
class TagPublicacao(TagBase):
    free_tagging = False

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
    ]

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
        ordering = ["name"]

    def __str__(self):
        return self.name

class ReferenciaPublicacao(Orderable):
    publicacao = ParentalKey(
        "conteudo.PublicacaoPage",
        related_name="referencias",
        on_delete=models.CASCADE,
    )

    marcador = models.CharField(
        "Marcador",
        max_length=20,
        blank=True,
        help_text="Use no corpo do texto como [[r:marcador]]. Exemplo: se o marcador for 1, use [[r:1]].",
    )
    usar_et_al = models.BooleanField("Usar et al.", default=False)

    autor1_nome = models.CharField("Nome do autor 1", max_length=255, blank=True)
    autor1_sobrenome = models.CharField("Sobrenome do autor 1", max_length=255, blank=True)

    autor2_nome = models.CharField("Nome do autor 2", max_length=255, blank=True)
    autor2_sobrenome = models.CharField("Sobrenome do autor 2", max_length=255, blank=True)

    autor3_nome = models.CharField("Nome do autor 3", max_length=255, blank=True)
    autor3_sobrenome = models.CharField("Sobrenome do autor 3", max_length=255, blank=True)

    titulo_obra = models.CharField("Título da obra", max_length=500)
    subtitulo = models.CharField("Subtítulo", max_length=500, blank=True)
    tipo_midia = models.CharField("Tipo de mídia", max_length=120, blank=True)
    editora = models.CharField("Editora", max_length=255, blank=True)
    local_publicacao = models.CharField("Local de publicação", max_length=255, blank=True)
    ano = models.CharField("Ano", max_length=20, blank=True)
    paginas = models.CharField("Páginas", max_length=120, blank=True)
    url = models.URLField("URL", blank=True)
    observacoes = models.TextField("Observações", blank=True)

    panels = [
        HelpPanel(
            content=(
                "Use o marcador para citar esta referencia no corpo do texto com "
                "[[r:marcador]]. Exemplo: [[r:1]]."
            )
        ),
        FieldPanel("marcador"),
        MultiFieldPanel([
            FieldPanel("autor1_nome"),
            FieldPanel("autor1_sobrenome"),
            FieldPanel("autor2_nome"),
            FieldPanel("autor2_sobrenome"),
            FieldPanel("autor3_nome"),
            FieldPanel("autor3_sobrenome"),
            FieldPanel("usar_et_al"),
        ], heading="Autores"),
        FieldPanel("titulo_obra"),
        FieldPanel("subtitulo"),
        FieldPanel("tipo_midia"),
        FieldPanel("editora"),
        FieldPanel("local_publicacao"),
        FieldPanel("ano"),
        FieldPanel("paginas"),
        FieldPanel("url"),
        FieldPanel("observacoes"),
    ]

    def _formatar_autor(self, nome, sobrenome):
        nome = (nome or "").strip()
        sobrenome = (sobrenome or "").strip()

        if not nome and not sobrenome:
            return ""

        if sobrenome and nome:
            return f"{sobrenome.upper()}, {nome}"

        if sobrenome:
            return sobrenome.upper()

        return nome

    @property
    def autores_estruturados(self):
        autores = []

        for i in range(1, 4):
            autor = self._formatar_autor(
                getattr(self, f"autor{i}_nome"),
                getattr(self, f"autor{i}_sobrenome"),
            )
            if autor:
                autores.append(autor)

        return autores

    @property
    def autores_formatados(self):
        autores = self.autores_estruturados

        if autores:
            if self.usar_et_al:
                return f"{autores[0]} et al."
            return "; ".join(autores)

        return ""

    class Meta:
        verbose_name = "Referência"
        verbose_name_plural = "Referências"

    def __str__(self):
        return self.titulo_obra

class PublicacaoPageTag(ItemBase):
    tag = models.ForeignKey(
        "conteudo.TagPublicacao",
        related_name="tagged_publicacoes",
        on_delete=models.CASCADE,
    )
    content_object = ParentalKey(
        "conteudo.PublicacaoPage",
        related_name="tagged_items",
        on_delete=models.CASCADE,
    )

class NotaRodapePublicacao(Orderable):
    publicacao = ParentalKey(
        "conteudo.PublicacaoPage",
        related_name="notas_rodape",
        on_delete=models.CASCADE,
    )

    marcador = models.CharField(
        "Marcador",
        max_length=20,
        blank=True,
        help_text="Use no corpo do texto como [[n:marcador]]. Exemplo: se o marcador for 1, use [[n:1]].",
    )
    conteudo = RichTextField("Conteúdo", blank=True)

    panels = [
        HelpPanel(
            content=(
                "Use o marcador para citar a nota no corpo com [[n:marcador]]. "
                "Exemplo: [[n:1]]."
            )
        ),
        FieldPanel("marcador"),
        FieldPanel("conteudo"),
    ]

    class Meta:
        verbose_name = "Nota de rodapé"
        verbose_name_plural = "Notas de rodapé"

    def __str__(self):
        return self.marcador or f"Nota {self.sort_order + 1 if self.sort_order is not None else ''}".strip()

class MidiaIncorporadaPublicacao(Orderable):
    publicacao = ParentalKey(
        "conteudo.PublicacaoPage",
        related_name="midias_embed",
        on_delete=models.CASCADE,
    )

    titulo = models.CharField("Título", max_length=255, blank=True)
    marcador = models.CharField(
        "Marcador",
        max_length=20,
        blank=True,
        help_text="Use no corpo do texto como [[v:marcador]]. Exemplo: se o marcador for video1, use [[v:video1]].",
    )
    url = models.URLField(
        "URL do vídeo",
        help_text="Use uma URL incorporável, como YouTube ou Vimeo.",
    )
    legenda = models.TextField("Legenda", blank=True)
    exibir_no_final = models.BooleanField(
        "Exibir na seção final",
        default=False,
        help_text="Uso legado. Prefira inserir o vídeo no corpo com o marcador; o final da publicação mostra apenas os créditos.",
    )
    credito_texto = models.CharField("Texto do crédito", max_length=255, blank=True)
    credito_url = models.URLField("URL do crédito", blank=True)
    fonte_url = models.URLField("URL da fonte", blank=True)

    panels = [
        HelpPanel(
            content=(
                "Cadastre o video e use [[v:marcador]] no corpo para posicionar."
            )
        ),
        MultiFieldPanel(
            [
                FieldPanel("titulo"),
                FieldPanel("marcador"),
                FieldPanel("url"),
                FieldPanel("legenda"),
            ],
            heading="Insercao no corpo",
        ),
        MultiFieldPanel(
            [
                FieldPanel("credito_texto"),
                FieldPanel("credito_url"),
                FieldPanel("fonte_url"),
                FieldPanel("exibir_no_final"),
            ],
            heading="Creditos",
            help_text=(
                "Nos creditos finais, o sistema prioriza o perfil/canal e exibe a fonte de forma padronizada."
            ),
        ),
    ]

    class Meta:
        verbose_name = "Vídeo externo"
        verbose_name_plural = "Vídeos externos"

    def __str__(self):
        return self.titulo or self.url

class ImagemPublicacao(Orderable):
    publicacao = ParentalKey(
        "conteudo.PublicacaoPage",
        related_name="imagens_publicacao",
        on_delete=models.CASCADE,
    )

    imagem = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Imagem",
        on_delete=models.CASCADE,
        related_name="+",
    )
    titulo = models.CharField("Título", max_length=255, blank=True)
    marcador = models.CharField(
        "Marcador",
        max_length=20,
        blank=True,
        help_text="Use no corpo do texto como [[i:marcador]]. Exemplo: se o marcador for fig1, use [[i:fig1]].",
    )
    legenda = models.TextField("Legenda", blank=True)
    credito_texto = models.CharField("Texto do crédito", max_length=255, blank=True)
    credito_url = models.URLField("URL do crédito", blank=True)
    fonte_url = models.URLField("URL da fonte", blank=True)
    exibir_na_pagina = models.BooleanField(
        "Exibir na seção final",
        default=False,
        help_text="Uso legado. Prefira inserir a imagem no corpo com o marcador; o final da publicação mostra apenas os créditos.",
    )

    panels = [
        HelpPanel(
            content=(
                "Cadastre a imagem e use [[i:marcador]] no corpo para posicionar."
            )
        ),
        MultiFieldPanel(
            [
                FieldPanel("imagem"),
                FieldPanel("titulo"),
                FieldPanel("marcador"),
                FieldPanel("legenda"),
            ],
            heading="Insercao no corpo",
        ),
        MultiFieldPanel(
            [
                FieldPanel("credito_texto"),
                FieldPanel("credito_url"),
                FieldPanel("fonte_url"),
                FieldPanel("exibir_na_pagina"),
            ],
            heading="Creditos",
            help_text=(
                "Nos creditos finais, o perfil e a fonte sao exibidos de forma padronizada."
            ),
        ),
    ]

    class Meta:
        verbose_name = "Imagem da publicação"
        verbose_name_plural = "Imagens da publicação"

    def __str__(self):
        return self.titulo or f"Imagem {self.pk or ''}".strip()

class PublicacaoPageAutor(Orderable):
    publicacao = ParentalKey(
        "conteudo.PublicacaoPage",
        related_name="autores_publicacao",
        on_delete=models.CASCADE,
    )
    autor = models.ForeignKey(
        "conteudo.Autor",
        verbose_name="Autor",
        on_delete=models.CASCADE,
        related_name="+",
    )

    panels = [
        FieldPanel("autor"),
    ]

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Autor da publicação"
        verbose_name_plural = "Autores da publicação"

    def __str__(self):
        return str(self.autor)

class PublicacoesIndexPage(Page):
    introducao = RichTextField("Introdução", blank=True)

    parent_page_types = ["home.HomePage"]
    subpage_types = ["conteudo.PublicacaoPage"]
    max_count = 1

    content_panels = Page.content_panels + [
        FieldPanel("introducao"),
    ]

    def get_context(self, request):
        context = super().get_context(request)
        context["publicacoes"] = (
            PublicacaoPage.objects.live()
            .public()
            .descendant_of(self)
            .order_by("-data_publicacao", "-first_published_at")
        )
        return context

    class Meta:
        verbose_name = "Pasta de publicações"
        verbose_name_plural = "Pastas de publicações"


class PublicacaoPage(Page):
    data_publicacao = models.DateField("Data de publicação", default=timezone.now)
    data_atualizacao = models.DateField("Data de atualização", null=True, blank=True)
    categoria_principal = models.ForeignKey(
        "conteudo.Categoria",
        verbose_name="Categoria principal",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    resumo = RichTextField("Resumo", blank=True)
    imagem_capa = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Imagem de capa",
        help_text="Use imagem horizontal padronizada. Recomendado: 1200 x 675 px ou maior, proporção 16:9.",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    corpo = RichTextField("Corpo", blank=True)
    tags = ClusterTaggableManager(
        through="conteudo.PublicacaoPageTag",
        blank=True,
        help_text="Use apenas etiquetas já cadastradas. Se a etiqueta necessária não aparecer, peça para um administrador cadastrá-la.",
    )

    palavras_chave = models.CharField("Palavras-chave", max_length=500, blank=True)

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("data_publicacao"),
                FieldPanel("data_atualizacao"),
                FieldPanel("categoria_principal"),
                InlinePanel("autores_publicacao", label="Autores"),
                FieldPanel("tags"),
            ],
            heading="1. Metadados editoriais",
        ),
        MultiFieldPanel(
            [
                FieldPanel("resumo"),
                FieldPanel("palavras_chave"),
                FieldPanel("imagem_capa"),
            ],
            heading="2. Resumo e capa",
        ),
        MultiFieldPanel(
            [
                HelpPanel(
                    content=(
                        "Marcadores no corpo: [[i:marcador]] imagem, [[v:marcador]] video, "
                        "[[n:marcador]] nota e [[r:marcador]] referencia."
                    )
                ),
                FieldPanel("corpo"),
            ],
            heading="3. Corpo da publicacao",
        ),
        MultiFieldPanel(
            [
                InlinePanel(
                    "imagens_publicacao",
                    label="Imagens da publicacao",
                    help_text=(
                        "Use padrao 16:9 (recomendado 1200 x 675 px ou maior). "
                        "Insira no corpo com [[i:marcador]]."
                    ),
                ),
                InlinePanel(
                    "midias_embed",
                    label="Videos externos",
                    help_text=(
                        "Use links incorporaveis (YouTube/Vimeo) e insira no corpo com [[v:marcador]]."
                    ),
                ),
                InlinePanel(
                    "notas_rodape",
                    label="Notas de rodape",
                    help_text="Referencie no corpo com [[n:marcador]].",
                ),
                InlinePanel(
                    "referencias",
                    label="Referencias",
                    help_text="Referencie no corpo com [[r:marcador]].",
                ),
            ],
            heading="4. Complementos tecnicos",
        ),
    ]

    parent_page_types = ["conteudo.PublicacoesIndexPage"]
    subpage_types = []
    @property
    def imagens_visiveis(self):
        return self.imagens_publicacao.filter(exibir_na_pagina=True)

    @property
    def autores_ordenados(self):
        return [
            item.autor
            for item in self.autores_publicacao.select_related("autor").order_by("sort_order")
        ]

    @property
    def videos_finais(self):
        return self.midias_embed.filter(exibir_no_final=True)

    @property
    def videos_com_credito(self):
        return [
            item for item in self.midias_embed.all()
            if item.credito_texto or item.fonte_url
        ]

    @property
    def publicacoes_relacionadas(self):
        tags_ids = list(self.tags.values_list("id", flat=True))

        if tags_ids:
            relacionadas_por_tag = (
                PublicacaoPage.objects.live()
                .filter(tags__in=tags_ids)
                .exclude(id=self.id)
                .annotate(
                    tags_em_comum=Count(
                        "tags",
                        filter=Q(tags__in=tags_ids),
                        distinct=True,
                    )
                )
                .order_by("-tags_em_comum", "-data_publicacao", "-first_published_at")
                .distinct()
            )

            if relacionadas_por_tag.exists():
                return relacionadas_por_tag[:4]

        if self.categoria_principal:
            relacionadas_por_categoria = (
                PublicacaoPage.objects.live()
                .filter(categoria_principal=self.categoria_principal)
                .exclude(id=self.id)
                .order_by("-data_publicacao", "-first_published_at")
            )

            if relacionadas_por_categoria.exists():
                return relacionadas_por_categoria[:4]

        return (
            PublicacaoPage.objects.live()
            .exclude(id=self.id)
            .order_by("-data_publicacao", "-first_published_at")[:4]
        )

    class Meta:
        verbose_name = "Publicação"
        verbose_name_plural = "Publicações"

class PaginaInstitucionalPage(Page):
    resumo = RichTextField("Resumo", blank=True)
    corpo = RichTextField("Conteúdo", blank=True)
    imagem_capa = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Imagem de capa",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        FieldPanel("resumo"),
        FieldPanel("imagem_capa"),
        FieldPanel("corpo"),
    ]

    class Meta:
        verbose_name = "Página institucional"
        verbose_name_plural = "Páginas institucionais"

class MensagemContato(models.Model):
    nome = models.CharField("Nome", max_length=255)
    email = models.EmailField("E-mail")
    mensagem = models.TextField("Mensagem")
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    pagina = models.ForeignKey(
        "conteudo.ContatoPage",
        verbose_name="Página de contato",
        on_delete=models.CASCADE,
        related_name="mensagens_recebidas",
    )

    class Meta:
        verbose_name = "Mensagem de contato"
        verbose_name_plural = "Mensagens de contato"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.nome} <{self.email}>"

class InscritoNewsletter(models.Model):
    email = models.EmailField("E-mail", unique=True)
    ativo = models.BooleanField("Ativo", default=False)
    consentimento = models.BooleanField("Consentimento", default=False)
    origem = models.CharField("Origem", max_length=100, blank=True)
    confirmado_em = models.DateTimeField("Confirmado em", null=True, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    panels = [
        FieldPanel("email"),
        FieldPanel("ativo"),
        FieldPanel("consentimento"),
        FieldPanel("origem"),
	FieldPanel("confirmado_em"),
    ]

    class Meta:
        verbose_name = "Inscrito na newsletter"
        verbose_name_plural = "Inscritos na newsletter"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.email

class NewsletterEvento(models.Model):
    TIPO_INSCRICAO_SOLICITADA = "inscricao_solicitada"
    TIPO_INSCRICAO_CONFIRMADA = "inscricao_confirmada"
    TIPO_CANCELAMENTO_SOLICITADO = "cancelamento_solicitado"
    TIPO_CANCELAMENTO_CONFIRMADO = "cancelamento_confirmado"

    TIPO_CHOICES = [
        (TIPO_INSCRICAO_SOLICITADA, "Inscrição solicitada"),
        (TIPO_INSCRICAO_CONFIRMADA, "Inscrição confirmada"),
        (TIPO_CANCELAMENTO_SOLICITADO, "Cancelamento solicitado"),
        (TIPO_CANCELAMENTO_CONFIRMADO, "Cancelamento confirmado"),
    ]

    inscrito = models.ForeignKey(
        "conteudo.InscritoNewsletter",
        verbose_name="Inscrito",
        on_delete=models.CASCADE,
        related_name="eventos",
    )
    email = models.EmailField("E-mail")
    tipo = models.CharField("Tipo", max_length=50, choices=TIPO_CHOICES)
    origem = models.CharField("Origem", max_length=100, blank=True)
    detalhes = models.TextField("Detalhes", blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    panels = [
        FieldPanel("inscrito"),
        FieldPanel("email"),
        FieldPanel("tipo"),
        FieldPanel("origem"),
        FieldPanel("detalhes"),
    ]

    class Meta:
        verbose_name = "Evento da newsletter"
        verbose_name_plural = "Eventos da newsletter"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.email} - {self.get_tipo_display()}"

class SolicitacaoPrivacidadeNewsletter(models.Model):
    TIPO_ACESSO = "acesso"
    TIPO_EXCLUSAO = "exclusao"

    TIPO_CHOICES = [
        (TIPO_ACESSO, "Solicitacao de acesso aos dados"),
        (TIPO_EXCLUSAO, "Solicitacao de exclusao dos dados"),
    ]

    STATUS_PENDENTE = "pendente"
    STATUS_ATENDIDA = "atendida"
    STATUS_NEGADA = "negada"

    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_ATENDIDA, "Atendida"),
        (STATUS_NEGADA, "Negada"),
    ]

    email = models.EmailField("E-mail")
    tipo = models.CharField("Tipo", max_length=20, choices=TIPO_CHOICES)
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDENTE,
    )
    observacoes = models.TextField("Observacoes", blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)
    atendida_em = models.DateTimeField("Atendida em", null=True, blank=True)
    arquivo_exportacao = models.FileField(
        "Arquivo de exportacao",
        upload_to="privacidade_newsletter/",
        blank=True,
        null=True,
    )
    executada_em = models.DateTimeField("Executada em", null=True, blank=True)

    confirmacao_usuario_exclusao = models.BooleanField(
        "Confirmacao do usuario para exclusao",
        default=False,
    )
    confirmacao_usuario_em = models.DateTimeField(
        "Confirmacao do usuario em",
        null=True,
        blank=True,
    )

    panels = [
        FieldPanel("email", read_only=True),
        FieldPanel("tipo", read_only=True),
        FieldPanel("status", read_only=True),
        FieldPanel("observacoes"),
        FieldPanel("atendida_em", read_only=True),
        FieldPanel("executada_em", read_only=True),
        FieldPanel("confirmacao_usuario_exclusao", read_only=True),
        FieldPanel("confirmacao_usuario_em", read_only=True),
    ]

    class Meta:
        verbose_name = "Solicitacao de privacidade da newsletter"
        verbose_name_plural = "Solicitacoes de privacidade da newsletter"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.email} - {self.get_tipo_display()}"

    def nome_arquivo_exportacao(self):
        email_slug = (
            self.email.lower()
            .replace("@", "_at_")
            .replace(".", "_")
            .replace("-", "_")
        )
        return f"privacidade_newsletter_{email_slug}_{self.pk}.csv"

    def gerar_csv_exportacao(self):
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        writer.writerow(["tipo", "campo_1", "campo_2", "campo_3", "campo_4", "campo_5"])

        inscrito = InscritoNewsletter.objects.filter(email__iexact=self.email).first()
        if inscrito:
            writer.writerow([
                "inscrito",
                inscrito.email,
                inscrito.ativo,
                inscrito.consentimento,
                inscrito.origem,
                inscrito.confirmado_em or "",
            ])
        else:
            writer.writerow([
                "inscrito",
                self.email,
                "nao_encontrado",
                "",
                "",
                "",
            ])

        for evento in NewsletterEvento.objects.filter(email__iexact=self.email).order_by("criado_em"):
            writer.writerow([
                "evento",
                evento.email,
                evento.tipo,
                evento.origem,
                evento.criado_em,
                evento.detalhes,
            ])

        for solicitacao in SolicitacaoPrivacidadeNewsletter.objects.filter(email__iexact=self.email).order_by("criado_em"):
            writer.writerow([
                "solicitacao_privacidade",
                solicitacao.email,
                solicitacao.tipo,
                solicitacao.status,
                solicitacao.criado_em,
                solicitacao.observacoes,
            ])

        return buffer.getvalue().encode("utf-8")

    def executar_solicitacao(self):
        if self.executada_em or self.status != self.STATUS_ATENDIDA:
            return

        if self.tipo == self.TIPO_ACESSO:
            conteudo = self.gerar_csv_exportacao()
            nome_arquivo = self.nome_arquivo_exportacao()

            self.arquivo_exportacao.save(
                nome_arquivo,
                ContentFile(conteudo),
                save=False,
            )

            assunto = "Exportacao dos seus dados da newsletter"
            corpo = (
                "O arquivo com os dados solicitados da newsletter segue em anexo.\n\n"
                "Este arquivo podera ser removido do servidor depois de alguns dias.\n"
                "Se voce precisar dele novamente no futuro, sera necessario fazer uma nova solicitacao.\n"
            )

            email_msg = EmailMessage(
                subject=assunto,
                body=corpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[self.email],
            )
            email_msg.attach(nome_arquivo, conteudo, "text/csv")
            email_msg.send(fail_silently=False)

            self.executada_em = timezone.now()

        elif self.tipo == self.TIPO_EXCLUSAO:
            if not self.confirmacao_usuario_exclusao:
                return

            inscrito = InscritoNewsletter.objects.filter(email__iexact=self.email).first()
            if inscrito:
                inscrito.delete()

            self.executada_em = timezone.now()

    def save(self, *args, **kwargs):
        if (
            self.tipo == self.TIPO_EXCLUSAO
            and self.status == self.STATUS_ATENDIDA
            and not self.confirmacao_usuario_exclusao
        ):
            self.status = self.STATUS_PENDENTE
            self.atendida_em = None

        if self.status in [self.STATUS_ATENDIDA, self.STATUS_NEGADA] and not self.atendida_em:
            self.atendida_em = timezone.now()

        if self.status == self.STATUS_PENDENTE:
            self.atendida_em = None

        precisa_executar = (
            self.status == self.STATUS_ATENDIDA
            and self.executada_em is None
            and (
                self.tipo == self.TIPO_ACESSO
                or self.confirmacao_usuario_exclusao
            )
        )

        super().save(*args, **kwargs)

        if precisa_executar:
            self.executar_solicitacao()
            super().save(
                update_fields=[
                    "arquivo_exportacao",
                    "executada_em",
                    "atualizado_em",
                ]
            )

class InscritoNewsletterViewSet(SnippetViewSet):
    model = InscritoNewsletter
    icon = "mail"
    menu_label = "Inscritos na newsletter"
    menu_name = "inscritos-newsletter"
    list_display = [
        "email",
        "ativo",
        "consentimento",
        "confirmado_em",
        "origem",
        "criado_em",
    ]
    search_fields = ["email", "origem"]
    ordering = ["-criado_em"]


register_snippet(InscritoNewsletterViewSet)


class NewsletterEventoViewSet(SnippetViewSet):
    model = NewsletterEvento
    icon = "history"
    menu_label = "Eventos da newsletter"
    menu_name = "eventos-newsletter"
    list_display = [
        "email",
        "tipo",
        "origem",
        "criado_em",
    ]
    search_fields = ["email", "tipo", "origem", "detalhes"]
    ordering = ["-criado_em"]


register_snippet(NewsletterEventoViewSet)


class SolicitacaoPrivacidadeNewsletterViewSet(SnippetViewSet):
    model = SolicitacaoPrivacidadeNewsletter
    icon = "warning"
    menu_label = "Solicitações de privacidade"
    menu_name = "solicitacoes-privacidade-newsletter"

    list_display = [
        "email",
        "tipo",
        "status",
        "confirmacao_usuario_exclusao",
        "confirmacao_usuario_em",
        "criado_em",
        "atendida_em",
        "executada_em",
    ]

    search_fields = ["email", "tipo", "status", "observacoes"]
    ordering = ["-criado_em"]


register_snippet(SolicitacaoPrivacidadeNewsletterViewSet)

class RegistroIndexador(ClusterableModel):
    titulo = models.CharField("Titulo da obra", max_length=500)
    slug = models.SlugField("Slug", max_length=255, unique=True, blank=True)
    ano_publicacao = models.CharField("Ano de publicacao", max_length=20, blank=True)
    dados_editoriais = models.TextField("Dados editoriais", blank=True)
    resumo = models.TextField("Resumo")
    palavras_chave = models.CharField("Palavras-chave", max_length=500, blank=True)
    doi = models.CharField("DOI", max_length=255, blank=True)
    url_acesso = models.URLField("Link de acesso ou download", blank=True)
    ativo = models.BooleanField("Ativo", default=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    panels = [
        FieldPanel("titulo"),
        FieldPanel("slug"),
        FieldPanel("ano_publicacao"),
        FieldPanel("dados_editoriais"),
        FieldPanel("resumo"),
        FieldPanel("palavras_chave"),
        FieldPanel("doi"),
        FieldPanel("url_acesso"),
        FieldPanel("ativo"),
        InlinePanel("autores_registro", label="Autores", min_num=1),
    ]

    class Meta:
        verbose_name = "Registro do indexador"
        verbose_name_plural = "Registros do indexador"
        ordering = ["titulo"]

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.titulo)[:230] or "registro"
            slug = base_slug
            contador = 2

            while RegistroIndexador.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                sufixo = f"-{contador}"
                slug = f"{base_slug[:255 - len(sufixo)]}{sufixo}"
                contador += 1

            self.slug = slug

        super().save(*args, **kwargs)

    @property
    def autores_formatados(self):
        return "; ".join(
            [autor.nome for autor in self.autores_registro.all() if autor.nome.strip()]
        )

    @property
    def orcids_formatados(self):
        return "; ".join(
            [autor.orcid for autor in self.autores_registro.all() if autor.orcid.strip()]
        )

class RegistroIndexadorAutor(Orderable):
    registro = ParentalKey(
        "conteudo.RegistroIndexador",
        related_name="autores_registro",
        on_delete=models.CASCADE,
    )
    nome = models.CharField("Nome do autor", max_length=1000)
    orcid = models.CharField("ORCID", max_length=19, blank=True)

    panels = [
        FieldPanel("nome"),
        FieldPanel("orcid"),
    ]

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Autor do registro"
        verbose_name_plural = "Autores do registro"

    def __str__(self):
        return self.nome

class RegistroIndexadorViewSet(SnippetViewSet):
    model = RegistroIndexador
    icon = "doc-full"
    menu_label = "Registros do indexador"
    menu_name = "registros-indexador"
    list_display = [
        "titulo",
        "ano_publicacao",
        "ativo",
        "atualizado_em",
    ]
    search_fields = ["titulo", "resumo", "dados_editoriais", "palavras_chave", "doi"]
    ordering = ["titulo"]


register_snippet(RegistroIndexadorViewSet)

class ContatoPage(Page):
    introducao = RichTextField("Introdução", blank=True)
    email_destino = models.EmailField("E-mail de destino", blank=True)
    mensagem_sucesso = models.CharField(
        "Mensagem de sucesso",
        max_length=255,
        default="Mensagem enviada com sucesso.",
    )

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        FieldPanel("introducao"),
        FieldPanel("email_destino"),
        FieldPanel("mensagem_sucesso"),
    ]

    class Meta:
        verbose_name = "Página de contato"
        verbose_name_plural = "Páginas de contato"

class IndexadorPage(Page):
    introducao = RichTextField("Introducao", blank=True)
    mensagem_sem_resultados = models.CharField(
        "Mensagem sem resultados",
        max_length=255,
        default="Nenhum registro encontrado.",
    )
    itens_por_pagina = models.PositiveIntegerField("Itens por pagina", default=10)

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        FieldPanel("introducao"),
        FieldPanel("mensagem_sem_resultados"),
        FieldPanel("itens_por_pagina"),
    ]

    class Meta:
        verbose_name = "Pagina do indexador"
        verbose_name_plural = "Paginas do indexador"

    def get_context(self, request):
        context = super().get_context(request)

        termo = request.GET.get("q", "").strip()
        ano_inicial = request.GET.get("ano_inicial", "").strip()
        ano_final = request.GET.get("ano_final", "").strip()
        ordenar = request.GET.get("ordenar", "recentes").strip()

        registros = RegistroIndexador.objects.filter(ativo=True).prefetch_related("autores_registro")

        if termo:
            registros = registros.filter(
                Q(titulo__icontains=termo)
                | Q(resumo__icontains=termo)
                | Q(dados_editoriais__icontains=termo)
                | Q(palavras_chave__icontains=termo)
                | Q(doi__icontains=termo)
                | Q(autores_registro__nome__icontains=termo)
                | Q(autores_registro__orcid__icontains=termo)
            ).distinct()

        if ano_inicial:
            registros = registros.filter(ano_publicacao__gte=ano_inicial)

        if ano_final:
            registros = registros.filter(ano_publicacao__lte=ano_final)

        if ordenar == "titulo_az":
            registros = registros.order_by("titulo")
        elif ordenar == "titulo_za":
            registros = registros.order_by("-titulo")
        elif ordenar == "antigos":
            registros = registros.order_by("ano_publicacao", "titulo")
        else:
            registros = registros.order_by("-ano_publicacao", "titulo")

        paginator = Paginator(registros, self.itens_por_pagina or 10)
        pagina_numero = request.GET.get("pagina")
        pagina_obj = paginator.get_page(pagina_numero)

        context["termo_busca"] = termo
        context["ano_inicial"] = ano_inicial
        context["ano_final"] = ano_final
        context["ordenacao_atual"] = ordenar
        context["pagina_obj"] = pagina_obj
        context["registros"] = pagina_obj.object_list

        return context

class NewsletterPage(Page):
    introducao = RichTextField("Introdução", blank=True)
    mensagem_sucesso = models.CharField(
        "Mensagem de sucesso",
        max_length=255,
        default="Inscricao realizada com sucesso.",
    )

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        FieldPanel("introducao"),
        FieldPanel("mensagem_sucesso"),
    ]

    class Meta:
        verbose_name = "Página de newsletter"
        verbose_name_plural = "Páginas de newsletter"
