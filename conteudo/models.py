import csv
import hashlib
import io
import json
import logging
import os
import random
import re
import urllib.parse
import unicodedata
import uuid
from datetime import timedelta


from django import forms
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.core import signing
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils.text import slugify
from modelcluster.models import ClusterableModel
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models import Count, F, Q, Sum
from django.utils.html import format_html
from django.utils.html import strip_tags
from django.utils import timezone
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from modelcluster.contrib.taggit import ClusterTaggableManager
from taggit.models import ItemBase, TagBase
from wagtail.admin.panels import FieldPanel, HelpPanel, InlinePanel, MultiFieldPanel
from wagtail.admin.forms.choosers import BaseFilterForm
from wagtail.fields import RichTextField
from wagtail.models import Page, Orderable, Site
from wagtail.permission_policies.base import ModelPermissionPolicy
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.chooser import ChooseResultsView, ChooseView, SnippetChooserViewSet
from wagtail.snippets.views.snippets import SnippetViewSet
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from .analytics import requisicao_ignorada_para_estatisticas
from .color_palette import derive_palette, suggest_secondary
from .current_user import get_current_user
from .storage import PrivatePendingMediaStorage, PrivateSubmissionStorage

logger = logging.getLogger(__name__)
midia_pendente_storage = PrivatePendingMediaStorage()
submissao_publica_storage = PrivateSubmissionStorage()

PROMOTE_PANELS_SEM_MENU_SITE = [
    MultiFieldPanel(
        ["slug", "seo_title", "search_description"],
        heading="Para motores de busca",
        classname="collapsed",
    )
]


def _usuario_pode_aprovar_editorial(user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    from .access import is_admin, is_reviewer

    return is_admin(user) or is_reviewer(user)


class AprovacaoEditorialMixin(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_APROVADO = "aprovado"
    STATUS_REJEITADO = "rejeitado"
    APROVACAO_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_APROVADO, "Aprovado"),
        (STATUS_REJEITADO, "Rejeitado"),
    ]

    aprovacao_status = models.CharField(
        "Status editorial",
        max_length=20,
        choices=APROVACAO_CHOICES,
        default=STATUS_PENDENTE,
        db_index=True,
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Criado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Aprovado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    aprovado_em = models.DateTimeField("Aprovado em", null=True, blank=True)

    class Meta:
        abstract = True

    def aplicar_fluxo_editorial(self):
        current_user = get_current_user()
        if current_user and getattr(current_user, "is_authenticated", False) and not self.criado_por_id:
            self.criado_por = current_user

        if current_user and not _usuario_pode_aprovar_editorial(current_user):
            self.aprovacao_status = self.STATUS_PENDENTE
            self.aprovado_por = None
            self.aprovado_em = None
            return

        if self.aprovacao_status == self.STATUS_APROVADO:
            if current_user and getattr(current_user, "is_authenticated", False):
                self.aprovado_por = current_user
            if not self.aprovado_em:
                self.aprovado_em = timezone.now()
        else:
            self.aprovado_por = None
            self.aprovado_em = None

    @property
    def aprovacao_badge(self):
        return self.get_aprovacao_status_display()


class TraducaoConteudoMixin(models.Model):
    traducoes = models.JSONField(default=dict, blank=True, editable=False)

    translation_source_language = "pt-br"
    translatable_fields = ()
    richtext_translation_fields = ()
    sync_translation_skip_fields = ()
    sync_translation_max_chars_plain = 800
    sync_translation_max_chars_html = 2200

    class Meta:
        abstract = True

    def _translation_field_value(self, field_name):
        valor = getattr(self, field_name, "")
        if hasattr(valor, "source"):
            return valor.source
        return valor

    def translation_source_changed(self):
        return False

    def get_translation_source_original(self):
        if not self.pk:
            return None
        return (
            type(self)
            .objects.filter(pk=self.pk)
            .only(*self.translatable_fields, "traducoes")
            .first()
        )

    def get_changed_translation_fields(self, original=None):
        return []

    def should_sync_translation_field(self, field_name):
        if field_name in self.sync_translation_skip_fields:
            return False
        valor = self._translation_field_value(field_name)
        bruto = "" if valor is None else str(valor)
        texto = strip_tags(bruto) if field_name in self.richtext_translation_fields else bruto
        tamanho = len((texto or "").strip())
        limite = (
            self.sync_translation_max_chars_html
            if field_name in self.richtext_translation_fields
            else self.sync_translation_max_chars_plain
        )
        return tamanho <= limite

    def get_translated_value(self, field_name, lang="pt-br"):
        return getattr(self, field_name, "")

    def build_translation_payload(self):
        return {
            field_name: getattr(self, field_name, "")
            for field_name in self.translatable_fields
        }

    def sync_translations(self):
        return

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


def normalizar_codigo_idioma_manual(valor):
    idioma = (valor or "").strip().lower().replace("_", "-")
    if not idioma:
        return "pt-br"
    if idioma in {"pt", "pt-br", "pt-brasil"}:
        return "pt-br"
    return idioma


def rotulo_idioma_manual_padrao(codigo):
    idioma = normalizar_codigo_idioma_manual(codigo)
    rotulos = {
        "pt-br": "Português",
        "en": "English",
        "es": "Español",
        "fr": "Français",
        "it": "Italiano",
        "de": "Deutsch",
    }
    return rotulos.get(idioma, idioma.upper())


def normalizar_rotulo_taxonomia(valor):
    texto = " ".join(str(valor or "").strip().split()).lower()
    if not texto:
        return ""
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(char for char in texto if unicodedata.category(char) != "Mn")
    return texto


def normalizar_username_publico(valor):
    return slugify(" ".join(str(valor or "").strip().split()))[:80]


def normalizar_marcador_publicacao(valor):
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", str(valor or "").strip()).strip("-")


def dividir_marcadores_publicacao(*valores):
    marcadores = []
    vistos = set()
    for valor in valores:
        for parte in re.split(r"[,;\n]+", str(valor or "")):
            marcador = parte.strip()
            chave = normalizar_marcador_publicacao(marcador).lower()
            if not marcador or not chave or chave in vistos:
                continue
            vistos.add(chave)
            marcadores.append(marcador)
    return marcadores


def chave_ordenacao_marcador_publicacao(valor):
    partes = re.split(r"(\d+)", str(valor or "").strip().lower())
    return [(0, int(parte)) if parte.isdigit() else (1, parte) for parte in partes if parte != ""]


def posicoes_marcadores_publicacao(html, prefixo):
    posicoes = {}
    padrao = re.compile(rf"\[\[\s*{re.escape(prefixo)}:\s*([^\]]+?)\s*\]\]", re.IGNORECASE)
    for match in padrao.finditer(str(html or "")):
        chave = normalizar_marcador_publicacao(match.group(1)).lower()
        if chave and chave not in posicoes:
            posicoes[chave] = match.start()
    return posicoes


def primeiro_marcador_em_uso(marcadores, posicoes):
    encontrados = [
        (posicoes[normalizar_marcador_publicacao(marcador).lower()], marcador)
        for marcador in marcadores
        if normalizar_marcador_publicacao(marcador).lower() in posicoes
    ]
    if not encontrados:
        return marcadores[0] if marcadores else ""
    return min(encontrados, key=lambda item: item[0])[1]

@register_setting
class ConfiguracaoSite(BaseSiteSetting):
    RUNTIME_ENV_OVERRIDES = {
        "shlink_base_url": "OWNPAPER_SHLINK_BASE_URL",
        "shlink_api_key": "OWNPAPER_SHLINK_API_KEY",
        "oauth_orcid_client_id": "OWNPAPER_OAUTH_ORCID_CLIENT_ID",
        "oauth_orcid_client_secret": "OWNPAPER_OAUTH_ORCID_CLIENT_SECRET",
        "oauth_github_client_id": "OWNPAPER_OAUTH_GITHUB_CLIENT_ID",
        "oauth_github_client_secret": "OWNPAPER_OAUTH_GITHUB_CLIENT_SECRET",
        "oauth_google_client_id": "OWNPAPER_OAUTH_GOOGLE_CLIENT_ID",
        "oauth_google_client_secret": "OWNPAPER_OAUTH_GOOGLE_CLIENT_SECRET",
        "oauth_codeberg_client_id": "OWNPAPER_OAUTH_CODEBERG_CLIENT_ID",
        "oauth_codeberg_client_secret": "OWNPAPER_OAUTH_CODEBERG_CLIENT_SECRET",
        "oauth_codeberg_base_url": "OWNPAPER_OAUTH_CODEBERG_BASE_URL",
        "oauth_gitlab_client_id": "OWNPAPER_OAUTH_GITLAB_CLIENT_ID",
        "oauth_gitlab_client_secret": "OWNPAPER_OAUTH_GITLAB_CLIENT_SECRET",
        "oauth_gitlab_base_url": "OWNPAPER_OAUTH_GITLAB_BASE_URL",
    }
    SECRET_RUNTIME_FIELDS = (
        "shlink_api_key",
        "oauth_orcid_client_secret",
        "oauth_github_client_secret",
        "oauth_google_client_secret",
        "oauth_codeberg_client_secret",
        "oauth_gitlab_client_secret",
    )
    NOTIFICACAO_PUBLICACOES_DESATIVADA = "desativada"
    NOTIFICACAO_PUBLICACOES_IMEDIATA = "imediata"
    NOTIFICACAO_PUBLICACOES_PERIODICA = "periodica"
    NOTIFICACAO_PUBLICACOES_CHOICES = [
        (NOTIFICACAO_PUBLICACOES_DESATIVADA, "Desativada"),
        (NOTIFICACAO_PUBLICACOES_IMEDIATA, "Imediata (nova publicação)"),
        (NOTIFICACAO_PUBLICACOES_PERIODICA, "Consolidada por período"),
    ]
    TEMA_PADRAO_CLARO = "claro"
    TEMA_PADRAO_ESCURO = "escuro"
    TEMA_PADRAO_CHOICES = [
        (TEMA_PADRAO_CLARO, "Claro"),
        (TEMA_PADRAO_ESCURO, "Escuro"),
    ]
    IDIOMA_SITE_PT_BR = "pt-br"
    IDIOMA_SITE_EN = "en"
    IDIOMA_SITE_ES = "es"
    IDIOMA_SITE_CHOICES = [
        (IDIOMA_SITE_PT_BR, "Português (Brasil)"),
        (IDIOMA_SITE_EN, "English"),
        (IDIOMA_SITE_ES, "Español"),
    ]
    MENU_HOME_LOGO_RATIO_AUTO = "auto"
    MENU_HOME_LOGO_RATIO_1_1 = "1:1"
    MENU_HOME_LOGO_RATIO_3_2 = "3:2"
    MENU_HOME_LOGO_RATIO_4_3 = "4:3"
    MENU_HOME_LOGO_RATIO_16_9 = "16:9"
    MENU_HOME_LOGO_RATIO_21_9 = "21:9"
    MENU_HOME_LOGO_RATIO_12_5 = "12:5"
    MENU_HOME_LOGO_RATIO_5_1 = "5:1"
    MENU_HOME_LOGO_RATIO_CHOICES = [
        (MENU_HOME_LOGO_RATIO_AUTO, "Manter proporção original da imagem"),
        (MENU_HOME_LOGO_RATIO_1_1, "1:1"),
        (MENU_HOME_LOGO_RATIO_3_2, "3:2"),
        (MENU_HOME_LOGO_RATIO_4_3, "4:3"),
        (MENU_HOME_LOGO_RATIO_5_1, "5:1"),
        (MENU_HOME_LOGO_RATIO_16_9, "16:9"),
        (MENU_HOME_LOGO_RATIO_21_9, "21:9"),
        (MENU_HOME_LOGO_RATIO_12_5, "12:5"),
    ]
    MENU_HOME_LOGO_AJUSTE_CONTER = "conter"
    MENU_HOME_LOGO_AJUSTE_PREENCHER = "preencher"
    MENU_HOME_LOGO_AJUSTE_CHOICES = [
        (MENU_HOME_LOGO_AJUSTE_CONTER, "Manter proporção da imagem"),
        (MENU_HOME_LOGO_AJUSTE_PREENCHER, "Redimensionar para preencher a proporção"),
    ]
    MENU_HOME_LOGO_RATIO_MAP = {
        MENU_HOME_LOGO_RATIO_1_1: (1, 1),
        MENU_HOME_LOGO_RATIO_3_2: (3, 2),
        MENU_HOME_LOGO_RATIO_4_3: (4, 3),
        MENU_HOME_LOGO_RATIO_16_9: (16, 9),
        MENU_HOME_LOGO_RATIO_21_9: (21, 9),
        MENU_HOME_LOGO_RATIO_12_5: (12, 5),
        MENU_HOME_LOGO_RATIO_5_1: (5, 1),
    }

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
    texto_rodape_link = models.CharField(
        "Link do texto do rodapé",
        max_length=255,
        blank=True,
        help_text="Opcional. Use '#' para subir ao topo da página ou uma URL completa.",
    )
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
        verbose_name="Página do Indexador",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    rotulo_indexador = models.CharField(
        "Rótulo do link do indexador",
        max_length=255,
        default="Indexador",
        blank=True,
    )
    pagina_quiz_estudo = models.ForeignKey(
        "wagtailcore.Page",
        verbose_name="Página de quiz de estudos",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    rotulo_quiz_estudo = models.CharField(
        "Rótulo do link de quiz",
        max_length=255,
        default="Quiz",
        blank=True,
    )

    modo_manutencao_ativo = models.BooleanField(
        "Modo manutenção ativo",
        default=False,
    )
    modo_manutencao_titulo = models.CharField(
        "Título da manutenção",
        max_length=255,
        default="Site em manutenção",
    )
    modo_manutencao_mensagem = models.TextField(
        "Mensagem da manutenção",
        default="Estamos realizando uma manutenção no momento. Tente novamente em alguns minutos.",
        blank=True,
    )
    travar_publicacao_por_orcid = models.BooleanField(
        "Travar autoria por ORCID nas publicações",
        default=True,
        help_text=(
            "Quando ativo, impede alteração dos autores em publicações já vinculadas "
            "a ORCID e exige ORCID dos autores para publicar."
        ),
    )
    notificacao_publicacoes_modo = models.CharField(
        "Modo de notificação de publicações",
        max_length=20,
        choices=NOTIFICACAO_PUBLICACOES_CHOICES,
        default=NOTIFICACAO_PUBLICACOES_DESATIVADA,
    )
    notificacao_publicacoes_periodo_horas = models.PositiveIntegerField(
        "Período (horas) para envio consolidado",
        default=168,
        help_text="Usado quando o modo estiver em consolidado por período. Ex.: 24 (diário), 168 (semanal).",
    )
    notificacao_publicacoes_ultimo_envio_em = models.DateTimeField(
        "Último envio de publicações",
        null=True,
        blank=True,
    )
    backup_email_destino = models.EmailField(
        "E-mail para relatório de backup",
        blank=True,
    )
    backup_enviar_relatorio = models.BooleanField(
        "Enviar relatório por e-mail",
        default=False,
    )
    backup_ultimo_envio_em = models.DateTimeField(
        "Última execução de backup",
        null=True,
        blank=True,
    )
    comentarios_ativos = models.BooleanField(
        "Ativar comentários públicos",
        default=False,
    )
    comentarios_auto_newsletter = models.BooleanField(
        "Cadastrar comentaristas na newsletter automaticamente",
        default=True,
        help_text=(
            "Quando ativo, usuários que confirmarem comentário serão inscritos na newsletter "
            "e poderão cancelar depois pela página de newsletter."
        ),
    )
    submissoes_publicas_ativas = models.BooleanField(
        "Ativar submissões públicas",
        default=False,
        help_text="Permite que usuários cadastrados no site público enviem textos para triagem editorial.",
    )
    submissoes_exigir_orcid = models.BooleanField(
        "Exigir ORCID nas submissões públicas",
        default=False,
        help_text="Quando ativo, o cadastro público precisa ter ORCID válido para enviar submissões.",
    )
    submissoes_limite_pdf_mb = models.PositiveSmallIntegerField(
        "Limite do PDF de submissão (MB)",
        default=25,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    doacoes_ativas = models.BooleanField(
        "Ativar apoios/doações no site",
        default=False,
    )
    doacoes_exibir_no_rodape = models.BooleanField(
        "Exibir link de apoio no rodapé",
        default=True,
    )
    doacoes_exibir_no_cabecalho = models.BooleanField(
        "Exibir link de apoio no cabeçalho",
        default=True,
    )
    doacoes_exibir_em_publicacoes = models.BooleanField(
        "Exibir bloco de apoio no fim das publicações",
        default=False,
    )
    doacoes_rotulo = models.CharField(
        "Rótulo do botão/link de apoio",
        max_length=120,
        default="Apoie",
        blank=True,
    )
    doacoes_titulo = models.CharField(
        "Título da página de apoio",
        max_length=255,
        default="Apoie o projeto",
    )
    doacoes_descricao = RichTextField(
        "Descrição da página de apoio",
        blank=True,
        default=(
            "<p>Se este projeto é útil para você, considere contribuir para manter "
            "a publicação independente, a infraestrutura técnica e o desenvolvimento "
            "de novos recursos. Todo apoio ajuda a sustentar o trabalho editorial e "
            "a continuidade do site.</p>"
        ),
        features=["bold", "italic", "link", "ol", "ul"],
    )
    doacoes_pix_chave = models.CharField(
        "Chave Pix",
        max_length=255,
        blank=True,
    )
    doacoes_pix_ativo = models.BooleanField(
        "Ativar Pix",
        default=False,
    )
    doacoes_pix_qr_code = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="QR Code Pix",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    doacoes_pix_copia_cola = models.TextField(
        "Pix copia e cola",
        blank=True,
        help_text="Payload EMV do QR Code Pix, quando houver.",
    )
    doacoes_apoiase_ativo = models.BooleanField(
        "Ativar Apoia.se",
        default=False,
    )
    doacoes_apoiase_url = models.URLField(
        "URL do Apoia.se",
        blank=True,
    )
    doacoes_buymeacoffee_ativo = models.BooleanField(
        "Ativar Buy Me a Coffee",
        default=False,
    )
    doacoes_buymeacoffee_usuario = models.CharField(
        "Usuário Buy Me a Coffee",
        max_length=120,
        blank=True,
        help_text="Informe apenas o usuário/slug, sem URL.",
    )
    doacoes_paypal_ativo = models.BooleanField(
        "Ativar PayPal",
        default=False,
    )
    doacoes_paypal_hosted_button_id = models.CharField(
        "PayPal hosted_button_id",
        max_length=120,
        blank=True,
        help_text="ID público do botão de doação criado no PayPal.",
    )
    doacoes_paypal_business = models.CharField(
        "PayPal business",
        max_length=255,
        blank=True,
        help_text="E-mail ou payer ID, usado apenas se não houver hosted_button_id.",
    )
    doacoes_paypal_url = models.URLField(
        "URL PayPal alternativa",
        blank=True,
    )
    doacoes_mercadopago_ativo = models.BooleanField(
        "Ativar Mercado Pago",
        default=False,
    )
    doacoes_mercadopago_url = models.URLField(
        "URL do Mercado Pago",
        blank=True,
        help_text="Link público de pagamento, checkout ou preferência já criada no Mercado Pago.",
    )
    doacoes_github_sponsors_ativo = models.BooleanField(
        "Ativar GitHub Sponsors",
        default=False,
    )
    doacoes_github_sponsors_usuario = models.CharField(
        "Usuário/organização GitHub Sponsors",
        max_length=120,
        blank=True,
        help_text="Informe apenas o usuário ou organização, sem URL.",
    )
    doacoes_bitcoin_ativo = models.BooleanField(
        "Ativar Bitcoin",
        default=False,
    )
    doacoes_bitcoin_endereco = models.CharField(
        "Endereço Bitcoin",
        max_length=255,
        blank=True,
    )
    doacoes_ethereum_ativo = models.BooleanField(
        "Ativar Ethereum",
        default=False,
    )
    doacoes_ethereum_endereco = models.CharField(
        "Endereço Ethereum",
        max_length=255,
        blank=True,
    )
    doacoes_link_externo = models.URLField(
        "Link externo complementar",
        blank=True,
    )
    doacoes_detalhes = RichTextField(
        "Outros meios de apoio/doação",
        blank=True,
        features=["bold", "italic", "link", "ol", "ul"],
    )

    @property
    def doacoes_buymeacoffee_url(self):
        usuario = (self.doacoes_buymeacoffee_usuario or "").strip().strip("/")
        if not usuario:
            return ""
        return f"https://www.buymeacoffee.com/{urllib.parse.quote(usuario)}"

    @property
    def doacoes_paypal_link(self):
        if self.doacoes_paypal_url:
            return self.doacoes_paypal_url
        hosted_button_id = (self.doacoes_paypal_hosted_button_id or "").strip()
        if hosted_button_id:
            return f"https://www.paypal.com/donate?hosted_button_id={urllib.parse.quote(hosted_button_id)}"
        business = (self.doacoes_paypal_business or "").strip()
        if business:
            return f"https://www.paypal.com/donate/?business={urllib.parse.quote(business)}"
        return ""

    @property
    def doacoes_github_sponsors_url(self):
        usuario = (self.doacoes_github_sponsors_usuario or "").strip().strip("/")
        if not usuario:
            return ""
        return f"https://github.com/sponsors/{urllib.parse.quote(usuario)}"

    @property
    def doacoes_bitcoin_uri(self):
        endereco = (self.doacoes_bitcoin_endereco or "").strip()
        if not endereco:
            return ""
        return f"bitcoin:{endereco}"

    @property
    def doacoes_ethereum_uri(self):
        endereco = (self.doacoes_ethereum_endereco or "").strip()
        if not endereco:
            return ""
        return f"ethereum:{endereco}"

    google_search_console_verification = models.CharField(
        "Verificação do Google Search Console",
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
    verificacao_head_html = models.TextField(
        "HTML avançado de verificação no head",
        blank=True,
        help_text=(
            "Use apenas códigos de verificação fornecidos por serviços confiáveis. "
            "Este conteúdo é inserido no head do site público sem depender de cookies."
        ),
    )
    verificacao_arquivo_nome = models.CharField(
        "Nome do arquivo de verificação",
        max_length=120,
        blank=True,
        help_text="Exemplo: google1234567890abcdef.html ou verificacao.txt.",
    )
    verificacao_arquivo_conteudo = models.TextField(
        "Conteúdo do arquivo de verificação",
        blank=True,
        help_text="Cole aqui o conteúdo integral do arquivo solicitado pelo provedor.",
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
    plausible_domain = models.CharField(
        "Plausible - domínio do site",
        max_length=255,
        blank=True,
        help_text="Exemplo: exemplo.com. Deixe vazio para desativar.",
    )
    plausible_script_url = models.URLField(
        "Plausible - URL do script",
        default="https://plausible.io/js/script.js",
        blank=True,
        help_text="Use a URL oficial ou da sua instância Plausible self-hosted.",
    )
    plausible_script_direto_ativo = models.BooleanField(
        "Usar snippet novo do Plausible sem domínio",
        default=False,
        help_text=(
            "Ative quando o Plausible fornecer apenas um script próprio, sem data-domain. "
            "O OwnPaper renderiza apenas o snippet seguro predefinido."
        ),
    )
    plausible_sem_consentimento_ativo = models.BooleanField(
        "Carregar Plausible sem aceite de cookies opcionais",
        default=False,
        help_text=(
            "Use somente quando a configuração do Plausible estiver sem cookies e adequada "
            "à política de privacidade do projeto."
        ),
    )
    umami_website_id = models.CharField(
        "Umami - Website ID",
        max_length=120,
        blank=True,
        help_text="ID do site no Umami. Deixe vazio para desativar.",
    )
    umami_script_url = models.URLField(
        "Umami - URL do script",
        blank=True,
        help_text="Exemplo: https://analytics.example.com/script.js.",
    )
    matomo_site_id = models.CharField(
        "Matomo - Site ID",
        max_length=40,
        blank=True,
        help_text="ID numérico do site no Matomo. Deixe vazio para desativar.",
    )
    matomo_url = models.URLField(
        "Matomo - URL base",
        blank=True,
        help_text="Exemplo: https://matomo.example.com/.",
    )
    estatisticas_internas_ativas = models.BooleanField(
        "Ativar estatísticas internas",
        default=True,
        help_text=(
            "Quando ativo, o OwnPaper registra estatísticas internas somente após "
            "consentimento de cookies opcionais."
        ),
    )
    estatisticas_reter_agregados_dias = models.PositiveIntegerField(
        "Retenção dos agregados diários (dias)",
        default=365,
        help_text="Padrão recomendado: 365 dias.",
    )
    estatisticas_reter_eventos_brutos_dias = models.PositiveIntegerField(
        "Retenção dos eventos brutos (dias)",
        default=90,
        help_text="Padrão recomendado: 90 dias.",
    )
    usar_menu_customizado = models.BooleanField(
        "Usar menu customizado",
        default=False,
        help_text="Quando ativo, o menu principal passa a usar os grupos e subitens configurados abaixo.",
    )
    menu_home_exibir = models.BooleanField(
        "Exibir item Início no menu",
        default=True,
    )
    menu_home_primeiro_fixo = models.BooleanField(
        "Fixar Início sempre no primeiro item",
        default=True,
        help_text="Desative para ordenar o Início manualmente via Menu principal.",
    )
    menu_home_rotulo = models.CharField(
        "Rótulo do Início no menu",
        max_length=120,
        default="Início",
        blank=True,
    )
    menu_home_imagem = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Imagem/logo do Início no menu",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    menu_home_imagem_claro = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Imagem/logo do Início (tema claro)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    menu_home_imagem_escuro = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Imagem/logo do Início (tema escuro)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    menu_home_imagem_mobile_claro = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Imagem/logo do Início no mobile (tema claro)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    menu_home_imagem_mobile_escuro = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Imagem/logo do Início no mobile (tema escuro)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    menu_home_logo_proporcao = models.CharField(
        "Proporção do botão/logo do Início",
        max_length=20,
        choices=MENU_HOME_LOGO_RATIO_CHOICES,
        default=MENU_HOME_LOGO_RATIO_AUTO,
        help_text="Defina uma proporção fixa ou mantenha a original do arquivo enviado.",
    )
    menu_home_logo_ajuste = models.CharField(
        "Modo de ajuste da imagem",
        max_length=20,
        choices=MENU_HOME_LOGO_AJUSTE_CHOICES,
        default=MENU_HOME_LOGO_AJUSTE_CONTER,
        help_text="Em 'preencher', a imagem ocupa toda a área definida pela proporção escolhida.",
    )
    menu_home_logo_altura_desktop_px = models.PositiveSmallIntegerField(
        "Altura do botão/logo do Início no desktop (px)",
        default=72,
        validators=[MinValueValidator(24), MaxValueValidator(80)],
        help_text="Altura máxima em pixels para desktop. Intervalo: 24 a 80.",
    )
    menu_home_logo_altura_mobile_px = models.PositiveSmallIntegerField(
        "Altura do botão/logo do Início no mobile (px)",
        default=50,
        validators=[MinValueValidator(24), MaxValueValidator(80)],
        help_text="Altura máxima em pixels para mobile. Intervalo: 24 a 80.",
    )
    menu_padrao_categorias_ativo = models.BooleanField("Exibir Categorias no menu padrão", default=True)
    menu_padrao_categorias_rotulo = models.CharField("Rótulo de Categorias", max_length=120, default="Categorias", blank=True)
    menu_padrao_autores_ativo = models.BooleanField("Exibir Autores no menu padrão", default=True)
    menu_padrao_autores_rotulo = models.CharField("Rótulo de Autores", max_length=120, default="Autores", blank=True)
    menu_padrao_tags_ativo = models.BooleanField("Exibir Tags no menu padrão", default=True)
    menu_padrao_tags_rotulo = models.CharField("Rótulo de Tags", max_length=120, default="Tags", blank=True)
    menu_padrao_busca_ativo = models.BooleanField("Exibir Busca no menu padrão", default=True)
    menu_padrao_busca_rotulo = models.CharField("Rótulo de Busca", max_length=120, default="Busca", blank=True)
    menu_padrao_destaques_ativo = models.BooleanField("Exibir Destaques no menu padrão", default=True)
    menu_padrao_destaques_rotulo = models.CharField("Rótulo de Destaques", max_length=120, default="Destaques", blank=True)
    menu_padrao_ultimas_ativo = models.BooleanField("Exibir Últimas publicações no menu padrão", default=True)
    menu_padrao_ultimas_rotulo = models.CharField("Rótulo de Últimas publicações", max_length=120, default="Últimas publicações", blank=True)
    menu_padrao_contato_ativo = models.BooleanField("Exibir Contato no menu padrão", default=True)
    menu_padrao_contato_rotulo = models.CharField("Rótulo de Contato", max_length=120, default="Contato", blank=True)
    menu_padrao_sobre_ativo = models.BooleanField("Exibir Sobre no menu padrão", default=True)
    menu_padrao_sobre_rotulo = models.CharField("Rótulo de Sobre", max_length=120, default="Sobre", blank=True)
    menu_padrao_newsletter_ativo = models.BooleanField("Exibir Newsletter no menu padrão", default=True)
    menu_padrao_newsletter_rotulo = models.CharField("Rótulo de Newsletter", max_length=120, default="Newsletter", blank=True)
    menu_padrao_indexador_ativo = models.BooleanField("Exibir Indexador no menu padrão", default=True)
    menu_padrao_indexador_rotulo = models.CharField("Rótulo de Indexador", max_length=120, default="Indexador", blank=True)
    menu_padrao_quiz_ativo = models.BooleanField("Exibir Quiz no menu padrão", default=True)
    menu_padrao_quiz_rotulo = models.CharField("Rótulo de Quiz", max_length=120, default="Quiz", blank=True)
    menu_padrao_apoio_ativo = models.BooleanField("Exibir Apoie no menu padrão", default=True)
    menu_padrao_apoio_rotulo = models.CharField("Rótulo de Apoie", max_length=120, default="Apoie", blank=True)
    menu_padrao_privacidade_ativo = models.BooleanField("Exibir Privacidade no menu padrão", default=False)
    menu_padrao_privacidade_rotulo = models.CharField("Rótulo de Privacidade", max_length=120, default="Privacidade", blank=True)
    menu_padrao_cookies_ativo = models.BooleanField("Exibir Cookies no menu padrão", default=False)
    menu_padrao_cookies_rotulo = models.CharField("Rótulo de Cookies", max_length=120, default="Cookies", blank=True)
    menu_padrao_rss_ativo = models.BooleanField("Exibir RSS no menu padrão", default=False)
    menu_padrao_rss_rotulo = models.CharField("Rótulo de RSS", max_length=120, default="RSS", blank=True)
    rodape_padrao_contato_ativo = models.BooleanField("Exibir Contato no rodapé padrão", default=True)
    rodape_padrao_contato_rotulo = models.CharField("Rótulo de Contato no rodapé", max_length=120, default="Contato", blank=True)
    rodape_padrao_sobre_ativo = models.BooleanField("Exibir Sobre no rodapé padrão", default=True)
    rodape_padrao_sobre_rotulo = models.CharField("Rótulo de Sobre no rodapé", max_length=120, default="Sobre", blank=True)
    rodape_padrao_privacidade_ativo = models.BooleanField("Exibir Privacidade no rodapé padrão", default=True)
    rodape_padrao_privacidade_rotulo = models.CharField("Rótulo de Privacidade no rodapé", max_length=120, default="Privacidade e dados", blank=True)
    rodape_padrao_cookies_ativo = models.BooleanField("Exibir Cookies no rodapé padrão", default=True)
    rodape_padrao_cookies_rotulo = models.CharField("Rótulo de Cookies no rodapé", max_length=120, default="Cookies", blank=True)
    rodape_padrao_newsletter_ativo = models.BooleanField("Exibir Newsletter no rodapé padrão", default=True)
    rodape_padrao_newsletter_rotulo = models.CharField("Rótulo de Newsletter no rodapé", max_length=120, default="Newsletter", blank=True)
    rodape_padrao_indexador_ativo = models.BooleanField("Exibir Indexador no rodapé padrão", default=True)
    rodape_padrao_indexador_rotulo = models.CharField("Rótulo de Indexador no rodapé", max_length=120, default="Indexador", blank=True)
    rodape_padrao_quiz_ativo = models.BooleanField("Exibir Quiz no rodapé padrão", default=True)
    rodape_padrao_quiz_rotulo = models.CharField("Rótulo de Quiz no rodapé", max_length=120, default="Quiz", blank=True)
    tema_padrao_site = models.CharField(
        "Tema padrão do site",
        max_length=20,
        choices=TEMA_PADRAO_CHOICES,
        default=TEMA_PADRAO_CLARO,
    )
    paleta_cor_1 = models.CharField(
        "Paleta cor 1",
        max_length=7,
        default="#1f3b5c",
        help_text="Hexadecimal no formato #RRGGBB.",
    )
    paleta_cor_2 = models.CharField(
        "Paleta cor 2",
        max_length=7,
        default="#3b82f6",
        help_text="Hexadecimal no formato #RRGGBB.",
    )
    idioma_site = models.CharField(
        "Idioma do site público",
        max_length=10,
        choices=IDIOMA_SITE_CHOICES,
        default=IDIOMA_SITE_PT_BR,
        help_text="Define o idioma da interface pública (menu, rótulos e mensagens padrão).",
    )
    social_facebook_url = models.URLField(
        "Facebook (URL)",
        blank=True,
    )
    social_instagram_url = models.URLField(
        "Instagram (URL)",
        blank=True,
    )
    social_x_url = models.URLField(
        "X / Twitter (URL)",
        blank=True,
    )
    social_youtube_url = models.URLField(
        "YouTube (URL)",
        blank=True,
    )
    social_linkedin_url = models.URLField(
        "LinkedIn (URL)",
        blank=True,
    )
    shlink_ativo = models.BooleanField(
        "Ativar encurtamento com Shlink",
        default=False,
    )
    shlink_base_url = models.URLField(
        "URL base do Shlink",
        blank=True,
        help_text="Ex.: https://s.seudominio.com",
    )
    shlink_api_key = models.CharField(
        "API key do Shlink",
        max_length=255,
        blank=True,
    )
    shlink_default_domain = models.CharField(
        "Domínio padrão do Shlink",
        max_length=255,
        blank=True,
        help_text="Opcional. Use quando a instância trabalha com múltiplos domínios curtos.",
    )
    oauth_orcid_client_id = models.CharField(
        "ORCID client ID",
        max_length=255,
        blank=True,
    )
    oauth_orcid_client_secret = models.CharField(
        "ORCID client secret",
        max_length=255,
        blank=True,
    )
    oauth_github_client_id = models.CharField(
        "GitHub client ID",
        max_length=255,
        blank=True,
    )
    oauth_github_client_secret = models.CharField(
        "GitHub client secret",
        max_length=255,
        blank=True,
    )
    oauth_google_client_id = models.CharField(
        "Google client ID",
        max_length=255,
        blank=True,
    )
    oauth_google_client_secret = models.CharField(
        "Google client secret",
        max_length=255,
        blank=True,
    )
    oauth_codeberg_client_id = models.CharField(
        "Codeberg client ID",
        max_length=255,
        blank=True,
    )
    oauth_codeberg_client_secret = models.CharField(
        "Codeberg client secret",
        max_length=255,
        blank=True,
    )
    oauth_codeberg_base_url = models.URLField(
        "Codeberg base URL",
        blank=True,
        default="https://codeberg.org",
        help_text="Use a URL do Codeberg público ou de uma instância Forgejo compatível.",
    )
    oauth_gitlab_client_id = models.CharField(
        "GitLab client ID",
        max_length=255,
        blank=True,
    )
    oauth_gitlab_client_secret = models.CharField(
        "GitLab client secret",
        max_length=255,
        blank=True,
    )
    oauth_gitlab_base_url = models.URLField(
        "GitLab base URL",
        blank=True,
        default="https://gitlab.com",
        help_text="Use a URL do GitLab público ou da instância própria.",
    )
    panels = [
        FieldPanel("nome_site"),
        FieldPanel("seo_title_padrao"),
        FieldPanel("descricao_padrao"),
        FieldPanel("imagem_compartilhamento_padrao"),
        FieldPanel("favicon"),
        FieldPanel("texto_rodape"),
        FieldPanel("texto_rodape_link"),
        FieldPanel("email_contato"),
        FieldPanel("copyright_texto"),
        FieldPanel("pagina_sobre"),
        FieldPanel("pagina_privacidade"),
        FieldPanel("pagina_cookies"),
	FieldPanel("pagina_contato"),
        FieldPanel("pagina_newsletter"),
        FieldPanel("pagina_indexador"),
        FieldPanel("rotulo_indexador"),
        FieldPanel("pagina_quiz_estudo"),
        FieldPanel("rotulo_quiz_estudo"),
        FieldPanel("modo_manutencao_ativo"),
        FieldPanel("modo_manutencao_titulo"),
        FieldPanel("modo_manutencao_mensagem"),
        FieldPanel("travar_publicacao_por_orcid"),
        MultiFieldPanel(
            [
                FieldPanel("google_search_console_verification"),
                FieldPanel("meta_domain_verification"),
                FieldPanel("verificacao_head_html"),
                FieldPanel("verificacao_arquivo_nome"),
                FieldPanel("verificacao_arquivo_conteudo"),
                FieldPanel("google_analytics_id"),
                FieldPanel("google_tag_manager_id"),
                FieldPanel("meta_pixel_id"),
                FieldPanel("plausible_domain"),
                FieldPanel("plausible_script_url"),
                FieldPanel("plausible_script_direto_ativo"),
                FieldPanel("plausible_sem_consentimento_ativo"),
                FieldPanel("umami_website_id"),
                FieldPanel("umami_script_url"),
                FieldPanel("matomo_site_id"),
                FieldPanel("matomo_url"),
                FieldPanel("estatisticas_internas_ativas"),
                FieldPanel("estatisticas_reter_agregados_dias"),
                FieldPanel("estatisticas_reter_eventos_brutos_dias"),
            ],
            heading="Rastreamento e verificação",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("usar_menu_customizado"),
                FieldPanel("menu_home_exibir"),
                FieldPanel("menu_home_primeiro_fixo"),
                FieldPanel("menu_home_rotulo"),
                FieldPanel("menu_home_imagem"),
                FieldPanel("menu_home_imagem_claro"),
                FieldPanel("menu_home_imagem_escuro"),
                FieldPanel("menu_home_imagem_mobile_claro"),
                FieldPanel("menu_home_imagem_mobile_escuro"),
                FieldPanel("menu_home_logo_proporcao"),
                FieldPanel("menu_home_logo_ajuste"),
                FieldPanel("menu_home_logo_altura_desktop_px"),
                FieldPanel("menu_home_logo_altura_mobile_px"),
                FieldPanel("menu_padrao_categorias_ativo"),
                FieldPanel("menu_padrao_categorias_rotulo"),
                FieldPanel("menu_padrao_autores_ativo"),
                FieldPanel("menu_padrao_autores_rotulo"),
                FieldPanel("menu_padrao_tags_ativo"),
                FieldPanel("menu_padrao_tags_rotulo"),
                FieldPanel("menu_padrao_busca_ativo"),
                FieldPanel("menu_padrao_busca_rotulo"),
                FieldPanel("menu_padrao_destaques_ativo"),
                FieldPanel("menu_padrao_destaques_rotulo"),
                FieldPanel("menu_padrao_ultimas_ativo"),
                FieldPanel("menu_padrao_ultimas_rotulo"),
                FieldPanel("menu_padrao_contato_ativo"),
                FieldPanel("menu_padrao_contato_rotulo"),
                FieldPanel("menu_padrao_sobre_ativo"),
                FieldPanel("menu_padrao_sobre_rotulo"),
                FieldPanel("menu_padrao_newsletter_ativo"),
                FieldPanel("menu_padrao_newsletter_rotulo"),
                FieldPanel("menu_padrao_indexador_ativo"),
                FieldPanel("menu_padrao_indexador_rotulo"),
                FieldPanel("menu_padrao_quiz_ativo"),
                FieldPanel("menu_padrao_quiz_rotulo"),
                FieldPanel("menu_padrao_apoio_ativo"),
                FieldPanel("menu_padrao_apoio_rotulo"),
                FieldPanel("menu_padrao_privacidade_ativo"),
                FieldPanel("menu_padrao_privacidade_rotulo"),
                FieldPanel("menu_padrao_cookies_ativo"),
                FieldPanel("menu_padrao_cookies_rotulo"),
                FieldPanel("menu_padrao_rss_ativo"),
                FieldPanel("menu_padrao_rss_rotulo"),
                HelpPanel(
                    content=(
                        "Para o botão da home, prefira imagem horizontal com fundo transparente. "
                        "Recomendação: 320x60 px, 360x72 px ou 450x72 px, com a arte ocupando bem a largura. "
                        "Os campos mobile claro/escuro têm prioridade no celular; se ficarem vazios, o site usa as imagens do desktop automaticamente."
                    )
                ),
                HelpPanel(
                    content=(
                        '<div id="op-menu-home-logo-dimensoes" data-op-menu-home-logo-dimensoes>'
                        "As dimensões recomendadas serão calculadas automaticamente conforme a proporção e a altura escolhidas."
                        "</div>"
                    )
                ),
                HelpPanel(
                    content="Gerencie os grupos e subitens em Menu principal, no painel administrativo."
                ),
            ],
            heading="Menu customizado",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("idioma_site"),
                FieldPanel("tema_padrao_site"),
                FieldPanel("paleta_cor_1", widget=forms.TextInput(attrs={"type": "color"})),
                FieldPanel("paleta_cor_2", widget=forms.TextInput(attrs={"type": "color"})),
                HelpPanel(
                    content=(
                        "Defina 2 cores base em hexadecimal. "
                        "A segunda pode ser sugerida automaticamente e o sistema deriva as demais cores para tema claro/escuro com foco em harmonia e leitura."
                    )
                ),
            ],
            heading="Tema e paleta",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("social_facebook_url"),
                FieldPanel("social_instagram_url"),
                FieldPanel("social_linkedin_url"),
                FieldPanel("social_x_url"),
                FieldPanel("social_youtube_url"),
                HelpPanel(
                    content=(
                        "Preencha apenas as redes que deseja exibir no menu público. "
                        "Campos vazios permanecem ocultos."
                    )
                ),
            ],
            heading="Redes sociais do site",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("shlink_ativo"),
                FieldPanel("shlink_default_domain"),
                HelpPanel(
                    content=(
                        "Integra o site a uma instância Shlink para geração de links curtos de "
                        "compartilhamento e de e-mails. A configuração de credenciais foi movida para o ambiente do servidor. "
                        "Use <code>OWNPAPER_SHLINK_BASE_URL</code> e <code>OWNPAPER_SHLINK_API_KEY</code> no arquivo <code>.env</code>."
                    )
                ),
            ],
            heading="Links curtos (Shlink)",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                HelpPanel(
                    content=(
                        "Credenciais para login e verificação externa de usuários de comentários. "
                        "Neste projeto, o selo deve ser exibido sempre como 'Verificado via ...'. "
                        "A configuração foi movida para o ambiente do servidor. "
                        "Campos suportados no <code>.env</code>: <code>OWNPAPER_OAUTH_ORCID_CLIENT_ID</code>, "
                        "<code>OWNPAPER_OAUTH_ORCID_CLIENT_SECRET</code>, <code>OWNPAPER_OAUTH_GITHUB_CLIENT_ID</code>, "
                        "<code>OWNPAPER_OAUTH_GITHUB_CLIENT_SECRET</code>, <code>OWNPAPER_OAUTH_GOOGLE_CLIENT_ID</code>, "
                        "<code>OWNPAPER_OAUTH_GOOGLE_CLIENT_SECRET</code>, <code>OWNPAPER_OAUTH_CODEBERG_CLIENT_ID</code>, "
                        "<code>OWNPAPER_OAUTH_CODEBERG_CLIENT_SECRET</code>, <code>OWNPAPER_OAUTH_CODEBERG_BASE_URL</code>, "
                        "<code>OWNPAPER_OAUTH_GITLAB_CLIENT_ID</code>, <code>OWNPAPER_OAUTH_GITLAB_CLIENT_SECRET</code> "
                        "e <code>OWNPAPER_OAUTH_GITLAB_BASE_URL</code>."
                    )
                ),
            ],
            heading="Identidades externas (comentários)",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("notificacao_publicacoes_modo"),
                FieldPanel("notificacao_publicacoes_periodo_horas"),
                FieldPanel("notificacao_publicacoes_ultimo_envio_em", read_only=True),
                HelpPanel(
                    content=(
                        "As notificações de publicações são enviadas para inscritos ativos da newsletter."
                    )
                ),
            ],
            heading="Notificações por e-mail",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("comentarios_ativos"),
                FieldPanel("comentarios_auto_newsletter"),
                FieldPanel("submissoes_publicas_ativas"),
                FieldPanel("submissoes_exigir_orcid"),
                FieldPanel("submissoes_limite_pdf_mb"),
            ],
            heading="Comentários e submissões públicas",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("doacoes_ativas"),
                FieldPanel("doacoes_exibir_no_cabecalho"),
                FieldPanel("doacoes_exibir_no_rodape"),
                FieldPanel("doacoes_exibir_em_publicacoes"),
                FieldPanel("doacoes_rotulo"),
                FieldPanel("doacoes_titulo"),
                FieldPanel("doacoes_descricao"),
                FieldPanel("doacoes_pix_ativo"),
                FieldPanel("doacoes_pix_chave"),
                FieldPanel("doacoes_pix_qr_code"),
                FieldPanel("doacoes_pix_copia_cola"),
                FieldPanel("doacoes_apoiase_ativo"),
                FieldPanel("doacoes_apoiase_url"),
                FieldPanel("doacoes_buymeacoffee_ativo"),
                FieldPanel("doacoes_buymeacoffee_usuario"),
                FieldPanel("doacoes_paypal_ativo"),
                FieldPanel("doacoes_paypal_hosted_button_id"),
                FieldPanel("doacoes_paypal_business"),
                FieldPanel("doacoes_paypal_url"),
                FieldPanel("doacoes_mercadopago_ativo"),
                FieldPanel("doacoes_mercadopago_url"),
                FieldPanel("doacoes_github_sponsors_ativo"),
                FieldPanel("doacoes_github_sponsors_usuario"),
                FieldPanel("doacoes_bitcoin_ativo"),
                FieldPanel("doacoes_bitcoin_endereco"),
                FieldPanel("doacoes_ethereum_ativo"),
                FieldPanel("doacoes_ethereum_endereco"),
                FieldPanel("doacoes_link_externo"),
                FieldPanel("doacoes_detalhes"),
            ],
            heading="Apoios e doações",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("backup_email_destino"),
                FieldPanel("backup_enviar_relatorio"),
                FieldPanel("backup_ultimo_envio_em", read_only=True),
            ],
            heading="Backups",
            classname="collapsed",
        ),
    ]

    class Meta:
        verbose_name = "Configuração do site"
        verbose_name_plural = "Configurações do site"

    @property
    def rodape_links_ativos(self):
        return [
            item
            for item in self.rodape_links.all()
            if item.ativo and item.tem_link
        ]

    @property
    def paleta_derivada(self):
        return derive_palette(self.paleta_cor_1, self.paleta_cor_2)

    @property
    def menu_home_logo_ratio_par(self):
        return self.MENU_HOME_LOGO_RATIO_MAP.get(self.menu_home_logo_proporcao)

    def _menu_home_logo_width(self, altura):
        ratio = self.menu_home_logo_ratio_par
        if not ratio:
            return None
        largura, base_altura = ratio
        return round((altura * largura) / base_altura)

    @property
    def menu_home_logo_width_desktop_px(self):
        return self._menu_home_logo_width(self.menu_home_logo_altura_desktop_px)

    @property
    def menu_home_logo_width_mobile_px(self):
        return self._menu_home_logo_width(self.menu_home_logo_altura_mobile_px)

    @property
    def menu_home_logo_css_fit(self):
        return "cover" if self.menu_home_logo_ajuste == self.MENU_HOME_LOGO_AJUSTE_PREENCHER else "contain"

    @property
    def menu_home_logo_css_ratio(self):
        ratio = self.menu_home_logo_ratio_par
        if not ratio:
            return ""
        return f"{ratio[0]} / {ratio[1]}"

    @staticmethod
    def _hex_valido(valor):
        if not isinstance(valor, str):
            return False
        texto = valor.strip()
        if len(texto) != 7 or not texto.startswith("#"):
            return False
        try:
            int(texto[1:], 16)
            return True
        except ValueError:
            return False

    @classmethod
    def runtime_env_var_name(cls, field_name):
        return cls.RUNTIME_ENV_OVERRIDES.get(field_name, "")

    def get_runtime_setting(self, field_name, default=""):
        env_name = self.runtime_env_var_name(field_name)
        if env_name:
            env_value = os.getenv(env_name)
            if env_value not in (None, ""):
                return env_value.strip() if isinstance(env_value, str) else env_value
        value = getattr(self, field_name, default)
        return value.strip() if isinstance(value, str) else value

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original:
                for field_name in self.SECRET_RUNTIME_FIELDS:
                    valor_atual = getattr(self, field_name, "")
                    if valor_atual == "":
                        setattr(self, field_name, getattr(original, field_name, ""))

        cor_1 = (self.paleta_cor_1 or "").strip().lower()
        cor_2 = (self.paleta_cor_2 or "").strip().lower()

        if not self._hex_valido(cor_1):
            cor_1 = "#1f3b5c"

        # Mantém a segunda cor automática quando estiver vazia ou inválida.
        if not self._hex_valido(cor_2):
            cor_2 = suggest_secondary(cor_1)

        self.paleta_cor_1 = cor_1
        self.paleta_cor_2 = cor_2
        super().save(*args, **kwargs)


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
    ATALHO_QUIZ = "quiz"
    ATALHO_SOBRE = "sobre"
    ATALHO_APOIO = "apoio"
    ATALHO_PRIVACIDADE = "privacidade"
    ATALHO_COOKIES = "cookies"
    ATALHO_RSS = "rss"
    ATALHO_CHOICES = [
        (ATALHO_HOME, "Início"),
        (ATALHO_CATEGORIAS, "Categorias"),
        (ATALHO_TAGS, "Tags"),
        (ATALHO_AUTORES, "Autores"),
        (ATALHO_BUSCA, "Busca"),
        (ATALHO_DESTAQUES, "Âncora: Destaques"),
        (ATALHO_ULTIMAS, "Âncora: Últimas publicações"),
        (ATALHO_CONTATO, "Contato"),
        (ATALHO_NEWSLETTER, "Newsletter"),
        (ATALHO_INDEXADOR, "Indexador"),
        (ATALHO_QUIZ, "Quiz"),
        (ATALHO_SOBRE, "Sobre"),
        (ATALHO_APOIO, "Apoie"),
        (ATALHO_PRIVACIDADE, "Privacidade"),
        (ATALHO_COOKIES, "Cookies"),
        (ATALHO_RSS, "RSS"),
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


class SuperuserOnlyPermissionPolicy(ModelPermissionPolicy):
    def user_has_permission(self, user, action):
        return bool(user.is_authenticated and user.is_superuser)

    def users_with_any_permission(self, actions):
        return get_user_model().objects.filter(is_active=True, is_superuser=True)

    def instances_user_has_any_permission_for(self, user, actions):
        if self.user_has_any_permission(user, actions):
            return self.model.objects.all()
        return self.model.objects.none()


class SuperuserOnlySnippetViewSet(SnippetViewSet):
    @property
    def permission_policy(self):
        return SuperuserOnlyPermissionPolicy(self.model)


class EditorialSnippetPermissionPolicy(ModelPermissionPolicy):
    def user_has_permission(self, user, action):
        if not bool(user.is_authenticated and user.is_staff):
            return False
        from .access import can_access_publications

        return can_access_publications(user)

    def users_with_any_permission(self, actions):
        return get_user_model().objects.filter(is_active=True, is_staff=True)

    def user_has_permission_for_instance(self, user, action, instance):
        if not self.user_has_permission(user, action):
            return False

        from .access import is_admin, is_reviewer

        if is_admin(user) or is_reviewer(user):
            return True

        if action == "add":
            return True

        if action in {"change", "delete"}:
            if getattr(instance, "criado_por_id", None) != user.id:
                return False
            return getattr(instance, "aprovacao_status", "") != getattr(
                instance, "STATUS_APROVADO", "aprovado"
            )

        return False

    def instances_user_has_any_permission_for(self, user, actions):
        if not self.user_has_any_permission(user, actions):
            return self.model.objects.none()

        from .access import is_admin, is_reviewer

        if is_admin(user) or is_reviewer(user):
            return self.model.objects.all()

        approved_status = getattr(self.model, "STATUS_APROVADO", "aprovado")
        if "change" in actions or "delete" in actions:
            return self.model.objects.filter(criado_por=user).exclude(
                aprovacao_status=approved_status
            )

        return self.model.objects.filter(
            Q(aprovacao_status=approved_status) | Q(criado_por=user)
        ).distinct()


class QuizCatalogSnippetViewSet(SnippetViewSet):
    @property
    def permission_policy(self):
        return EditorialSnippetPermissionPolicy(self.model)


class EditorialSnippetViewSet(SnippetViewSet):
    @property
    def permission_policy(self):
        return EditorialSnippetPermissionPolicy(self.model)


class MenuPrincipalGrupoViewSet(SuperuserOnlySnippetViewSet):
    model = MenuPrincipalGrupo
    icon = "list-ul"
    menu_label = "Menu principal"
    menu_name = "menu-principal"
    list_display = ["titulo", "tipo", "configuracao_site", "sort_order"]
    search_fields = ["titulo", "url_externa"]
    ordering = ["configuracao_site", "sort_order", "titulo"]


register_snippet(MenuPrincipalGrupoViewSet)


class RodapeLink(models.Model):
    TIPO_PAGINA = "pagina"
    TIPO_URL = "url"
    TIPO_ATALHO = "atalho"
    TIPO_CHOICES = [
        (TIPO_PAGINA, "Página interna"),
        (TIPO_URL, "URL externa"),
        (TIPO_ATALHO, "Atalho do site"),
    ]

    configuracao_site = models.ForeignKey(
        "conteudo.ConfiguracaoSite",
        related_name="rodape_links",
        on_delete=models.CASCADE,
    )
    sort_order = models.PositiveIntegerField("Ordem", default=0)
    ativo = models.BooleanField("Ativo", default=True)
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
        FieldPanel("configuracao_site"),
        FieldPanel("sort_order"),
        FieldPanel("ativo"),
        FieldPanel("titulo"),
        FieldPanel("tipo"),
        FieldPanel("pagina"),
        FieldPanel("url_externa"),
        FieldPanel("atalho"),
        FieldPanel("abrir_nova_aba"),
    ]

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Link do rodapé"
        verbose_name_plural = "Links do rodapé"

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


class RodapeLinkViewSet(SuperuserOnlySnippetViewSet):
    model = RodapeLink
    icon = "link"
    menu_label = "Rodapé"
    menu_name = "rodape-links"
    list_display = ["titulo", "tipo", "configuracao_site", "sort_order", "ativo"]
    search_fields = ["titulo", "url_externa", "atalho"]
    ordering = ["configuracao_site", "sort_order", "titulo"]


register_snippet(RodapeLinkViewSet)


class ConviteUsuario(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_ACEITO = "aceito"
    STATUS_EXPIRADO = "expirado"
    STATUS_CANCELADO = "cancelado"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_ACEITO, "Aceito"),
        (STATUS_EXPIRADO, "Expirado"),
        (STATUS_CANCELADO, "Cancelado"),
    ]

    email = models.EmailField("E-mail")
    nome_completo = models.CharField("Nome completo", max_length=255, blank=True)
    username_sugerido = models.SlugField("Nome de usuário sugerido", max_length=80, blank=True)
    papel_admin = models.BooleanField("Admin", default=False)
    papel_autor = models.BooleanField("Autor", default=True)
    papel_revisor = models.BooleanField("Revisor", default=False)
    papel_operacao = models.BooleanField("Operação", default=False)
    pode_publicar_direto = models.BooleanField("Pode publicar direto", default=False)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    token = models.CharField("Token", max_length=64, unique=True, editable=False)
    expira_em = models.DateTimeField("Expira em")
    enviado_em = models.DateTimeField("Enviado em", null=True, blank=True)
    aceito_em = models.DateTimeField("Aceito em", null=True, blank=True)
    usuario_criado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Usuário criado",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    erro_envio = models.TextField("Erro de envio", blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    panels = [
        FieldPanel("email"),
        FieldPanel("nome_completo"),
        FieldPanel("username_sugerido"),
        MultiFieldPanel(
            [
                FieldPanel("papel_admin"),
                FieldPanel("papel_autor"),
                FieldPanel("papel_revisor"),
                FieldPanel("papel_operacao"),
                FieldPanel("pode_publicar_direto"),
            ],
            heading="Papéis do convite",
            classname="collapsed",
        ),
        FieldPanel("expira_em"),
        FieldPanel("status", read_only=True),
        FieldPanel("token", read_only=True),
        FieldPanel("enviado_em", read_only=True),
        FieldPanel("aceito_em", read_only=True),
        FieldPanel("usuario_criado", read_only=True),
        FieldPanel("erro_envio", read_only=True),
    ]

    class Meta:
        verbose_name = "Convite de usuário"
        verbose_name_plural = "Convites de usuários"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.email} ({self.resumo_papeis})"

    @property
    def resumo_papeis(self):
        papeis = []
        if self.papel_admin:
            papeis.append("Admin")
        if self.papel_autor:
            papeis.append("Autor")
        if self.papel_revisor:
            papeis.append("Revisor")
        if self.papel_operacao:
            papeis.append("Operação")
        return " / ".join(papeis) or "Sem papel"

    @property
    def link_aceite(self):
        base = getattr(settings, "PUBLIC_BASE_URL", "").strip().rstrip("/")
        return f"{base}/convites/aceitar/{self.token}/"

    @property
    def expirado(self):
        return timezone.now() > self.expira_em

    def enviar_email_convite(self):
        assunto = f"Convite para acesso ao painel - {getattr(settings, 'WAGTAIL_SITE_NAME', 'OwnPaper')}"
        corpo = (
            "<p>Você recebeu um convite para acessar o painel administrativo.</p>"
            f"<p><strong>Papéis:</strong> {self.resumo_papeis}</p>"
            f"<p><a href=\"{self.link_aceite}\">Aceitar convite e criar senha</a></p>"
            "<p>Se o botão não abrir, use este link:</p>"
            f"<p><a href=\"{self.link_aceite}\">{self.link_aceite}</a></p>"
            "<p>Se você não esperava este convite, ignore este e-mail.</p>"
        )

        email_msg = EmailMessage(
            subject=assunto,
            body=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[self.email],
        )
        email_msg.content_subtype = "html"
        email_msg.send(fail_silently=False)

    def save(self, *args, **kwargs):
        created = self._state.adding

        if not self.token:
            self.token = uuid.uuid4().hex

        if not self.expira_em:
            self.expira_em = timezone.now() + timedelta(
                days=getattr(settings, "USER_INVITE_EXPIRY_DAYS", 7)
            )

        if self.status == self.STATUS_PENDENTE and self.expirado:
            self.status = self.STATUS_EXPIRADO

        super().save(*args, **kwargs)

        if created and self.status == self.STATUS_PENDENTE and not self.enviado_em:
            try:
                self.enviar_email_convite()
                self.enviado_em = timezone.now()
                self.erro_envio = ""
                super().save(update_fields=["enviado_em", "erro_envio", "atualizado_em"])
            except Exception as exc:
                self.erro_envio = str(exc)
                super().save(update_fields=["erro_envio", "atualizado_em"])


class AuditLog(models.Model):
    HASH_VERSION = "ownpaper-audit-v1"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Usuário",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    usuario_id_ref = models.PositiveIntegerField(
        "ID técnico do usuário",
        null=True,
        blank=True,
        db_index=True,
    )
    usuario_email = models.EmailField("E-mail do usuário", blank=True)
    usuario_username = models.CharField("Username do usuário", max_length=150, blank=True)
    acao = models.CharField("Ação", max_length=80, db_index=True)
    alvo_tipo = models.CharField("Tipo de alvo", max_length=120, blank=True, db_index=True)
    alvo_id = models.CharField("ID do alvo", max_length=64, blank=True)
    alvo_repr = models.CharField("Alvo", max_length=255, blank=True)
    ip = models.CharField("IP", max_length=64, blank=True)
    detalhes = models.TextField("Detalhes", blank=True)
    criado_em = models.DateTimeField("Criado em", default=timezone.now, editable=False, db_index=True)
    sequencia = models.PositiveBigIntegerField("Sequência", null=True, blank=True, unique=True, db_index=True)
    hash_anterior = models.CharField("Hash anterior", max_length=64, blank=True, db_index=True)
    hash_registro = models.CharField("Hash do registro", max_length=64, blank=True, db_index=True)
    assinado_em = models.DateTimeField("Assinado em", null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Log de atividade"
        verbose_name_plural = "Logs de atividade"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.acao} ({self.criado_em:%d/%m/%Y %H:%M})"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Logs de auditoria não podem ser alterados.")
        if not self.sequencia or not self.hash_registro:
            with transaction.atomic():
                ultimo_log = (
                    type(self).objects.select_for_update()
                    .exclude(sequencia__isnull=True)
                    .order_by("-sequencia")
                    .first()
                )
                self.sequencia = (ultimo_log.sequencia if ultimo_log else 0) + 1
                self.hash_anterior = (ultimo_log.hash_registro if ultimo_log else "") or ""
                if not self.criado_em:
                    self.criado_em = timezone.now()
                self.assinado_em = self.assinado_em or timezone.now()
                self.hash_registro = self.calcular_hash_registro()
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Logs de auditoria não podem ser removidos.")

    @staticmethod
    def _valor_hash(valor):
        if valor is None:
            return ""
        if hasattr(valor, "isoformat"):
            return valor.isoformat()
        return str(valor)

    @classmethod
    def calcular_hash_para_valores(
        cls,
        *,
        sequencia,
        hash_anterior,
        usuario_id_ref,
        usuario_email,
        usuario_username,
        acao,
        alvo_tipo,
        alvo_id,
        alvo_repr,
        ip,
        detalhes,
        criado_em,
        assinado_em,
    ):
        payload = {
            "versao": cls.HASH_VERSION,
            "sequencia": sequencia,
            "hash_anterior": hash_anterior or "",
            "usuario_id_ref": usuario_id_ref or "",
            "usuario_email": usuario_email or "",
            "usuario_username": usuario_username or "",
            "acao": acao or "",
            "alvo_tipo": alvo_tipo or "",
            "alvo_id": alvo_id or "",
            "alvo_repr": alvo_repr or "",
            "ip": ip or "",
            "detalhes": detalhes or "",
            "criado_em": cls._valor_hash(criado_em),
            "assinado_em": cls._valor_hash(assinado_em),
        }
        payload_json = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    def calcular_hash_registro(self):
        return self.calcular_hash_para_valores(
            sequencia=self.sequencia,
            hash_anterior=self.hash_anterior,
            usuario_id_ref=self.usuario_id_ref,
            usuario_email=self.usuario_email,
            usuario_username=self.usuario_username,
            acao=self.acao,
            alvo_tipo=self.alvo_tipo,
            alvo_id=self.alvo_id,
            alvo_repr=self.alvo_repr,
            ip=self.ip,
            detalhes=self.detalhes,
            criado_em=self.criado_em,
            assinado_em=self.assinado_em,
        )

    @classmethod
    def verificar_integridade(cls):
        esperado_hash_anterior = ""
        esperado_sequencia = 1
        total = 0
        for log in cls.objects.order_by("sequencia", "id").iterator():
            total += 1
            if not log.sequencia or not log.hash_registro:
                return {
                    "ok": False,
                    "total": total,
                    "erro": "Registro sem sequência ou hash.",
                    "log_id": log.id,
                }
            if log.sequencia != esperado_sequencia:
                return {
                    "ok": False,
                    "total": total,
                    "erro": "Sequência quebrada.",
                    "log_id": log.id,
                    "esperado": esperado_sequencia,
                    "encontrado": log.sequencia,
                }
            if log.hash_anterior != esperado_hash_anterior:
                return {
                    "ok": False,
                    "total": total,
                    "erro": "Hash anterior incompatível.",
                    "log_id": log.id,
                }
            hash_calculado = log.calcular_hash_registro()
            if hash_calculado != log.hash_registro:
                return {
                    "ok": False,
                    "total": total,
                    "erro": "Hash do registro incompatível.",
                    "log_id": log.id,
                }
            esperado_hash_anterior = log.hash_registro
            esperado_sequencia += 1
        return {
            "ok": True,
            "total": total,
            "ultimo_hash": esperado_hash_anterior,
        }


class DisparoEmail(models.Model):
    TIPO_MANUAL = "manual"
    TIPO_PUBLICACOES_IMEDIATA = "publicacoes_imediata"
    TIPO_PUBLICACOES_PERIODICA = "publicacoes_periodica"
    TIPO_CHOICES = [
        (TIPO_MANUAL, "Manual"),
        (TIPO_PUBLICACOES_IMEDIATA, "Publicações (imediata)"),
        (TIPO_PUBLICACOES_PERIODICA, "Publicações (periódica)"),
    ]

    SEG_TODOS_USUARIOS = "todos_usuarios"
    SEG_APENAS_ADMINS = "apenas_admins"
    SEG_APENAS_AUTORES = "apenas_autores"
    SEG_NEWSLETTER = "newsletter"
    SEGMENTO_CHOICES = [
        (SEG_TODOS_USUARIOS, "Todos os usuários do painel"),
        (SEG_APENAS_ADMINS, "Apenas administradores"),
        (SEG_APENAS_AUTORES, "Apenas autores/escritores"),
        (SEG_NEWSLETTER, "Inscritos ativos da newsletter"),
    ]

    STATUS_PENDENTE = "pendente"
    STATUS_ENVIANDO = "enviando"
    STATUS_CONCLUIDO = "concluido"
    STATUS_FALHOU = "falhou"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_ENVIANDO, "Enviando"),
        (STATUS_CONCLUIDO, "Concluído"),
        (STATUS_FALHOU, "Falhou"),
    ]

    tipo = models.CharField("Tipo", max_length=30, choices=TIPO_CHOICES, default=TIPO_MANUAL)
    segmento = models.CharField("Segmento", max_length=30, choices=SEGMENTO_CHOICES)
    assunto = models.CharField("Assunto", max_length=255)
    corpo_html = models.TextField("Corpo HTML")
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDENTE,
        db_index=True,
    )
    total_destinatarios = models.PositiveIntegerField("Total de destinatários", default=0)
    total_enviados = models.PositiveIntegerField("Total enviados", default=0)
    total_falhas = models.PositiveIntegerField("Total de falhas", default=0)
    erro = models.TextField("Erro", blank=True)
    metadata = models.JSONField("Metadados", default=dict, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Criado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    enviado_em = models.DateTimeField("Enviado em", null=True, blank=True)

    class Meta:
        verbose_name = "Disparo de e-mail"
        verbose_name_plural = "Disparos de e-mail"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.assunto}"


class TemplateEmailCampanha(models.Model):
    nome = models.CharField("Nome", max_length=120, unique=True)
    assunto_padrao = models.CharField("Assunto padrão", max_length=255)
    corpo_html_padrao = models.TextField("Corpo HTML padrão")
    ativo = models.BooleanField("Ativo", default=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Criado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Template de campanha de e-mail"
        verbose_name_plural = "Templates de campanhas de e-mail"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class DisparoEmailDestino(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_ENVIADO = "enviado"
    STATUS_FALHOU = "falhou"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_ENVIADO, "Enviado"),
        (STATUS_FALHOU, "Falhou"),
    ]

    disparo = models.ForeignKey(
        "conteudo.DisparoEmail",
        verbose_name="Disparo",
        on_delete=models.CASCADE,
        related_name="destinos",
    )
    tracking_token = models.UUIDField(
        "Token de rastreio",
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    email = models.EmailField("E-mail", db_index=True)
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDENTE,
        db_index=True,
    )
    erro = models.TextField("Erro", blank=True)
    enviado_em = models.DateTimeField("Enviado em", null=True, blank=True)
    aberto_em = models.DateTimeField("Aberto em", null=True, blank=True)
    ultimo_clique_em = models.DateTimeField("Último clique em", null=True, blank=True)
    total_aberturas = models.PositiveIntegerField("Total de aberturas", default=0)
    total_cliques = models.PositiveIntegerField("Total de cliques", default=0)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Destino do disparo de e-mail"
        verbose_name_plural = "Destinos dos disparos de e-mail"
        ordering = ["id"]

    def __str__(self):
        return f"{self.email} - {self.get_status_display()}"


class DisparoEmailClique(models.Model):
    disparo = models.ForeignKey(
        "conteudo.DisparoEmail",
        verbose_name="Disparo",
        on_delete=models.CASCADE,
        related_name="cliques",
    )
    destino = models.ForeignKey(
        "conteudo.DisparoEmailDestino",
        verbose_name="Destino",
        on_delete=models.CASCADE,
        related_name="cliques",
    )
    url = models.URLField("URL clicada", max_length=2000)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Clique de disparo de e-mail"
        verbose_name_plural = "Cliques de disparos de e-mail"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["disparo", "criado_em"]),
            models.Index(fields=["destino", "criado_em"]),
        ]

    def __str__(self):
        return f"{self.destino.email} - {self.url}"


class BackupExecucao(models.Model):
    TIPO_MANUAL = "manual"
    TIPO_AGENDADO = "agendado"
    TIPO_PAINEL = "painel"
    TIPO_CHOICES = [
        (TIPO_MANUAL, "Manual"),
        (TIPO_AGENDADO, "Agendado"),
        (TIPO_PAINEL, "Painel"),
    ]

    STATUS_PENDENTE = "pendente"
    STATUS_EM_EXECUCAO = "em_execucao"
    STATUS_CONCLUIDO = "concluido"
    STATUS_FALHOU = "falhou"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_EM_EXECUCAO, "Em execução"),
        (STATUS_CONCLUIDO, "Concluído"),
        (STATUS_FALHOU, "Falhou"),
    ]

    FORMATO_PGDUMP = "pg_dump"
    FORMATO_JSON = "json"
    FORMATO_CHOICES = [
        (FORMATO_PGDUMP, "pg_dump"),
        (FORMATO_JSON, "JSON (dumpdata)"),
    ]

    site = models.ForeignKey(
        "wagtailcore.Site",
        verbose_name="Site",
        on_delete=models.CASCADE,
        related_name="backups_execucoes",
    )
    tipo = models.CharField("Tipo", max_length=20, choices=TIPO_CHOICES, default=TIPO_MANUAL)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, db_index=True)
    formato_db = models.CharField(
        "Formato do banco",
        max_length=20,
        choices=FORMATO_CHOICES,
        default=FORMATO_JSON,
    )
    inclui_midia = models.BooleanField("Inclui mídia", default=True)
    arquivo_caminho = models.CharField("Caminho do arquivo", max_length=500, blank=True)
    arquivo_tamanho_bytes = models.BigIntegerField("Tamanho (bytes)", default=0)
    checksum_sha256 = models.CharField("Checksum SHA256", max_length=64, blank=True)
    detalhes = models.JSONField("Detalhes", default=dict, blank=True)
    erro = models.TextField("Erro", blank=True)
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Solicitado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    concluido_em = models.DateTimeField("Concluído em", null=True, blank=True)

    class Meta:
        verbose_name = "Execução de backup"
        verbose_name_plural = "Execuções de backup"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.site.hostname} - {self.get_status_display()} - {self.criado_em:%d/%m/%Y %H:%M}"


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
    if atalho == MenuPrincipalGrupo.ATALHO_QUIZ and config_site and config_site.pagina_quiz_estudo:
        return config_site.pagina_quiz_estudo.url
    if atalho == MenuPrincipalGrupo.ATALHO_SOBRE and config_site and config_site.pagina_sobre:
        return config_site.pagina_sobre.url
    if atalho == MenuPrincipalGrupo.ATALHO_APOIO and config_site and config_site.doacoes_ativas:
        return "/apoio/"
    if atalho == MenuPrincipalGrupo.ATALHO_PRIVACIDADE and config_site and config_site.pagina_privacidade:
        return config_site.pagina_privacidade.url
    if atalho == MenuPrincipalGrupo.ATALHO_COOKIES and config_site and config_site.pagina_cookies:
        return config_site.pagina_cookies.url
    if atalho == MenuPrincipalGrupo.ATALHO_RSS:
        return "/rss.xml"
    return ""


class Autor(TraducaoConteudoMixin, models.Model):
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
    mastodon = models.URLField("Mastodon", blank=True)
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

    translatable_fields = ("mini_bio",)

    panels = [
        FieldPanel("nome_completo"),
        FieldPanel("nome_exibicao"),
        FieldPanel("username"),
        FieldPanel("usuario_admin"),
        FieldPanel("orcid"),
        FieldPanel("email"),
        FieldPanel("instagram"),
        FieldPanel("mastodon"),
	FieldPanel("foto"),
        FieldPanel("mini_bio"),
        FieldPanel("lattes_url"),
    ]

    class Meta:
        verbose_name = "Autor"
        verbose_name_plural = "Autores"
        ordering = ["nome_completo"]

    def clean(self):
        super().clean()
        if not self.pk:
            return

        original = Autor.objects.filter(pk=self.pk).only("orcid").first()
        if not original:
            return

        orcid_original = (original.orcid or "").strip()
        orcid_atual = (self.orcid or "").strip()
        if orcid_original and orcid_original != orcid_atual:
            raise ValidationError(
                {"orcid": "ORCID já definido. Para preservar autoria, este campo não pode ser alterado."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome_exibicao or self.nome_completo

    def miniatura_admin(self):
        nome = str(self).strip()
        inicial = (nome[:1] or "?").upper()
        if self.foto_id:
            try:
                rendition = self.foto.get_rendition("fill-48x48")
                return format_html(
                    '<img src="{}" alt="{}" width="36" height="36" '
                    'style="display:block;width:36px;height:36px;border-radius:999px;object-fit:cover;">',
                    rendition.url,
                    nome,
                )
            except Exception:
                logger.exception("Falha ao gerar miniatura do autor %s", self.pk)
        return format_html(
            '<span aria-label="Sem foto" title="Sem foto" '
            'style="display:inline-flex;width:36px;height:36px;border-radius:999px;'
            'align-items:center;justify-content:center;background:var(--w-color-surface-field,#f2f4f7);'
            'border:1px solid var(--w-color-border-furniture,#d0d5dd);'
            'color:var(--w-color-text-meta,#667085);font-weight:700;font-size:0.85rem;">{}</span>',
            inicial,
        )

    miniatura_admin.short_description = "Foto"

    @property
    def instagram_url(self):
        if not self.instagram:
            return ""
        if self.instagram.startswith(("http://", "https://")):
            return self.instagram
        username = self.instagram.lstrip("@").strip()
        return f"https://www.instagram.com/{username}/" if username else ""

    @property
    def mastodon_url(self):
        return (self.mastodon or "").strip()

    @property
    def orcid_url(self):
        if not self.orcid:
            return ""
        if self.orcid.startswith(("http://", "https://")):
            return self.orcid
        return f"https://orcid.org/{self.orcid}"

    @property
    def papeis_publicos(self):
        from .access import public_editorial_roles_for_user

        if not self.usuario_admin_id:
            return ["Autor"]
        papeis = public_editorial_roles_for_user(self.usuario_admin)
        return papeis or ["Autor"]

    @property
    def papel_publico_legivel(self):
        return " / ".join(self.papeis_publicos)


class AutorViewSet(SuperuserOnlySnippetViewSet):
    model = Autor
    icon = "user"
    menu_label = "Autores"
    menu_name = "autores"
    list_display = [
        "nome_completo",
        "miniatura_admin",
        "nome_exibicao",
        "username",
        "email",
        "orcid",
        "usuario_admin",
    ]
    search_fields = ["nome_completo", "nome_exibicao", "username", "email", "orcid"]
    ordering = ["nome_completo"]


register_snippet(AutorViewSet)


class Categoria(AprovacaoEditorialMixin, TraducaoConteudoMixin, models.Model):
    nome = models.CharField("Nome", max_length=255)
    slug = models.SlugField("Slug", max_length=255, unique=True)
    descricao = models.TextField("Descrição", blank=True)

    translatable_fields = ("nome", "descricao")

    panels = [
        FieldPanel("nome"),
        FieldPanel("slug"),
        FieldPanel("descricao"),
        MultiFieldPanel(
            [
                FieldPanel("aprovacao_status", read_only=True),
                FieldPanel("criado_por", read_only=True),
                FieldPanel("aprovado_por", read_only=True),
                FieldPanel("aprovado_em", read_only=True),
            ],
            heading="Fluxo editorial",
            classname="collapsed",
        ),
    ]

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ["nome"]

    def clean(self):
        super().clean()
        nome_normalizado = normalizar_rotulo_taxonomia(self.nome)
        if not nome_normalizado:
            return
        conflito = (
            type(self)
            .objects.exclude(pk=self.pk)
            .only("id", "nome")
        )
        for item in conflito:
            if normalizar_rotulo_taxonomia(item.nome) == nome_normalizado:
                raise ValidationError({
                    "nome": "Já existe uma categoria com este nome, considerando maiúsculas, minúsculas e acentuação."
                })

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.aplicar_fluxo_editorial()
        super().save(*args, **kwargs)


class TagPublicacao(AprovacaoEditorialMixin, TraducaoConteudoMixin, TagBase):
    free_tagging = False

    translatable_fields = ("name",)

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
        MultiFieldPanel(
            [
                FieldPanel("aprovacao_status", read_only=True),
                FieldPanel("criado_por", read_only=True),
                FieldPanel("aprovado_por", read_only=True),
                FieldPanel("aprovado_em", read_only=True),
            ],
            heading="Fluxo editorial",
            classname="collapsed",
        ),
    ]

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
        ordering = ["name"]

    def clean(self):
        super().clean()
        nome_normalizado = normalizar_rotulo_taxonomia(self.name)
        if not nome_normalizado:
            return
        conflito = (
            type(self)
            .objects.exclude(pk=self.pk)
            .only("id", "name")
        )
        for item in conflito:
            if normalizar_rotulo_taxonomia(item.name) == nome_normalizado:
                raise ValidationError({
                    "name": "Já existe uma tag com este nome, considerando maiúsculas, minúsculas e acentuação."
                })

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.aplicar_fluxo_editorial()
        super().save(*args, **kwargs)


class CategoriaViewSet(EditorialSnippetViewSet):
    model = Categoria
    icon = "folder-open-1"
    menu_label = "Categorias"
    menu_name = "categorias-editoriais"
    list_display = ["nome", "aprovacao_status", "criado_por", "aprovado_em"]
    list_filter = ["aprovacao_status", "aprovado_em"]
    search_fields = ["nome", "slug", "descricao"]
    ordering = ["nome"]


register_snippet(CategoriaViewSet)


class TagPublicacaoViewSet(EditorialSnippetViewSet):
    model = TagPublicacao
    icon = "tag"
    menu_label = "Tags"
    menu_name = "tags-editoriais"
    list_display = ["name", "aprovacao_status", "criado_por", "aprovado_em"]
    list_filter = ["aprovacao_status", "aprovado_em"]
    search_fields = ["name", "slug"]
    ordering = ["name"]


register_snippet(TagPublicacaoViewSet)

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
    marcadores_adicionais = models.TextField(
        "Marcadores adicionais",
        blank=True,
        help_text=(
            "Opcional. Use quando a mesma referência aparecer mais de uma vez com marcadores diferentes. "
            "Separe por vírgula, ponto e vírgula ou linha."
        ),
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
        FieldPanel("marcadores_adicionais"),
        MultiFieldPanel([
            FieldPanel("autor1_nome"),
            FieldPanel("autor1_sobrenome"),
            FieldPanel("autor2_nome"),
            FieldPanel("autor2_sobrenome"),
            FieldPanel("autor3_nome"),
            FieldPanel("autor3_sobrenome"),
            FieldPanel("usar_et_al"),
        ], heading="Autores", classname="collapsed"),
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

    @property
    def marcadores_lista(self):
        return dividir_marcadores_publicacao(self.marcador, self.marcadores_adicionais)

    @property
    def marcadores_display(self):
        return ", ".join(self.marcadores_lista)

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
    marcadores_adicionais = models.TextField(
        "Marcadores adicionais",
        blank=True,
        help_text=(
            "Opcional. Use quando a mesma nota aparecer mais de uma vez com marcadores diferentes. "
            "Separe por vírgula, ponto e vírgula ou linha."
        ),
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
        FieldPanel("marcadores_adicionais"),
        FieldPanel("conteudo"),
    ]

    class Meta:
        verbose_name = "Nota de rodapé"
        verbose_name_plural = "Notas de rodapé"

    def __str__(self):
        return self.marcador or f"Nota {self.sort_order + 1 if self.sort_order is not None else ''}".strip()

    @property
    def marcadores_lista(self):
        return dividir_marcadores_publicacao(self.marcador, self.marcadores_adicionais)

    @property
    def marcadores_display(self):
        return ", ".join(self.marcadores_lista)


class NotaRodapePublicacaoIdiomaManual(Orderable):
    publicacao = ParentalKey(
        "conteudo.PublicacaoPage",
        related_name="notas_rodape_idiomas",
        on_delete=models.CASCADE,
    )
    marcador_referencia = models.CharField(
        "Marcador da nota original",
        max_length=20,
        help_text=(
            "Use o mesmo marcador da nota original. Se a nota original nao tiver marcador, "
            "use o numero exibido na lista, como 1, 2, 3."
        ),
    )
    idioma_codigo = models.CharField(
        "Codigo do idioma",
        max_length=16,
        help_text="Use um codigo simples, como en, es, fr ou en-us.",
    )
    conteudo = RichTextField("Conteudo no idioma", blank=True)

    panels = [
        HelpPanel(
            content=(
                "Cadastre aqui apenas o conteudo alternativo da nota. "
                "O marcador deve apontar para uma nota de rodape ja existente na publicacao."
            )
        ),
        FieldPanel("marcador_referencia"),
        FieldPanel("idioma_codigo"),
        FieldPanel("conteudo"),
    ]

    class Meta:
        verbose_name = "Nota de rodape em outro idioma"
        verbose_name_plural = "Notas de rodape em outros idiomas"
        ordering = ["sort_order"]

    @property
    def idioma_codigo_normalizado(self):
        return normalizar_codigo_idioma_manual(self.idioma_codigo)

    @property
    def marcador_normalizado(self):
        return str(self.marcador_referencia or "").strip()

    def __str__(self):
        idioma = self.idioma_codigo_normalizado.upper()
        marcador = self.marcador_normalizado or "?"
        return f"{idioma} - nota {marcador}"

class MidiaIncorporadaPublicacao(Orderable):
    ORIGEM_EXTERNA = "externa"
    ORIGEM_LOCAL = "local"
    ORIGEM_CHOICES = [
        (ORIGEM_EXTERNA, "Vídeo externo"),
        (ORIGEM_LOCAL, "Vídeo local aprovado ou pendente"),
    ]

    publicacao = ParentalKey(
        "conteudo.PublicacaoPage",
        related_name="midias_embed",
        on_delete=models.CASCADE,
    )

    origem_video = models.CharField(
        "Origem do vídeo",
        max_length=20,
        choices=ORIGEM_CHOICES,
        default=ORIGEM_EXTERNA,
    )
    titulo = models.CharField("Título", max_length=255, blank=True)
    marcador = models.CharField(
        "Marcador",
        max_length=20,
        blank=True,
        help_text="Use no corpo do texto como [[v:marcador]]. Exemplo: se o marcador for video1, use [[v:video1]].",
    )
    marcadores_adicionais = models.TextField(
        "Marcadores adicionais",
        blank=True,
        help_text=(
            "Opcional. Use quando o mesmo vídeo aparecer mais de uma vez com marcadores diferentes. "
            "Separe por vírgula, ponto e vírgula ou linha."
        ),
    )
    url = models.URLField(
        "URL do vídeo",
        blank=True,
        help_text="Use uma URL incorporável, como YouTube ou Vimeo.",
    )
    midia_pendente = models.ForeignKey(
        "conteudo.MidiaPendente",
        verbose_name="Vídeo local",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="videos_em_publicacoes",
        limit_choices_to={"tipo": "video"},
        help_text=(
            "Use para vídeo local enviado em Mídias pendentes. Se ainda estiver pendente, "
            "o site exibe um aviso até a aprovação."
        ),
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
                "Cadastre o vídeo externo e use [[v:marcador]] no corpo para posicionar."
            )
        ),
        MultiFieldPanel(
            [
                FieldPanel("titulo"),
                FieldPanel("marcador"),
                FieldPanel("marcadores_adicionais"),
                FieldPanel("origem_video"),
                FieldPanel("url"),
                FieldPanel("midia_pendente"),
                FieldPanel("legenda"),
            ],
            heading="Posicionamento no corpo",
            help_text="Use estes campos para definir onde o vídeo aparecerá no texto.",
            classname="collapsed",
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
            classname="collapsed",
        ),
    ]

    class Meta:
        verbose_name = "Vídeo externo"
        verbose_name_plural = "Vídeos externos"

    def __str__(self):
        return self.titulo or self.url or f"Vídeo local {self.pk or ''}".strip()

    @property
    def marcadores_lista(self):
        return dividir_marcadores_publicacao(self.marcador, self.marcadores_adicionais)

    @property
    def marcadores_display(self):
        return ", ".join(self.marcadores_lista)

    @property
    def is_video_local(self):
        return self.origem_video == self.ORIGEM_LOCAL

    @property
    def video_local_aprovado(self):
        return bool(
            self.is_video_local
            and self.midia_pendente_id
            and self.midia_pendente.status == MidiaPendente.STATUS_APROVADO
            and self.midia_pendente.video_aprovado
        )

    @property
    def video_local_pendente(self):
        return bool(
            self.is_video_local
            and self.midia_pendente_id
            and self.midia_pendente.status == MidiaPendente.STATUS_PENDENTE
        )

    @property
    def video_url(self):
        if self.is_video_local:
            if self.video_local_aprovado:
                return self.midia_pendente.video_aprovado.url
            return ""
        return self.url

    @property
    def video_content_type(self):
        if self.is_video_local and self.midia_pendente_id:
            return self.midia_pendente.content_type or "video/mp4"
        return ""

    def video_publico_url(self, request=None):
        url = self.video_url
        if request is not None and url and url.startswith("/"):
            return request.build_absolute_uri(url)
        return url

class ImagemPublicacao(Orderable):
    publicacao = ParentalKey(
        "conteudo.PublicacaoPage",
        related_name="imagens_publicacao",
        on_delete=models.CASCADE,
    )

    imagem = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Imagem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    midia_pendente = models.ForeignKey(
        "conteudo.MidiaPendente",
        verbose_name="Mídia pendente",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="usos_em_publicacoes",
        limit_choices_to={"tipo": "imagem"},
        help_text="Use quando a imagem ainda depende de aprovação. Após aprovada, a imagem final será vinculada automaticamente.",
    )
    titulo = models.CharField("Título", max_length=255, blank=True)
    marcador = models.CharField(
        "Marcador",
        max_length=20,
        blank=True,
        help_text="Use no corpo do texto como [[i:marcador]]. Exemplo: se o marcador for fig1, use [[i:fig1]].",
    )
    marcadores_adicionais = models.TextField(
        "Marcadores adicionais",
        blank=True,
        help_text=(
            "Opcional. Use quando a mesma imagem aparecer mais de uma vez com marcadores diferentes. "
            "Separe por vírgula, ponto e vírgula ou linha."
        ),
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
                "Use [[i:marcador]] no corpo para posicionar a imagem. Arquivos enviados diretamente aqui "
                "são movidos para quarentena ao salvar e só aparecem como imagem final depois da aprovação."
            )
        ),
        MultiFieldPanel(
            [
                FieldPanel("imagem"),
                FieldPanel("titulo"),
                FieldPanel("marcador"),
                FieldPanel("marcadores_adicionais"),
                FieldPanel("legenda"),
            ],
            heading="Mídia e posicionamento no corpo",
            help_text=(
                "Envie a imagem normalmente. Ao salvar, o arquivo direto é movido para quarentena "
                "e a imagem final é preenchida automaticamente após aprovação."
            ),
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("credito_texto"),
                FieldPanel("credito_url"),
                FieldPanel("fonte_url"),
                FieldPanel("exibir_na_pagina"),
            ],
            heading="Créditos",
            help_text=(
                "Nos créditos finais, o perfil e a fonte são exibidos de forma padronizada."
            ),
            classname="collapsed",
        ),
    ]

    class Meta:
        verbose_name = "Imagem da publicação"
        verbose_name_plural = "Imagens da publicação"

    def __str__(self):
        return self.titulo or f"Imagem {self.pk or ''}".strip()

    @property
    def marcadores_lista(self):
        return dividir_marcadores_publicacao(self.marcador, self.marcadores_adicionais)

    @property
    def marcadores_display(self):
        return ", ".join(self.marcadores_lista)

    @property
    def imagem_disponivel(self):
        return self.imagem

    @property
    def aguardando_aprovacao(self):
        return bool(
            not self.imagem_id
            and self.midia_pendente_id
            and self.midia_pendente.status == MidiaPendente.STATUS_PENDENTE
        )


class MidiaPendente(models.Model):
    TIPO_IMAGEM = "imagem"
    TIPO_DOCUMENTO = "documento"
    TIPO_VIDEO = "video"
    TIPO_CHOICES = [
        (TIPO_IMAGEM, "Imagem"),
        (TIPO_DOCUMENTO, "Documento PDF"),
        (TIPO_VIDEO, "Vídeo"),
    ]

    STATUS_PENDENTE = "pendente"
    STATUS_APROVADO = "aprovado"
    STATUS_REJEITADO = "rejeitado"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_APROVADO, "Aprovado"),
        (STATUS_REJEITADO, "Rejeitado"),
    ]

    titulo = models.CharField("Título", max_length=255)
    tipo = models.CharField("Tipo", max_length=20, choices=TIPO_CHOICES, db_index=True)
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDENTE,
        db_index=True,
    )
    arquivo = models.FileField(
        "Arquivo sanitizado em quarentena",
        upload_to="arquivos/",
        storage=midia_pendente_storage,
    )
    nome_original = models.CharField("Nome original", max_length=255, blank=True)
    content_type = models.CharField("Content-Type", max_length=120, blank=True)
    tamanho_bytes = models.PositiveBigIntegerField("Tamanho em bytes", default=0)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Enviado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    criado_em = models.DateTimeField("Enviado em", auto_now_add=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Revisado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    revisado_em = models.DateTimeField("Revisado em", null=True, blank=True)
    observacao = models.TextField("Observação", blank=True)
    imagem_aprovada = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Imagem aprovada",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    documento_aprovado = models.ForeignKey(
        "wagtaildocs.Document",
        verbose_name="Documento aprovado",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    video_aprovado = models.FileField(
        "Vídeo aprovado",
        upload_to="videos/",
        blank=True,
    )
    substituicao_token = models.CharField(
        "Token de substituição",
        max_length=80,
        blank=True,
        db_index=True,
        help_text="Uso interno para reinserir documento aprovado em publicações.",
    )
    texto_link = models.CharField(
        "Texto do link",
        max_length=255,
        blank=True,
        help_text="Texto usado ao reinserir documento aprovado na publicação.",
    )

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Mídia pendente"
        verbose_name_plural = "Mídias pendentes"

    def __str__(self):
        return self.titulo


class PublicacaoPageAutor(Orderable):
    STATUS_CONFIRMACAO_PENDENTE = "pendente"
    STATUS_CONFIRMACAO_CONFIRMADO = "confirmado"
    STATUS_CONFIRMACAO_REJEITADO = "rejeitado"
    STATUS_CONFIRMACAO_CHOICES = [
        (STATUS_CONFIRMACAO_PENDENTE, "Pendente"),
        (STATUS_CONFIRMACAO_CONFIRMADO, "Confirmada"),
        (STATUS_CONFIRMACAO_REJEITADO, "Rejeitada"),
    ]

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
    confirmacao_status = models.CharField(
        "Confirmação de autoria",
        max_length=20,
        choices=STATUS_CONFIRMACAO_CHOICES,
        default=STATUS_CONFIRMACAO_PENDENTE,
        db_index=True,
    )
    atribuido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Atribuído por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    atribuido_em = models.DateTimeField("Atribuído em", null=True, blank=True)
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Confirmado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    confirmado_em = models.DateTimeField("Confirmado em", null=True, blank=True)
    rejeitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Rejeitado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    rejeitado_em = models.DateTimeField("Rejeitado em", null=True, blank=True)
    observacao_confirmacao = models.TextField("Observação da confirmação", blank=True)

    panels = [
        FieldPanel("autor"),
        FieldPanel("confirmacao_status", read_only=True),
        FieldPanel("atribuido_por", read_only=True),
        FieldPanel("atribuido_em", read_only=True),
        FieldPanel("confirmado_por", read_only=True),
        FieldPanel("confirmado_em", read_only=True),
        FieldPanel("rejeitado_por", read_only=True),
        FieldPanel("rejeitado_em", read_only=True),
        FieldPanel("observacao_confirmacao", read_only=True),
    ]

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Autor da publicação"
        verbose_name_plural = "Autores da publicação"

    def __str__(self):
        return str(self.autor)

    @property
    def confirmada(self):
        return self.confirmacao_status == self.STATUS_CONFIRMACAO_CONFIRMADO

class PublicacoesIndexPage(TraducaoConteudoMixin, Page):
    introducao = RichTextField("Introdução", blank=True)

    translatable_fields = ("title", "seo_title", "search_description", "introducao")
    richtext_translation_fields = ("introducao",)

    parent_page_types = ["home.HomePage"]
    subpage_types = ["conteudo.PublicacaoPage"]
    max_count = 1

    content_panels = Page.content_panels + [
        FieldPanel("introducao"),
    ]
    promote_panels = PROMOTE_PANELS_SEM_MENU_SITE

    def get_context(self, request):
        context = super().get_context(request)
        context["publicacoes"] = (
            PublicacaoPage.objects.live()
            .public()
            .descendant_of(self)
            .select_related("categoria_principal")
            .prefetch_related("autores_publicacao__autor")
            .annotate(
                comentarios_aprovados_total=Count(
                    "comentarios_publicacao",
                    filter=Q(
                        comentarios_publicacao__status=ComentarioPublicacao.STATUS_APROVADO
                    ),
                    distinct=True,
                )
            )
            .order_by("-data_publicacao", "-first_published_at")
        )
        return context

    class Meta:
        verbose_name = "Pasta de publicações"
        verbose_name_plural = "Pastas de publicações"


class PublicacaoPage(TraducaoConteudoMixin, Page):
    ORDENACAO_COMPLEMENTOS_APARICAO = "aparicao"
    ORDENACAO_COMPLEMENTOS_MARCADOR = "marcador"
    ORDENACAO_COMPLEMENTOS_ALFABETICA = "alfabetica"
    ORDENACAO_COMPLEMENTOS_CHOICES = [
        (ORDENACAO_COMPLEMENTOS_APARICAO, "Ordem de aparição no texto"),
        (ORDENACAO_COMPLEMENTOS_MARCADOR, "Marcador"),
        (ORDENACAO_COMPLEMENTOS_ALFABETICA, "Ordem alfabética"),
    ]

    STATUS_EDITORIAL_RASCUNHO = "rascunho"
    STATUS_EDITORIAL_EM_REVISAO = "em_revisao"
    STATUS_EDITORIAL_AJUSTES = "ajustes_solicitados"
    STATUS_EDITORIAL_REJEITADO = "rejeitado"
    STATUS_EDITORIAL_AGENDADO = "agendado"
    STATUS_EDITORIAL_PUBLICADO = "publicado"
    STATUS_EDITORIAL_LEGADO_APROVADO = "aprovado"
    STATUS_EDITORIAL_CHOICES = [
        (STATUS_EDITORIAL_RASCUNHO, "Rascunho"),
        (STATUS_EDITORIAL_EM_REVISAO, "Em revisão"),
        (STATUS_EDITORIAL_AJUSTES, "Ajustes solicitados"),
        (STATUS_EDITORIAL_REJEITADO, "Rejeitado"),
        (STATUS_EDITORIAL_AGENDADO, "Agendado"),
        (STATUS_EDITORIAL_PUBLICADO, "Publicado"),
    ]

    data_publicacao = models.DateField("Data de publicação", default=timezone.now)
    data_atualizacao = models.DateField("Data de atualização", null=True, blank=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Atualizado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )
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
    imagem_capa_pendente = models.ForeignKey(
        "conteudo.MidiaPendente",
        verbose_name="Imagem de capa pendente",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="capas_em_publicacoes",
        limit_choices_to={"tipo": "imagem"},
        help_text="Preenchido automaticamente quando uma capa enviada por autor aguarda aprovação.",
    )
    corpo = RichTextField("Corpo", blank=True)
    tags = ClusterTaggableManager(
        through="conteudo.PublicacaoPageTag",
        blank=True,
        help_text="Use apenas etiquetas já cadastradas. Se a etiqueta necessária não aparecer, peça para um administrador cadastrá-la.",
    )

    palavras_chave = models.CharField("Palavras-chave", max_length=500, blank=True)
    quiz_habilitado = models.BooleanField(
        "Habilitar quiz nesta publicação",
        default=False,
    )
    comentarios_habilitados = models.BooleanField(
        "Habilitar comentários nesta publicação",
        default=True,
    )
    total_visualizacoes = models.PositiveIntegerField(
        "Total de visualizações",
        default=0,
    )
    total_avaliacoes = models.PositiveIntegerField(
        "Total de avaliações",
        default=0,
    )
    soma_avaliacoes_meio = models.PositiveIntegerField(
        "Soma das avaliações (meio ponto)",
        default=0,
        help_text="Armazena a soma das notas em escala de meio ponto. Ex.: 3,5 = 7.",
    )
    ordenacao_notas_rodape = models.CharField(
        "Ordenação das notas de rodapé",
        max_length=20,
        choices=ORDENACAO_COMPLEMENTOS_CHOICES,
        default=ORDENACAO_COMPLEMENTOS_APARICAO,
    )
    ordenacao_referencias = models.CharField(
        "Ordenação das referências",
        max_length=20,
        choices=ORDENACAO_COMPLEMENTOS_CHOICES,
        default=ORDENACAO_COMPLEMENTOS_APARICAO,
    )
    ordenacao_creditos = models.CharField(
        "Ordenação dos créditos de mídia",
        max_length=20,
        choices=ORDENACAO_COMPLEMENTOS_CHOICES,
        default=ORDENACAO_COMPLEMENTOS_APARICAO,
    )
    status_editorial = models.CharField(
        "Status editorial",
        max_length=32,
        choices=STATUS_EDITORIAL_CHOICES,
        default=STATUS_EDITORIAL_RASCUNHO,
        db_index=True,
    )
    revisao_solicitada_em = models.DateTimeField(
        "Revisão solicitada em",
        null=True,
        blank=True,
    )
    revisao_solicitada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Revisão solicitada por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    publicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Publicado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    publicado_em = models.DateTimeField(
        "Publicado em",
        null=True,
        blank=True,
    )
    reabertura_solicitada = models.BooleanField(
        "Reabertura solicitada",
        default=False,
    )
    reabertura_solicitada_em = models.DateTimeField(
        "Reabertura solicitada em",
        null=True,
        blank=True,
    )
    reabertura_solicitada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Reabertura solicitada por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    translatable_fields = (
        "title",
        "seo_title",
        "search_description",
        "resumo",
        "corpo",
        "palavras_chave",
    )
    richtext_translation_fields = ("resumo", "corpo")
    sync_translation_skip_fields = ("corpo",)

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("data_publicacao"),
                FieldPanel("data_atualizacao"),
                FieldPanel("atualizado_por", read_only=True),
                FieldPanel("categoria_principal"),
                InlinePanel("autores_publicacao", label="Autores"),
                FieldPanel("tags"),
            ],
            heading="1. Metadados editoriais",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("resumo"),
                FieldPanel("palavras_chave"),
                FieldPanel("imagem_capa"),
                FieldPanel("quiz_habilitado"),
                FieldPanel("comentarios_habilitados"),
            ],
            heading="2. Resumo e capa",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                HelpPanel(
                    content=(
                        "Marcadores no corpo: [[i:marcador]] imagem, [[v:marcador]] video, "
                        "[[n:marcador]] nota, [[r:marcador]] referencia e "
                        "[[a:marcador]] ancora interna. Para o link, use o recurso nativo "
                        "de links do editor apontando para #marcador."
                    )
                ),
                FieldPanel("corpo"),
            ],
            heading="3. Corpo da publicacao",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                HelpPanel(
                    content=(
                        "Opcional. Cadastre versões manuais da publicação em outros idiomas. "
                        "Essas versões serão exibidas por um seletor no topo da publicação e usadas também no PDF."
                    )
                ),
                InlinePanel(
                    "idiomas_manuscritos",
                    label="Versões manuais em outros idiomas",
                ),
            ],
            heading="3.1 Idiomas alternativos",
            classname="collapsed",
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
                    "notas_rodape_idiomas",
                    label="Notas de rodape em outros idiomas",
                    help_text=(
                        "Opcional. Use o mesmo marcador da nota original e informe o idioma manual."
                    ),
                ),
                InlinePanel(
                    "referencias",
                    label="Referencias",
                    help_text="Referencie no corpo com [[r:marcador]].",
                ),
                MultiFieldPanel(
                    [
                        FieldPanel("ordenacao_notas_rodape"),
                        FieldPanel("ordenacao_referencias"),
                        FieldPanel("ordenacao_creditos"),
                    ],
                    heading="Ordenação dos complementos no final da publicação",
                    help_text=(
                        "O padrão é a ordem de aparição no texto. A ordenação por marcador usa ordem natural, "
                        "então 2 vem antes de 10."
                    ),
                    classname="collapsed",
                ),
                HelpPanel(
                    content=(
                        'Busque perguntas já cadastradas no catálogo abaixo. '
                        'Se precisar criar uma nova, use <a href="/admin/perguntas-quiz/" target="_blank" rel="noopener noreferrer">Perguntas do quiz</a> '
                        'ou abra direto a tela de <a href="/admin/snippets/conteudo/perguntaquizcatalogo/add/" target="_blank" rel="noopener noreferrer">nova pergunta reutilizável</a>.'
                    )
                ),
                InlinePanel(
                    "quiz_perguntas_reutilizaveis",
                    label="Perguntas do quiz",
                    help_text=(
                        "Opcional. Vincule perguntas cadastradas no catálogo reutilizável. "
                        "No seletor, pesquise pelo ID exato ou por trechos da pergunta/explicação. "
                        "Novas perguntas devem ser criadas no catálogo e depois vinculadas aqui."
                    ),
                ),
            ],
            heading="4. Complementos tecnicos",
            classname="collapsed",
        ),
    ]
    promote_panels = PROMOTE_PANELS_SEM_MENU_SITE

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
            if item.confirmacao_status == PublicacaoPageAutor.STATUS_CONFIRMACAO_CONFIRMADO
        ]

    @property
    def autores_editoriais_ordenados(self):
        return [
            item.autor
            for item in self.autores_publicacao.select_related("autor").order_by("sort_order")
        ]

    @property
    def possui_autoria_pendente(self):
        return self.autores_publicacao.filter(
            confirmacao_status=PublicacaoPageAutor.STATUS_CONFIRMACAO_PENDENTE
        ).exists()

    @property
    def possui_autoria_rejeitada(self):
        return self.autores_publicacao.filter(
            confirmacao_status=PublicacaoPageAutor.STATUS_CONFIRMACAO_REJEITADO
        ).exists()

    @property
    def autoria_publica_fallback_nome(self):
        usuario = self.publicado_por or self.owner
        if not usuario:
            return ""
        return usuario.get_username()

    @property
    def videos_finais(self):
        return self.midias_embed.filter(exibir_no_final=True)

    @property
    def videos_com_credito(self):
        return self.ordenar_complementos_publicacao(
            [
                item for item in self.midias_embed.all()
                if item.credito_texto or item.fonte_url
            ],
            "v",
            self.ordenacao_creditos,
            self.rotulo_ordenacao_video,
        )

    @property
    def imagens_com_credito(self):
        return self.ordenar_complementos_publicacao(
            [
                item for item in self.imagens_publicacao.all()
                if item.credito_texto or item.fonte_url
            ],
            "i",
            self.ordenacao_creditos,
            self.rotulo_ordenacao_imagem,
        )

    @property
    def referencias_ordenadas(self):
        return self.ordenar_complementos_publicacao(
            self.referencias.all(),
            "r",
            self.ordenacao_referencias,
            self.rotulo_ordenacao_referencia,
        )

    def texto_para_ordenacao_complementos(self):
        return f"{self.resumo or ''}\n{self.corpo or ''}"

    def rotulo_ordenacao_video(self, item):
        return (
            item.titulo
            or item.credito_texto
            or item.fonte_url
            or item.video_url
            or item.url
            or ""
        ).strip()

    def rotulo_ordenacao_imagem(self, item):
        return (item.titulo or item.credito_texto or item.fonte_url or "").strip()

    def rotulo_ordenacao_nota(self, item):
        return strip_tags(str(item.conteudo or "")).strip()

    def rotulo_ordenacao_referencia(self, item):
        return (item.autores_formatados or item.titulo_obra or "").strip()

    def ordenar_complementos_publicacao(self, itens, prefixo, modo, rotulo_func=None):
        itens = list(itens)
        posicoes = posicoes_marcadores_publicacao(self.texto_para_ordenacao_complementos(), prefixo)

        def marcadores(item):
            lista = list(getattr(item, "marcadores_lista", []) or [])
            if not lista:
                marcador = str(getattr(item, "marcador", "") or "").strip()
                if marcador:
                    lista = [marcador]
            return lista

        def primeiro(item):
            return primeiro_marcador_em_uso(marcadores(item), posicoes)

        def chave_aparicao(item):
            encontrados = [
                posicoes[normalizar_marcador_publicacao(marcador).lower()]
                for marcador in marcadores(item)
                if normalizar_marcador_publicacao(marcador).lower() in posicoes
            ]
            posicao = min(encontrados) if encontrados else 10**12 + (getattr(item, "sort_order", 0) or 0)
            return (posicao, chave_ordenacao_marcador_publicacao(primeiro(item)), getattr(item, "sort_order", 0) or 0)

        def chave_marcador(item):
            return (chave_ordenacao_marcador_publicacao(primeiro(item)), getattr(item, "sort_order", 0) or 0)

        def chave_alfabetica(item):
            rotulo = rotulo_func(item) if rotulo_func else str(item)
            return (normalizar_rotulo_taxonomia(rotulo), chave_ordenacao_marcador_publicacao(primeiro(item)))

        if modo == self.ORDENACAO_COMPLEMENTOS_MARCADOR:
            return sorted(itens, key=chave_marcador)
        if modo == self.ORDENACAO_COMPLEMENTOS_ALFABETICA:
            return sorted(itens, key=chave_alfabetica)
        return sorted(itens, key=chave_aparicao)

    @property
    def quiz_perguntas_exibicao(self):
        perguntas_catalogo = []
        for vinculo in self.quiz_perguntas_reutilizaveis.select_related("pergunta").prefetch_related(
            "pergunta__opcoes",
            "pergunta__tags_editoriais",
            "pergunta__publicacoes_vinculadas__publicacao",
        ):
            if (
                vinculo.pergunta
                and vinculo.pergunta.ativa
                and vinculo.pergunta.aprovacao_status == PerguntaQuizCatalogo.STATUS_APROVADO
            ):
                perguntas_catalogo.append(vinculo.pergunta)
        return perguntas_catalogo

    @property
    def possui_quiz_publico(self):
        return bool(
            self.quiz_habilitado
            or self.quiz_perguntas_reutilizaveis.exists()
        )

    @property
    def revisores_aprovados_publicos(self):
        revisoes = (
            self.revisoes.select_related("revisor__autor_vinculado")
            .filter(decisao=PublicacaoRevisao.DECISAO_APROVAR)
            .order_by("concluido_em", "criado_em")
        )
        itens = []
        for revisao in revisoes:
            autor = getattr(revisao.revisor, "autor_vinculado", None)
            if autor:
                itens.append(autor)
        return itens

    @property
    def atualizador_publico(self):
        if not self.atualizado_por_id:
            return None
        if self.autores_publicacao.filter(
            autor__usuario_admin_id=self.atualizado_por_id,
            confirmacao_status=PublicacaoPageAutor.STATUS_CONFIRMACAO_CONFIRMADO,
        ).exists():
            return None
        return getattr(self.atualizado_por, "autor_vinculado", None)

    @property
    def atualizador_publico_nome(self):
        autor = self.atualizador_publico
        if autor:
            return str(autor)
        if not self.atualizado_por_id:
            return ""
        nome = self.atualizado_por.get_full_name()
        return nome or self.atualizado_por.get_username()

    @property
    def comentarios_aprovados_count(self):
        anotado = getattr(self, "comentarios_aprovados_total", None)
        if anotado is not None:
            return anotado
        return self.comentarios_publicacao.filter(
            status=ComentarioPublicacao.STATUS_APROVADO
        ).count()

    @property
    def avaliacao_media(self):
        if not self.total_avaliacoes:
            return 0
        return round((self.soma_avaliacoes_meio / 2) / self.total_avaliacoes, 1)

    @property
    def avaliacao_media_percentual(self):
        return max(0, min(100, self.avaliacao_media * 20))

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

    def normalizar_status_editorial_legado(self):
        if self.status_editorial == self.STATUS_EDITORIAL_LEGADO_APROVADO:
            self.status_editorial = self.STATUS_EDITORIAL_PUBLICADO

    def clean(self):
        self.normalizar_status_editorial_legado()
        super().clean()

    def save(self, *args, **kwargs):
        self.normalizar_status_editorial_legado()
        hoje = timezone.localdate()
        if self.pk:
            original = (
                type(self)
                .objects.filter(pk=self.pk)
                .only("data_atualizacao")
                .first()
            )
            original_data = getattr(original, "data_atualizacao", None)
            if self.data_atualizacao in {None, original_data}:
                self.data_atualizacao = hoje
        elif not self.data_atualizacao:
            self.data_atualizacao = hoje
        super().save(*args, **kwargs)

    def get_manual_translation(self, lang_code="pt-br"):
        idioma = normalizar_codigo_idioma_manual(lang_code)
        if idioma == "pt-br":
            return None
        traducoes = getattr(self, "_prefetched_objects_cache", {}).get("idiomas_manuscritos")
        if traducoes is not None:
            for item in traducoes:
                if normalizar_codigo_idioma_manual(item.idioma_codigo) == idioma:
                    return item
            return None
        return self.idiomas_manuscritos.filter(idioma_codigo__iexact=idioma).first()

    def resolve_content_language(self, lang_code="pt-br"):
        idioma = normalizar_codigo_idioma_manual(lang_code)
        traducao = self.get_manual_translation(idioma)
        if not traducao:
            idioma = "pt-br"

        def valor(campo):
            base = getattr(self, campo, "")
            if not traducao:
                return base
            manual = getattr(traducao, campo, "")
            return manual if manual not in (None, "") else base

        return {
            "lang": idioma,
            "translation": traducao,
            "title": valor("title"),
            "seo_title": valor("seo_title"),
            "search_description": valor("search_description"),
            "resumo": valor("resumo"),
            "corpo": valor("corpo"),
            "palavras_chave": valor("palavras_chave"),
        }

    def resolve_footnotes_language(self, lang_code="pt-br"):
        idioma = normalizar_codigo_idioma_manual(lang_code)
        posicoes = posicoes_marcadores_publicacao(self.texto_para_ordenacao_complementos(), "n")
        notas = self.ordenar_complementos_publicacao(
            self.notas_rodape.all(),
            "n",
            self.ordenacao_notas_rodape,
            self.rotulo_ordenacao_nota,
        )
        if idioma == "pt-br":
            return [
                {
                    "marker": primeiro_marcador_em_uso(
                        nota.marcadores_lista or [(nota.marcador or str(indice)).strip()],
                        posicoes,
                    ),
                    "markers": nota.marcadores_lista or [(nota.marcador or str(indice)).strip()],
                    "markers_display": nota.marcadores_display or (nota.marcador or str(indice)).strip(),
                    "content": nota.conteudo,
                    "source": nota,
                }
                for indice, nota in enumerate(notas, start=1)
            ]

        traducoes = list(self.notas_rodape_idiomas.all())
        traducoes_por_marcador = {
            item.marcador_normalizado: item
            for item in traducoes
            if item.idioma_codigo_normalizado == idioma and item.marcador_normalizado
        }

        resultado = []
        for indice, nota in enumerate(notas, start=1):
            marcadores = nota.marcadores_lista or [(nota.marcador or str(indice)).strip()]
            marcador = primeiro_marcador_em_uso(marcadores, posicoes)
            traducao = None
            for marcador_traducao in marcadores:
                traducao = traducoes_por_marcador.get(str(marcador_traducao or "").strip())
                if traducao:
                    break
            resultado.append(
                {
                    "marker": marcador,
                    "markers": marcadores,
                    "markers_display": ", ".join(marcadores),
                    "content": getattr(traducao, "conteudo", "") or nota.conteudo,
                    "source": nota,
                    "translation": traducao,
                }
            )
        return resultado

    def get_context(self, request):
        context = super().get_context(request)
        site = Site.find_for_request(request)
        config_site = ConfiguracaoSite.for_site(site) if site else None
        idioma_solicitado = normalizar_codigo_idioma_manual(request.GET.get("idioma") or "pt-br")
        content_data = self.resolve_content_language(idioma_solicitado)
        translated_title = content_data["title"] or self.title

        visualizacoes_sessao = request.session.get("ownpaper_publicacao_views") or {}
        agora_ts = int(timezone.now().timestamp())
        ultima_visualizacao_ts = int(visualizacoes_sessao.get(str(self.id), 0) or 0)
        if (
            not requisicao_ignorada_para_estatisticas(request)
            and agora_ts - ultima_visualizacao_ts > 60 * 60 * 6
        ):
            type(self).objects.filter(pk=self.pk).update(
                total_visualizacoes=F("total_visualizacoes") + 1
            )
            self.total_visualizacoes += 1
            visualizacoes_sessao[str(self.id)] = agora_ts
            request.session["ownpaper_publicacao_views"] = visualizacoes_sessao

        comentarios_qs = list(
            self.comentarios_publicacao.filter(
                status=ComentarioPublicacao.STATUS_APROVADO,
            )
            .select_related("usuario")
            .order_by("criado_em")
        )
        comentarios_por_pai = {}
        comentarios_topo = []
        for comentario in comentarios_qs:
            comentario.thread_children = []
            comentarios_por_pai.setdefault(comentario.comentario_pai_id, []).append(comentario)
        for comentario in comentarios_qs:
            filhos = comentarios_por_pai.get(comentario.id, [])
            comentario.thread_children = filhos
            if comentario.comentario_pai_id is None:
                comentarios_topo.append(comentario)
        comentarios_topo.reverse()
        context["comentarios_aprovados"] = comentarios_topo
        quiz_publico_disponivel = self.possui_quiz_publico
        context["quiz_publico_disponivel"] = quiz_publico_disponivel
        context["comentarios_habilitados_publico"] = bool(
            getattr(config_site, "comentarios_ativos", False)
            and self.comentarios_habilitados
        )
        context["comentario_acesso_disponivel"] = bool(
            getattr(config_site, "comentarios_ativos", False)
            and (self.comentarios_habilitados or quiz_publico_disponivel)
        )
        from .oauth_service import oauth_provider_enabled_map

        context["comentario_oauth_providers"] = (
            oauth_provider_enabled_map(config_site) if config_site else {}
        )
        usuario_comentario = None
        cookie_auth = (request.COOKIES.get("ownpaper_comment_auth") or "").strip()
        if cookie_auth:
            try:
                payload = signing.loads(
                    cookie_auth,
                    salt="ownpaper_comment_auth",
                    max_age=60 * 60 * 24 * 30,
                )
                user_id = int((payload or {}).get("uid"))
                usuario_comentario = UsuarioComentario.objects.filter(id=user_id).first()
            except Exception:
                usuario_comentario = None
        context["comentario_usuario_logado"] = usuario_comentario
        respostas_quiz_usuario = {}
        if usuario_comentario and self.possui_quiz_publico:
            perguntas_exibicao = list(self.quiz_perguntas_exibicao)
            perguntas_catalogo_ids = [item.id for item in perguntas_exibicao if item.id]
            respostas_qs = QuizRespostaUsuario.objects.filter(
                usuario=usuario_comentario,
                pergunta_catalogo_id__in=perguntas_catalogo_ids,
            ).select_related("pergunta_catalogo")
            for resposta in respostas_qs:
                pergunta_obj = resposta.pergunta_catalogo
                if not pergunta_obj:
                    continue
                respostas_quiz_usuario[pergunta_obj.quiz_dom_id] = {
                    "correta": bool(resposta.ultima_correta),
                    "selecionadas": list(resposta.selecionadas or []),
                    "respondida_em": resposta.ultima_respondida_em,
                }
        context["quiz_respostas_usuario"] = respostas_quiz_usuario
        pending = request.session.get("comentario_auth_pending") or {}
        if pending and str(pending.get("page_id")) != str(self.id):
            pending = {}
        context["comentario_auth_pending"] = pending
        status_comentario = (request.GET.get("comentario") or "").strip().lower()
        popup_state = "closed"
        if pending and status_comentario in {
            "codigo_enviado",
            "cadastro_codigo_enviado",
            "codigo_invalido",
            "token_invalido",
        }:
            popup_state = "codigo"
        elif status_comentario in {
            "login_nao_encontrado",
            "login_campos",
            "erro_email",
            "erro_envio_email",
        }:
            popup_state = "login"
        elif status_comentario in {
            "cadastro_campos",
            "erro_usuario_email",
            "erro_usuario_duplicado",
            "erro_identidade_conflito",
            "erro_orcid_duplicado",
            "erro_orcid",
            "privacidade",
        }:
            popup_state = "cadastro"
        context["comentario_popup_state"] = popup_state
        context["comentario_popup_active_state"] = (
            popup_state if popup_state in {"login", "cadastro", "codigo"} else "login"
        )
        context["comentario_popup_open"] = popup_state != "closed"
        context["comentario_popup_error"] = status_comentario if popup_state != "closed" else ""
        rating_cookie_id = (request.COOKIES.get("ownpaper_rating_id") or "").strip()
        avaliacao_usuario_meio = None
        if rating_cookie_id:
            avaliacao = self.avaliacoes_publicacao.filter(
                cookie_id=rating_cookie_id
            ).only("valor_meio").first()
            if avaliacao:
                avaliacao_usuario_meio = avaliacao.valor_meio / 2
        context["avaliacao_usuario_meio"] = avaliacao_usuario_meio
        try:
            from .shlink_service import gerar_links_compartilhamento_publicacao

            context["short_share_urls"] = gerar_links_compartilhamento_publicacao(
                request,
                self,
                titulo=translated_title or self.title,
            )
        except Exception:
            context["short_share_urls"] = {}
        context["share_urls"] = context.get("short_share_urls") or {}
        def url_idioma(codigo):
            codigo = normalizar_codigo_idioma_manual(codigo)
            if codigo == "pt-br":
                return request.path
            return f"{request.path}?{urllib.parse.urlencode({'idioma': codigo})}"

        idiomas_disponiveis = [
            {
                "code": "pt-br",
                "label": "PT",
                "title": "Português",
                "active": content_data["lang"] == "pt-br",
                "url": url_idioma("pt-br"),
            }
        ]
        for traducao in self.idiomas_manuscritos.all():
            codigo = traducao.idioma_codigo_normalizado
            idiomas_disponiveis.append(
                {
                    "code": codigo,
                    "label": traducao.idioma_rotulo_abreviado_exibicao,
                    "title": traducao.idioma_rotulo_exibicao,
                    "active": content_data["lang"] == codigo,
                    "url": url_idioma(codigo),
                }
            )
        context.update(
            {
                "content_lang": content_data["lang"],
                "content_title": content_data["title"],
                "content_seo_title": content_data["seo_title"],
                "content_search_description": content_data["search_description"],
                "content_resumo": content_data["resumo"],
                "content_corpo": content_data["corpo"],
                "content_palavras_chave": content_data["palavras_chave"],
                "content_translation": content_data["translation"],
                "content_notas_rodape": self.resolve_footnotes_language(content_data["lang"]),
                "content_language_options": idiomas_disponiveis,
                "content_current_url": next(
                    (item["url"] for item in idiomas_disponiveis if item["active"]),
                    request.get_full_path(),
                ),
                "content_current_absolute_url": request.build_absolute_uri(
                    next(
                        (item["url"] for item in idiomas_disponiveis if item["active"]),
                        request.get_full_path(),
                    )
                ),
                "content_alternate_links": [
                    {
                        "code": item["code"],
                        "title": item["title"],
                        "url": request.build_absolute_uri(item["url"]),
                    }
                    for item in idiomas_disponiveis
                ],
            }
        )
        return context


class PublicacaoIdiomaManual(Orderable):
    page = ParentalKey(
        "conteudo.PublicacaoPage",
        related_name="idiomas_manuscritos",
        on_delete=models.CASCADE,
    )
    idioma_codigo = models.CharField(
        "Código do idioma",
        max_length=16,
        help_text="Use um código simples, como en, es, fr ou en-us.",
    )
    idioma_rotulo = models.CharField(
        "Rótulo do idioma",
        max_length=80,
        blank=True,
        help_text="Opcional. Ex.: English, Español, Français.",
    )
    idioma_rotulo_abreviado = models.CharField(
        "Rótulo abreviado",
        max_length=12,
        blank=True,
        help_text="Opcional. Ex.: EN, ES, FR.",
    )
    title = models.CharField("Título", max_length=255, blank=True)
    seo_title = models.CharField("Título SEO", max_length=255, blank=True)
    search_description = models.TextField("Descrição para busca", blank=True)
    resumo = RichTextField("Resumo", blank=True)
    corpo = RichTextField("Corpo", blank=True)
    palavras_chave = models.CharField("Palavras-chave", max_length=500, blank=True)

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("idioma_codigo"),
                FieldPanel("idioma_rotulo"),
                FieldPanel("idioma_rotulo_abreviado"),
            ],
            heading="Idioma",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("title"),
                FieldPanel("seo_title"),
                FieldPanel("search_description"),
                FieldPanel("resumo"),
                FieldPanel("corpo"),
                FieldPanel("palavras_chave"),
            ],
            heading="Conteúdo manual",
            classname="collapsed",
        ),
    ]

    class Meta:
        verbose_name = "Versão manual da publicação"
        verbose_name_plural = "Versões manuais da publicação"
        ordering = ["sort_order"]

    @property
    def idioma_codigo_normalizado(self):
        return normalizar_codigo_idioma_manual(self.idioma_codigo)

    @property
    def idioma_rotulo_exibicao(self):
        return (self.idioma_rotulo or "").strip() or rotulo_idioma_manual_padrao(self.idioma_codigo)

    @property
    def idioma_rotulo_abreviado_exibicao(self):
        return (self.idioma_rotulo_abreviado or "").strip() or self.idioma_codigo_normalizado.upper()

    def clean(self):
        super().clean()
        self.idioma_codigo = self.idioma_codigo_normalizado
        if self.idioma_codigo == "pt-br":
            raise ValidationError({"idioma_codigo": "Use este bloco apenas para idiomas alternativos."})
        if not self.page_id:
            return
        conflito = (
            type(self)
            .objects.filter(page_id=self.page_id, idioma_codigo__iexact=self.idioma_codigo)
            .exclude(pk=self.pk)
            .exists()
        )
        if conflito:
            raise ValidationError({"idioma_codigo": "Já existe uma versão manual cadastrada para este idioma."})


@register_snippet
class UsuarioComentario(models.Model):
    nome = models.CharField("Nome", max_length=120, blank=True)
    email = models.EmailField("E-mail", unique=True)
    username = models.SlugField("Nome de usuário", max_length=80, unique=True)
    orcid = models.CharField("ORCID", max_length=19, blank=True)
    verificado_em = models.DateTimeField("Verificado em", auto_now_add=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    panels = [
        FieldPanel("nome"),
        FieldPanel("email"),
        FieldPanel("username"),
        FieldPanel("orcid"),
    ]

    class Meta:
        verbose_name = "Usuário de comentário"
        verbose_name_plural = "Usuários de comentário"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.username} <{self.email}>"

    def clean(self):
        super().clean()
        email = (self.email or "").strip().lower()
        username = normalizar_username_publico(self.username)
        orcid = (self.orcid or "").strip()

        conflitos = {}

        if email:
            existente = (
                type(self).objects.filter(email__iexact=email)
                .exclude(pk=self.pk)
                .first()
            )
            if existente:
                conflitos["email"] = "Já existe um usuário de comentário com este e-mail."

        if username:
            for existente in type(self).objects.exclude(pk=self.pk).only("id", "username"):
                if normalizar_username_publico(existente.username) == username:
                    conflitos["username"] = "Já existe um usuário de comentário com este nome de usuário."
                    break

        if orcid:
            existente = (
                type(self).objects.filter(orcid__iexact=orcid)
                .exclude(pk=self.pk)
                .first()
            )
            if existente:
                conflitos["orcid"] = "Já existe um usuário de comentário com este ORCID."

        if conflitos:
            raise ValidationError(conflitos)


    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        self.username = normalizar_username_publico(self.username)
        self.orcid = (self.orcid or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def certificado(self):
        return bool((self.orcid or "").strip())

    @property
    def identidade_verificada_principal(self):
        identidades = list(self.identidades_externas.all())
        if not identidades:
            return None
        prioridade = {
            IdentidadeExternaComentario.PROVIDER_ORCID: 0,
            IdentidadeExternaComentario.PROVIDER_GOOGLE: 1,
            IdentidadeExternaComentario.PROVIDER_GITHUB: 2,
            IdentidadeExternaComentario.PROVIDER_CODEBERG: 3,
            IdentidadeExternaComentario.PROVIDER_GITLAB: 4,
        }
        identidades.sort(key=lambda item: prioridade.get(item.provider, 99))
        return identidades[0]

    @property
    def selo_verificacao_legivel(self):
        identidade = self.identidade_verificada_principal
        if not identidade or identidade.provider != IdentidadeExternaComentario.PROVIDER_ORCID:
            return ""
        return identidade.selo_legivel

def submissao_publica_upload_to(instance, filename):
    nome = slugify(getattr(instance, "titulo", "") or "submissao")[:70] or "submissao"
    return f"{timezone.now():%Y/%m}/{nome}-{uuid.uuid4().hex[:12]}.pdf"


@register_snippet
class SubmissaoPublica(models.Model):
    STATUS_RECEBIDA = "recebida"
    STATUS_EM_TRIAGEM = "em_triagem"
    STATUS_AJUSTES = "ajustes_solicitados"
    STATUS_ACEITA = "aceita"
    STATUS_REJEITADA = "rejeitada"
    STATUS_CONVERTIDA = "convertida"
    STATUS_CHOICES = [
        (STATUS_RECEBIDA, "Recebida"),
        (STATUS_EM_TRIAGEM, "Em triagem"),
        (STATUS_AJUSTES, "Ajustes solicitados"),
        (STATUS_ACEITA, "Aceita"),
        (STATUS_REJEITADA, "Rejeitada"),
        (STATUS_CONVERTIDA, "Convertida em publicação"),
    ]

    usuario = models.ForeignKey(
        "conteudo.UsuarioComentario",
        verbose_name="Usuário público",
        on_delete=models.PROTECT,
        related_name="submissoes_publicas",
    )
    titulo = models.CharField("Título", max_length=255)
    resumo = models.TextField("Resumo", blank=True)
    mensagem = models.TextField("Mensagem para a equipe", blank=True)
    arquivo_pdf = models.FileField(
        "PDF sanitizado",
        upload_to=submissao_publica_upload_to,
        storage=submissao_publica_storage,
    )
    arquivo_nome_original = models.CharField("Nome original", max_length=255, blank=True)
    arquivo_tamanho = models.PositiveIntegerField("Tamanho do arquivo", default=0)
    arquivo_sha256 = models.CharField("SHA-256 do arquivo", max_length=64, db_index=True)
    status = models.CharField(
        "Status",
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_RECEBIDA,
        db_index=True,
    )
    autor_vinculado = models.ForeignKey(
        "conteudo.Autor",
        verbose_name="Autor vinculado",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submissoes_publicas",
    )
    publicacao_criada = models.ForeignKey(
        "conteudo.PublicacaoPage",
        verbose_name="Publicação criada",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submissoes_origem",
    )
    ficha_nome_completo = models.CharField("Nome completo para autoria", max_length=255, blank=True)
    ficha_nome_exibicao = models.CharField("Nome de exibição", max_length=255, blank=True)
    ficha_mini_bio = models.TextField("Mini bio", blank=True)
    ficha_instagram = models.CharField("Instagram", max_length=255, blank=True)
    ficha_mastodon = models.URLField("Mastodon", blank=True)
    ficha_lattes_url = models.URLField("Link do Lattes", blank=True)
    texto_final = models.TextField("Texto final enviado pelo autor", blank=True)
    token_acesso = models.UUIDField("Token de acesso público", default=uuid.uuid4, unique=True, editable=False)
    ip_origem = models.GenericIPAddressField("IP de origem", null=True, blank=True)
    user_agent = models.CharField("User agent", max_length=500, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)
    decidido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Decidido por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decidido_em = models.DateTimeField("Decidido em", null=True, blank=True)
    observacao_admin = models.TextField("Observação administrativa", blank=True)

    panels = [
        FieldPanel("usuario", read_only=True),
        FieldPanel("titulo"),
        FieldPanel("resumo"),
        FieldPanel("mensagem"),
        FieldPanel("arquivo_pdf", read_only=True),
        FieldPanel("arquivo_sha256", read_only=True),
        FieldPanel("status", read_only=True),
        FieldPanel("autor_vinculado", read_only=True),
        FieldPanel("publicacao_criada", read_only=True),
        FieldPanel("observacao_admin"),
    ]

    class Meta:
        verbose_name = "Submissão pública"
        verbose_name_plural = "Submissões públicas"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.titulo

    @property
    def pode_complementar_ficha(self):
        return self.status in {self.STATUS_ACEITA, self.STATUS_AJUSTES}


class IdentidadeExternaComentario(models.Model):
    PROVIDER_ORCID = "orcid"
    PROVIDER_GITHUB = "github"
    PROVIDER_GOOGLE = "google"
    PROVIDER_CODEBERG = "codeberg"
    PROVIDER_GITLAB = "gitlab"
    PROVIDER_CHOICES = [
        (PROVIDER_ORCID, "ORCID"),
        (PROVIDER_GITHUB, "GitHub"),
        (PROVIDER_GOOGLE, "Google"),
        (PROVIDER_CODEBERG, "Codeberg"),
        (PROVIDER_GITLAB, "GitLab"),
    ]

    usuario = models.ForeignKey(
        "conteudo.UsuarioComentario",
        verbose_name="Usuário",
        on_delete=models.CASCADE,
        related_name="identidades_externas",
    )
    provider = models.CharField("Provedor", max_length=20, choices=PROVIDER_CHOICES, db_index=True)
    provider_user_id = models.CharField("ID do usuário no provedor", max_length=255, db_index=True)
    provider_username = models.CharField("Nome no provedor", max_length=255, blank=True)
    nome_exibicao = models.CharField("Nome exibido pelo provedor", max_length=255, blank=True)
    email_externo = models.EmailField("E-mail do provedor", blank=True)
    email_verificado = models.BooleanField("E-mail verificado no provedor", default=False)
    perfil_url = models.URLField("URL do perfil", blank=True)
    avatar_url = models.URLField("URL do avatar", blank=True)
    escopos = models.CharField("Escopos", max_length=500, blank=True)
    payload = models.JSONField("Payload", default=dict, blank=True)
    vinculado_em = models.DateTimeField("Vinculado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    panels = [
        FieldPanel("usuario", read_only=True),
        FieldPanel("provider", read_only=True),
        FieldPanel("provider_user_id", read_only=True),
        FieldPanel("provider_username", read_only=True),
        FieldPanel("nome_exibicao", read_only=True),
        FieldPanel("email_externo", read_only=True),
        FieldPanel("email_verificado", read_only=True),
        FieldPanel("perfil_url", read_only=True),
        FieldPanel("avatar_url", read_only=True),
        FieldPanel("escopos", read_only=True),
        FieldPanel("payload", read_only=True),
    ]

    class Meta:
        verbose_name = "Identidade externa de comentário"
        verbose_name_plural = "Identidades externas de comentários"
        ordering = ["-atualizado_em", "-vinculado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_user_id"],
                name="unique_provider_identity_comment",
            )
        ]

    def __str__(self):
        return f"{self.get_provider_display()} | {self.provider_username or self.provider_user_id}"

    @property
    def selo_legivel(self):
        if self.provider == self.PROVIDER_ORCID:
            return "Verificado via ORCID"
        return ""


class ComentarioPublicacao(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_APROVADO = "aprovado"
    STATUS_REJEITADO = "rejeitado"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_APROVADO, "Aprovado"),
        (STATUS_REJEITADO, "Rejeitado"),
    ]

    publicacao = models.ForeignKey(
        "conteudo.PublicacaoPage",
        verbose_name="Publicação",
        on_delete=models.CASCADE,
        related_name="comentarios_publicacao",
    )
    usuario = models.ForeignKey(
        "conteudo.UsuarioComentario",
        verbose_name="Usuário",
        on_delete=models.CASCADE,
        related_name="comentarios",
    )
    comentario_pai = models.ForeignKey(
        "self",
        verbose_name="Comentário pai",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="respostas",
    )
    texto = models.TextField("Comentário")
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDENTE,
        db_index=True,
    )
    sinalizado_conteudo = models.BooleanField(
        "Sinalizado para moderação reforçada",
        default=False,
    )
    editado_pela_moderacao = models.BooleanField(
        "Editado pela moderação",
        default=False,
    )
    editado_moderacao_em = models.DateTimeField(
        "Editado pela moderação em",
        null=True,
        blank=True,
    )
    ip_origem = models.GenericIPAddressField("IP de origem", null=True, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    panels = [
        FieldPanel("publicacao", read_only=True),
        FieldPanel("usuario", read_only=True),
        FieldPanel("comentario_pai", read_only=True),
        FieldPanel("texto"),
        FieldPanel("sinalizado_conteudo", read_only=True),
        FieldPanel("editado_pela_moderacao", read_only=True),
        FieldPanel("editado_moderacao_em", read_only=True),
        FieldPanel("status"),
    ]

    class Meta:
        verbose_name = "Comentário da publicação"
        verbose_name_plural = "Comentários das publicações"
        ordering = ["criado_em"]

    def __str__(self):
        return f"{self.usuario.username} em {self.publicacao.title}"

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).only("texto").first()
            if original and (original.texto or "").strip() != (self.texto or "").strip():
                self.editado_pela_moderacao = True
                self.editado_moderacao_em = timezone.now()
        if self.comentario_pai_id:
            self.publicacao_id = self.comentario_pai.publicacao_id
        super().save(*args, **kwargs)

    @property
    def nivel_thread(self):
        return 1 if self.comentario_pai_id else 0


class LinkCurtoShlink(models.Model):
    CONTEXTO_PUBLICACAO = "publicacao"
    CONTEXTO_EMAIL = "email"
    CONTEXTO_MANUAL = "manual"
    CONTEXTO_CHOICES = [
        (CONTEXTO_PUBLICACAO, "Publicação"),
        (CONTEXTO_EMAIL, "E-mail"),
        (CONTEXTO_MANUAL, "Manual"),
    ]

    CANAL_WHATSAPP = "whatsapp"
    CANAL_TELEGRAM = "telegram"
    CANAL_LINKEDIN = "linkedin"
    CANAL_MASTODON = "mastodon"
    CANAL_BLUESKY = "bluesky"
    CANAL_X = "x"
    CANAL_EMAIL = "email"
    CANAL_COPIA = "copia"
    CANAL_MANUAL = "manual"
    CANAL_CHOICES = [
        (CANAL_WHATSAPP, "WhatsApp"),
        (CANAL_TELEGRAM, "Telegram"),
        (CANAL_LINKEDIN, "LinkedIn"),
        (CANAL_MASTODON, "Mastodon"),
        (CANAL_BLUESKY, "Bluesky"),
        (CANAL_X, "X"),
        (CANAL_EMAIL, "E-mail"),
        (CANAL_COPIA, "Cópia"),
        (CANAL_MANUAL, "Manual"),
    ]

    publicacao = models.ForeignKey(
        "conteudo.PublicacaoPage",
        verbose_name="Publicação",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="links_curtos_shlink",
    )
    contexto = models.CharField("Contexto", max_length=20, choices=CONTEXTO_CHOICES, default=CONTEXTO_MANUAL)
    canal = models.CharField("Canal", max_length=30, choices=CANAL_CHOICES, default=CANAL_MANUAL)
    titulo = models.CharField("Título", max_length=255, blank=True)
    long_url = models.URLField("URL original", max_length=2048)
    short_url = models.URLField("URL curta", max_length=1024, blank=True)
    short_code = models.CharField("Short code", max_length=255, blank=True)
    dominio = models.CharField("Domínio curto", max_length=255, blank=True)
    slug_customizado = models.CharField("Slug customizado", max_length=255, blank=True)
    tags = models.JSONField("Tags", default=list, blank=True)
    visits_total = models.PositiveIntegerField("Visitas totais", default=0)
    visits_non_bots = models.PositiveIntegerField("Visitas humanas", default=0)
    visits_bots = models.PositiveIntegerField("Visitas de bots", default=0)
    ultimo_sync_em = models.DateTimeField("Última sincronização", null=True, blank=True)
    ultimo_erro = models.TextField("Último erro", blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    panels = [
        FieldPanel("publicacao"),
        FieldPanel("contexto"),
        FieldPanel("canal"),
        FieldPanel("titulo"),
        FieldPanel("long_url"),
        FieldPanel("short_url"),
        FieldPanel("short_code"),
        FieldPanel("dominio"),
        FieldPanel("slug_customizado"),
        FieldPanel("tags"),
        FieldPanel("visits_total", read_only=True),
        FieldPanel("visits_non_bots", read_only=True),
        FieldPanel("visits_bots", read_only=True),
        FieldPanel("ultimo_sync_em", read_only=True),
        FieldPanel("ultimo_erro", read_only=True),
    ]

    class Meta:
        verbose_name = "Link curto do Shlink"
        verbose_name_plural = "Links curtos do Shlink"
        ordering = ["-atualizado_em", "-criado_em"]

    def __str__(self):
        alvo = self.titulo or self.short_url or self.long_url
        return f"{self.get_contexto_display()} | {self.get_canal_display()} | {alvo}"

    def save(self, *args, **kwargs):
        auto_shorten = kwargs.pop("auto_shorten", True)
        super().save(*args, **kwargs)
        if auto_shorten and self.long_url and not self.short_url:
            try:
                from .shlink_service import obter_ou_criar_link_curto

                obter_ou_criar_link_curto(
                    self.long_url,
                    canal=self.canal,
                    contexto=self.contexto,
                    publicacao=self.publicacao,
                    titulo=self.titulo,
                    tags=self.tags,
                )
                self.refresh_from_db()
            except Exception:
                pass


class AvaliacaoPublicacao(models.Model):
    publicacao = models.ForeignKey(
        "conteudo.PublicacaoPage",
        verbose_name="Publicação",
        on_delete=models.CASCADE,
        related_name="avaliacoes_publicacao",
    )
    cookie_id = models.CharField("ID do cookie", max_length=64, db_index=True)
    valor_meio = models.PositiveSmallIntegerField(
        "Nota em meio ponto",
        help_text="Escala de 1 a 10, onde 10 corresponde a 5 estrelas.",
    )
    ip_origem = models.GenericIPAddressField("IP de origem", null=True, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    panels = [
        FieldPanel("publicacao", read_only=True),
        FieldPanel("cookie_id", read_only=True),
        FieldPanel("valor_meio", read_only=True),
    ]

    class Meta:
        verbose_name = "Avaliação da publicação"
        verbose_name_plural = "Avaliações das publicações"
        ordering = ["-atualizado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["publicacao", "cookie_id"],
                name="unique_publicacao_avaliacao_cookie",
            )
        ]

    def __str__(self):
        return f"{self.publicacao.title} - {self.valor_meio / 2:.1f}"


class ComentarioVerificacaoToken(models.Model):
    token = models.UUIDField("Token", default=uuid.uuid4, unique=True, editable=False)
    publicacao = models.ForeignKey(
        "conteudo.PublicacaoPage",
        verbose_name="Publicação",
        on_delete=models.CASCADE,
        related_name="+",
    )
    email = models.EmailField("E-mail")
    username = models.SlugField("Nome de usuário", max_length=80)
    orcid = models.CharField("ORCID", max_length=19, blank=True)
    texto = models.TextField("Comentário")
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    expira_em = models.DateTimeField("Expira em")
    usado_em = models.DateTimeField("Usado em", null=True, blank=True)

    class Meta:
        verbose_name = "Token de verificação de comentário"
        verbose_name_plural = "Tokens de verificação de comentários"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Token comentário {self.email} - {self.publicacao_id}"

    @property
    def valido(self):
        return (not self.usado_em) and self.expira_em >= timezone.now()


class ComentarioAcessoCodigo(models.Model):
    FLUXO_LOGIN = "login"
    FLUXO_CADASTRO = "cadastro"
    FLUXO_CHOICES = [
        (FLUXO_LOGIN, "Entrar"),
        (FLUXO_CADASTRO, "Cadastro"),
    ]

    token = models.UUIDField("Token", default=uuid.uuid4, unique=True, editable=False)
    publicacao = models.ForeignKey(
        "conteudo.PublicacaoPage",
        verbose_name="Publicação",
        on_delete=models.CASCADE,
        related_name="+",
    )
    fluxo = models.CharField("Fluxo", max_length=20, choices=FLUXO_CHOICES, db_index=True)
    codigo = models.CharField("Código", max_length=6, db_index=True)
    email = models.EmailField("E-mail")
    username = models.SlugField("Nome de usuário", max_length=80, blank=True)
    nome = models.CharField("Nome", max_length=120, blank=True)
    orcid = models.CharField("ORCID", max_length=19, blank=True)
    usuario = models.ForeignKey(
        "conteudo.UsuarioComentario",
        verbose_name="Usuário",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    expira_em = models.DateTimeField("Expira em")
    usado_em = models.DateTimeField("Usado em", null=True, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Código de acesso para comentário"
        verbose_name_plural = "Códigos de acesso para comentários"
        ordering = ["-criado_em"]

    @property
    def valido(self):
        return (not self.usado_em) and self.expira_em >= timezone.now()


class QuizAcessoCodigo(models.Model):
    token = models.UUIDField("Token", default=uuid.uuid4, unique=True, editable=False)
    pagina = models.ForeignKey(
        "conteudo.QuizEstudoPage",
        verbose_name="Página de quiz",
        on_delete=models.CASCADE,
        related_name="+",
    )
    codigo = models.CharField("Código", max_length=6, db_index=True)
    email = models.EmailField("E-mail")
    usuario = models.ForeignKey(
        "conteudo.UsuarioComentario",
        verbose_name="Usuário",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    expira_em = models.DateTimeField("Expira em")
    usado_em = models.DateTimeField("Usado em", null=True, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Código de acesso do quiz"
        verbose_name_plural = "Códigos de acesso do quiz"
        ordering = ["-criado_em"]

    @property
    def valido(self):
        return (not self.usado_em) and self.expira_em >= timezone.now()


class QuizSessaoUsuario(models.Model):
    usuario = models.ForeignKey(
        "conteudo.UsuarioComentario",
        verbose_name="Usuário",
        on_delete=models.CASCADE,
        related_name="quiz_sessoes",
    )
    pagina = models.ForeignKey(
        "conteudo.QuizEstudoPage",
        verbose_name="Página de quiz",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sessoes_usuario",
    )
    respondidas = models.PositiveIntegerField("Respondidas", default=0)
    corretas = models.PositiveIntegerField("Corretas", default=0)
    erradas = models.PositiveIntegerField("Erradas", default=0)
    puladas = models.PositiveIntegerField("Puladas", default=0)
    consideradas = models.PositiveIntegerField("Consideradas", default=0)
    media_percentual = models.PositiveIntegerField("Média da sessão", default=0)
    detalhes = models.JSONField("Detalhes da sessão", default=dict, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    finalizado_em = models.DateTimeField("Finalizado em", auto_now_add=True)

    class Meta:
        verbose_name = "Sessão de quiz do usuário"
        verbose_name_plural = "Sessões de quiz dos usuários"
        ordering = ["-finalizado_em", "-criado_em"]

    def __str__(self):
        base = self.pagina.title if self.pagina_id else "Quiz"
        return f"{self.usuario.username} · {base} · {self.media_percentual}%"


class QuizRespostaUsuario(models.Model):
    usuario = models.ForeignKey(
        "conteudo.UsuarioComentario",
        verbose_name="Usuário",
        on_delete=models.CASCADE,
        related_name="quiz_respostas",
    )
    publicacao = models.ForeignKey(
        "conteudo.PublicacaoPage",
        verbose_name="Publicação",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quiz_respostas_usuario",
    )
    pergunta_catalogo = models.ForeignKey(
        "conteudo.PerguntaQuizCatalogo",
        verbose_name="Pergunta de catálogo",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="respostas_usuario",
    )
    ultima_correta = models.BooleanField("Última resposta correta", null=True, blank=True)
    selecionadas = models.JSONField("Índices selecionados", default=list, blank=True)
    ultima_respondida_em = models.DateTimeField("Última resposta em", auto_now=True)

    class Meta:
        verbose_name = "Resposta de quiz do usuário"
        verbose_name_plural = "Respostas de quiz dos usuários"
        ordering = ["-ultima_respondida_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "pergunta_catalogo"],
                name="unique_quiz_resposta_usuario_pergunta_catalogo",
            ),
        ]

    def __str__(self):
        pergunta = self.pergunta_catalogo
        label = getattr(pergunta, "pergunta", "Pergunta")
        return f"{self.usuario.username} · {label}"


def coletar_linhas_privacidade_por_email(email):
    linhas = []
    email_norm = (email or "").strip().lower()

    inscrito = InscritoNewsletter.objects.filter(email__iexact=email_norm).first()
    if inscrito:
        linhas.append([
            "inscrito_newsletter",
            inscrito.email,
            str(inscrito.ativo),
            str(inscrito.consentimento),
            inscrito.origem,
            inscrito.confirmado_em or "",
            inscrito.criado_em,
            "",
        ])
    else:
        linhas.append([
            "inscrito_newsletter",
            email_norm,
            "nao_encontrado",
            "",
            "",
            "",
            "",
            "",
        ])

    for evento in NewsletterEvento.objects.filter(email__iexact=email_norm).order_by("criado_em"):
        linhas.append([
            "evento_newsletter",
            evento.email,
            evento.tipo,
            evento.origem,
            evento.criado_em,
            evento.detalhes,
            "",
            "",
        ])

    usuarios = UsuarioComentario.objects.filter(email__iexact=email_norm).order_by("criado_em")
    if not usuarios.exists():
        linhas.append([
            "usuario_comentario",
            email_norm,
            "nao_encontrado",
            "",
            "",
            "",
            "",
            "",
        ])

    for usuario in usuarios:
        linhas.append([
            "usuario_comentario",
            usuario.id,
            usuario.nome,
            usuario.email,
            usuario.username,
            usuario.orcid,
            usuario.criado_em,
            usuario.atualizado_em,
        ])

        for identidade in usuario.identidades_externas.all().order_by("vinculado_em"):
            linhas.append([
                "identidade_externa",
                usuario.username,
                identidade.provider,
                identidade.provider_username,
                identidade.email_externo,
                str(identidade.email_verificado),
                identidade.perfil_url,
                identidade.vinculado_em,
            ])

        for comentario in usuario.comentarios.select_related("publicacao", "comentario_pai").order_by("criado_em"):
            linhas.append([
                "comentario_publicacao",
                usuario.username,
                comentario.publicacao.title if comentario.publicacao_id else "",
                comentario.publicacao.slug if comentario.publicacao_id else "",
                comentario.status,
                comentario.criado_em,
                comentario.comentario_pai_id or "",
                comentario.texto,
            ])

        for sessao in usuario.quiz_sessoes.select_related("pagina").order_by("finalizado_em"):
            linhas.append([
                "quiz_sessao",
                usuario.username,
                sessao.pagina.title if sessao.pagina_id else "Quiz",
                sessao.media_percentual,
                sessao.corretas,
                sessao.erradas,
                sessao.puladas,
                sessao.finalizado_em,
            ])

        for resposta in usuario.quiz_respostas.select_related(
            "publicacao", "pergunta_catalogo"
        ).order_by("ultima_respondida_em"):
            pergunta_label = resposta.pergunta_catalogo.pergunta if resposta.pergunta_catalogo_id else ""
            linhas.append([
                "quiz_resposta",
                usuario.username,
                resposta.publicacao.title if resposta.publicacao_id else "",
                pergunta_label,
                str(bool(resposta.ultima_correta)),
                ",".join(str(item) for item in (resposta.selecionadas or [])),
                resposta.ultima_respondida_em,
                "",
            ])

        for duvida in usuario.duvidas_quiz.select_related("publicacao", "pergunta_catalogo").order_by("criado_em"):
            pergunta_label = duvida.pergunta_catalogo.pergunta if duvida.pergunta_catalogo_id else ""
            linhas.append([
                "duvida_quiz",
                usuario.username,
                duvida.publicacao.title if duvida.publicacao_id else "",
                pergunta_label,
                duvida.status,
                duvida.criado_em,
                str(duvida.permitir_publicacao_comentarios),
                duvida.mensagem,
            ])

    for codigo in ComentarioAcessoCodigo.objects.filter(email__iexact=email_norm).order_by("criado_em"):
        linhas.append([
            "codigo_acesso_comentario",
            codigo.email,
            codigo.fluxo,
            codigo.criado_em,
            codigo.expira_em,
            codigo.usado_em or "",
            codigo.publicacao_id,
            "",
        ])

    for codigo in QuizAcessoCodigo.objects.filter(email__iexact=email_norm).order_by("criado_em"):
        linhas.append([
            "codigo_acesso_quiz",
            codigo.email,
            codigo.criado_em,
            codigo.expira_em,
            codigo.usado_em or "",
            codigo.pagina_id,
            "",
            "",
        ])

    for solicitacao in SolicitacaoPrivacidadeNewsletter.objects.filter(email__iexact=email_norm).order_by("criado_em"):
        linhas.append([
            "solicitacao_privacidade",
            solicitacao.email,
            solicitacao.tipo,
            solicitacao.status,
            solicitacao.criado_em,
            solicitacao.observacoes,
            solicitacao.atendida_em or "",
            solicitacao.executada_em or "",
        ])

    return linhas


def anonimizar_usuario_comentario_privacidade(usuario):
    sufixo = f"{usuario.id}-{uuid.uuid4().hex[:10]}"
    usuario.nome = "Usuário excluído"
    usuario.email = f"excluido+{sufixo}@anon.invalid"
    usuario.username = f"usuario-excluido-{usuario.id}"
    usuario.orcid = ""
    usuario.save(update_fields=["nome", "email", "username", "orcid", "atualizado_em"])


def executar_exclusao_privacidade_por_email(email):
    email_norm = (email or "").strip().lower()

    InscritoNewsletter.objects.filter(email__iexact=email_norm).delete()
    NewsletterEvento.objects.filter(email__iexact=email_norm).delete()
    ComentarioVerificacaoToken.objects.filter(email__iexact=email_norm).delete()
    ComentarioAcessoCodigo.objects.filter(email__iexact=email_norm).delete()
    QuizAcessoCodigo.objects.filter(email__iexact=email_norm).delete()

    usuarios = list(UsuarioComentario.objects.filter(email__iexact=email_norm))
    for usuario in usuarios:
        usuario.identidades_externas.all().delete()
        usuario.quiz_sessoes.all().delete()
        usuario.quiz_respostas.all().delete()
        ComentarioAcessoCodigo.objects.filter(usuario=usuario).delete()
        QuizAcessoCodigo.objects.filter(usuario=usuario).delete()
        anonimizar_usuario_comentario_privacidade(usuario)


class PerguntaQuizCatalogo(AprovacaoEditorialMixin, TraducaoConteudoMixin, ClusterableModel):
    pergunta = models.CharField("Pergunta", max_length=500)
    explicacao = models.TextField("Explicação (opcional)", blank=True)
    exigir_todas_corretas = models.BooleanField(
        "Exigir todas as respostas corretas",
        default=True,
        help_text=(
            "Se houver mais de uma opção correta, esta regra define se o usuário precisa "
            "marcar todas as corretas para acertar."
        ),
    )
    ativa = models.BooleanField("Ativa", default=True)
    categoria_editorial = models.ForeignKey(
        "conteudo.Categoria",
        verbose_name="Categoria editorial",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="perguntas_quiz_editoriais",
    )
    tags_editoriais = ParentalManyToManyField(
        "conteudo.TagPublicacao",
        verbose_name="Tags editoriais",
        blank=True,
        help_text="Use as mesmas tags editoriais disponíveis nas publicações.",
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("pergunta"),
                FieldPanel("explicacao"),
            ],
            heading="Conteúdo",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("categoria_editorial"),
                FieldPanel("tags_editoriais"),
            ],
            heading="Classificação editorial",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("aprovacao_status", read_only=True),
                FieldPanel("criado_por", read_only=True),
                FieldPanel("aprovado_por", read_only=True),
                FieldPanel("aprovado_em", read_only=True),
            ],
            heading="Fluxo editorial",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("exigir_todas_corretas"),
                FieldPanel("ativa"),
            ],
            heading="Configurações",
            classname="collapsed",
        ),
        MultiFieldPanel(
            [
                InlinePanel("opcoes", label="Opções", min_num=2),
            ],
            heading="Opções de resposta",
            classname="collapsed",
        ),
    ]

    translatable_fields = ("pergunta", "explicacao")

    class Meta:
        verbose_name = "Pergunta reutilizável do quiz"
        verbose_name_plural = "Perguntas reutilizáveis do quiz"
        ordering = ["-atualizado_em", "-criado_em"]

    def __str__(self):
        if self.pk:
            return f"#{self.pk} · {self.pergunta}"
        return self.pergunta

    def save(self, *args, **kwargs):
        self.aplicar_fluxo_editorial()
        super().save(*args, **kwargs)

    @property
    def possui_multiplas_corretas(self):
        return self.opcoes.filter(correta=True).count() > 1

    @property
    def quiz_kind(self):
        return "catalogo"

    @property
    def quiz_dom_id(self):
        return f"catalogo-{self.id}"

    @property
    def quiz_publicacoes_vinculadas(self):
        publicacoes = []
        for vinculo in self.publicacoes_vinculadas.select_related("publicacao").all():
            if (
                vinculo.publicacao_id
                and getattr(vinculo.publicacao, "live", False)
                and vinculo.publicacao.url
            ):
                publicacoes.append(vinculo.publicacao)
        return publicacoes

    @property
    def quiz_tema(self):
        return self.categoria_editorial

    @property
    def quiz_tags(self):
        return list(self.tags_editoriais.all())

    @property
    def publicacoes_vinculadas_admin(self):
        publicacoes = []
        for vinculo in self.publicacoes_vinculadas.select_related("publicacao", "publicacao__categoria_principal").prefetch_related(
            "publicacao__tags"
        ):
            if vinculo.publicacao_id:
                publicacoes.append(vinculo.publicacao)
        return sorted(publicacoes, key=lambda publicacao: (publicacao.title or "").lower())

    @property
    def tags_editoriais_ordenadas(self):
        return sorted(self.tags_editoriais.all(), key=lambda tag: (tag.name or "").lower())

    @property
    def categorias_em_uso(self):
        categorias = {}
        for publicacao in self.publicacoes_vinculadas_admin:
            if publicacao.categoria_principal_id:
                categorias[publicacao.categoria_principal_id] = publicacao.categoria_principal
        return sorted(categorias.values(), key=lambda categoria: (categoria.nome or "").lower())

    @property
    def tags_em_uso(self):
        tags = {}
        for publicacao in self.publicacoes_vinculadas_admin:
            for tag in publicacao.tags.all():
                tags[tag.id] = tag
        return sorted(tags.values(), key=lambda tag: (tag.name or "").lower())


class QuizOpcaoPerguntaCatalogo(TraducaoConteudoMixin, Orderable):
    pergunta = ParentalKey(
        "conteudo.PerguntaQuizCatalogo",
        related_name="opcoes",
        on_delete=models.CASCADE,
    )
    texto = models.CharField("Texto da opção", max_length=400)
    correta = models.BooleanField("Correta", default=False)

    panels = [
        FieldPanel("texto"),
        FieldPanel("correta"),
    ]

    translatable_fields = ("texto",)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Opção da pergunta reutilizável"
        verbose_name_plural = "Opções da pergunta reutilizável"

    def __str__(self):
        return self.texto


class PublicacaoPerguntaQuizCatalogo(Orderable):
    publicacao = ParentalKey(
        "conteudo.PublicacaoPage",
        related_name="quiz_perguntas_reutilizaveis",
        on_delete=models.CASCADE,
    )
    pergunta = models.ForeignKey(
        "conteudo.PerguntaQuizCatalogo",
        verbose_name="Pergunta do catálogo",
        on_delete=models.CASCADE,
        related_name="publicacoes_vinculadas",
    )

    panels = [
        FieldPanel("pergunta"),
    ]

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Pergunta reutilizável vinculada à publicação"
        verbose_name_plural = "Perguntas reutilizáveis vinculadas à publicação"
        constraints = [
            models.UniqueConstraint(
                fields=["publicacao", "pergunta"],
                name="unique_publicacao_pergunta_quiz_catalogo",
            )
        ]

    def __str__(self):
        return f"{self.publicacao.title} -> {self.pergunta.pergunta}"


class PublicacaoRevisao(models.Model):
    MODO_MANUAL = "manual"
    MODO_ALEATORIA = "aleatoria"
    MODO_CHOICES = [
        (MODO_MANUAL, "Manual"),
        (MODO_ALEATORIA, "Aleatória"),
    ]

    DECISAO_PENDENTE = "pendente"
    DECISAO_APROVAR = "aprovar"
    DECISAO_AJUSTES = "ajustes"
    DECISAO_REJEITAR = "rejeitar"
    DECISAO_CHOICES = [
        (DECISAO_PENDENTE, "Pendente"),
        (DECISAO_APROVAR, "Aprovar"),
        (DECISAO_AJUSTES, "Solicitar ajustes"),
        (DECISAO_REJEITAR, "Rejeitar"),
    ]

    publicacao = models.ForeignKey(
        "conteudo.PublicacaoPage",
        related_name="revisoes",
        on_delete=models.CASCADE,
    )
    revisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Revisor",
        related_name="revisoes_atribuidas",
        on_delete=models.CASCADE,
    )
    atribuido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Atribuído por",
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    modo_atribuicao = models.CharField(
        "Modo de atribuição",
        max_length=20,
        choices=MODO_CHOICES,
        default=MODO_MANUAL,
    )
    decisao = models.CharField(
        "Decisão",
        max_length=20,
        choices=DECISAO_CHOICES,
        default=DECISAO_PENDENTE,
        db_index=True,
    )
    observacoes = models.TextField("Observações", blank=True)
    concluido_em = models.DateTimeField("Concluído em", null=True, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Revisão de publicação"
        verbose_name_plural = "Revisões de publicações"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.publicacao.title} · {self.revisor.username}"


class PublicacaoComentarioRevisao(models.Model):
    publicacao = models.ForeignKey(
        "conteudo.PublicacaoPage",
        related_name="comentarios_revisao",
        on_delete=models.CASCADE,
    )
    revisao = models.ForeignKey(
        "conteudo.PublicacaoRevisao",
        verbose_name="Revisão",
        null=True,
        blank=True,
        related_name="comentarios",
        on_delete=models.SET_NULL,
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Criado por",
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    trecho = models.TextField("Trecho ou referência", blank=True)
    contexto_antes = models.TextField("Contexto anterior", blank=True)
    contexto_depois = models.TextField("Contexto posterior", blank=True)
    sugestao = models.TextField("Sugestão de alteração", blank=True)
    comentario = models.TextField("Comentário")
    resolvido = models.BooleanField("Resolvido", default=False, db_index=True)
    resolvido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Resolvido por",
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    resolvido_em = models.DateTimeField("Resolvido em", null=True, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Comentário de revisão"
        verbose_name_plural = "Comentários de revisão"
        ordering = ["resolvido", "-criado_em"]

    def __str__(self):
        return f"{self.publicacao.title} · {self.criado_por_id or '-'}"


class UsuarioPainelPerfil(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="Usuário",
        related_name="painel_perfil",
        on_delete=models.CASCADE,
    )
    pode_publicar_direto = models.BooleanField(
        "Pode publicar direto",
        default=False,
    )
    email_monitoramento_respostas = models.EmailField(
        "E-mail para monitorar respostas enviadas pelo usuário",
        blank=True,
    )
    termos_painel_versao = models.CharField(
        "Versão dos termos do painel aceita",
        max_length=40,
        blank=True,
        db_index=True,
    )
    aceitou_termos_painel_em = models.DateTimeField(
        "Aceitou os termos do painel em",
        null=True,
        blank=True,
    )
    aceitou_termos_painel_ip = models.CharField(
        "IP do aceite dos termos do painel",
        max_length=64,
        blank=True,
    )
    aceitou_termos_painel_user_agent = models.CharField(
        "User-Agent do aceite dos termos do painel",
        max_length=255,
        blank=True,
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Perfil do usuário do painel"
        verbose_name_plural = "Perfis dos usuários do painel"

    def __str__(self):
        return f"Perfil {self.usuario.username}"

    def aceitou_termos_painel_atuais(self):
        versao_atual = getattr(settings, "OWNPAPER_PANEL_TERMS_VERSION", "")
        return bool(
            self.aceitou_termos_painel_em
            and self.termos_painel_versao
            and self.termos_painel_versao == versao_atual
        )


class SolicitacaoMudancaAdmin(models.Model):
    TIPO_REMOVER_ADMIN = "remover_admin"
    TIPO_DESATIVAR_USUARIO = "desativar_usuario"
    TIPO_CHOICES = [
        (TIPO_REMOVER_ADMIN, "Remover papel de admin"),
        (TIPO_DESATIVAR_USUARIO, "Desativar usuário admin"),
    ]
    STATUS_PENDENTE = "pendente"
    STATUS_CONFIRMADA = "confirmada"
    STATUS_CANCELADA = "cancelada"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_CONFIRMADA, "Confirmada"),
        (STATUS_CANCELADA, "Cancelada"),
    ]

    usuario_alvo = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Usuário alvo",
        related_name="solicitacoes_mudanca_admin",
        on_delete=models.CASCADE,
    )
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Solicitado por",
        related_name="+",
        on_delete=models.CASCADE,
    )
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Confirmado por",
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    tipo = models.CharField("Tipo", max_length=30, choices=TIPO_CHOICES)
    payload = models.JSONField("Payload", default=dict, blank=True)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    confirmado_em = models.DateTimeField("Confirmado em", null=True, blank=True)

    class Meta:
        verbose_name = "Solicitação de mudança sensível de admin"
        verbose_name_plural = "Solicitações de mudanças sensíveis de admin"
        ordering = ["-criado_em"]


class QuizCatalogChooserFilterForm(BaseFilterForm):
    q = forms.CharField(
        label="Busca",
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "ID, pergunta ou explicação",
            }
        ),
    )
    categoria = forms.ModelChoiceField(
        label="Categoria",
        queryset=Categoria.objects.none(),
        required=False,
        empty_label="Todas",
        widget=forms.Select(attrs={"data-chooser-modal-search-filter": True}),
    )
    tag = forms.ModelChoiceField(
        label="Tag",
        queryset=TagPublicacao.objects.none(),
        required=False,
        empty_label="Todas",
        widget=forms.Select(attrs={"data-chooser-modal-search-filter": True}),
    )
    status = forms.ChoiceField(
        label="Status",
        required=False,
        choices=[
            ("", "Todos"),
            ("ativa", "Ativa"),
            ("inativa", "Inativa"),
        ],
        widget=forms.Select(attrs={"data-chooser-modal-search-filter": True}),
    )
    aprovacao = forms.ChoiceField(
        label="Aprovação",
        required=False,
        choices=[
            ("", "Todas"),
            (PerguntaQuizCatalogo.STATUS_PENDENTE, "Pendente"),
            (PerguntaQuizCatalogo.STATUS_APROVADO, "Aprovada"),
            (PerguntaQuizCatalogo.STATUS_REJEITADO, "Rejeitada"),
        ],
        widget=forms.Select(attrs={"data-chooser-modal-search-filter": True}),
    )
    uso = forms.ChoiceField(
        label="Uso",
        required=False,
        choices=[
            ("", "Todos"),
            ("em_uso", "Em uso"),
            ("sem_uso", "Sem uso"),
        ],
        widget=forms.Select(attrs={"data-chooser-modal-search-filter": True}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = Categoria.objects.order_by("nome")
        self.fields["tag"].queryset = TagPublicacao.objects.order_by("name")

    def filter(self, objects):
        objects = super().filter(objects)

        query = (self.cleaned_data.get("q") or "").strip()
        categoria = self.cleaned_data.get("categoria")
        tag = self.cleaned_data.get("tag")
        status = (self.cleaned_data.get("status") or "").strip()
        aprovacao = (self.cleaned_data.get("aprovacao") or "").strip()
        uso = (self.cleaned_data.get("uso") or "").strip()

        if query:
            filtro_q = Q(pergunta__icontains=query) | Q(explicacao__icontains=query)
            if query.isdigit():
                filtro_q |= Q(id=int(query))
            objects = objects.filter(filtro_q)
            self.is_searching = True
            self.search_query = query

        if categoria:
            objects = objects.filter(categoria_editorial=categoria)

        if tag:
            objects = objects.filter(tags_editoriais=tag).distinct()

        if status == "ativa":
            objects = objects.filter(ativa=True)
        elif status == "inativa":
            objects = objects.filter(ativa=False)

        if aprovacao in {
            PerguntaQuizCatalogo.STATUS_PENDENTE,
            PerguntaQuizCatalogo.STATUS_APROVADO,
            PerguntaQuizCatalogo.STATUS_REJEITADO,
        }:
            objects = objects.filter(aprovacao_status=aprovacao)

        if uso == "em_uso":
            objects = objects.filter(publicacoes_vinculadas__isnull=False).distinct()
        elif uso == "sem_uso":
            objects = objects.filter(publicacoes_vinculadas__isnull=True)

        return objects


class QuizCatalogChooseView(ChooseView):
    filter_form_class = QuizCatalogChooserFilterForm
    page_title = "Escolher pergunta do quiz"
    template_name = "conteudo/admin_quiz_catalogo_chooser.html"

    def get_object_list(self):
        objects = (
            self.model_class.objects.all()
            .select_related("categoria_editorial")
            .prefetch_related("tags_editoriais")
            .order_by("-atualizado_em", "-criado_em")
        )
        from .access import is_admin, is_reviewer

        if not (is_admin(self.request.user) or is_reviewer(self.request.user)):
            objects = objects.filter(
                Q(aprovacao_status=PerguntaQuizCatalogo.STATUS_APROVADO)
                | Q(criado_por=self.request.user)
            )
        return objects


class QuizCatalogChooseResultsView(ChooseResultsView):
    filter_form_class = QuizCatalogChooserFilterForm

    def get_object_list(self):
        objects = (
            self.model_class.objects.all()
            .select_related("categoria_editorial")
            .prefetch_related("tags_editoriais")
            .order_by("-atualizado_em", "-criado_em")
        )
        from .access import is_admin, is_reviewer

        if not (is_admin(self.request.user) or is_reviewer(self.request.user)):
            objects = objects.filter(
                Q(aprovacao_status=PerguntaQuizCatalogo.STATUS_APROVADO)
                | Q(criado_por=self.request.user)
            )
        return objects


class QuizCatalogChooserViewSet(SnippetChooserViewSet):
    choose_view_class = QuizCatalogChooseView
    choose_results_view_class = QuizCatalogChooseResultsView
    per_page = 15


class PerguntaQuizCatalogoViewSet(QuizCatalogSnippetViewSet):
    model = PerguntaQuizCatalogo
    icon = "help"
    menu_label = "Perguntas do quiz"
    menu_name = "perguntas-quiz-catalogo"
    chooser_viewset_class = QuizCatalogChooserViewSet
    list_display = [
        "id",
        "pergunta",
        "aprovacao_status",
        "categoria_editorial",
        "ativa",
        "atualizado_em",
    ]
    list_filter = ["aprovacao_status", "ativa", "categoria_editorial", "criado_em", "atualizado_em"]
    search_fields = ["id", "pergunta", "explicacao"]
    ordering = ["-atualizado_em", "-criado_em"]


register_snippet(PerguntaQuizCatalogoViewSet)


class DuvidaQuizPublicacao(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_RESPONDIDA = "respondida"
    STATUS_ARQUIVADA = "arquivada"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_RESPONDIDA, "Respondida"),
        (STATUS_ARQUIVADA, "Arquivada"),
    ]

    publicacao = models.ForeignKey(
        "conteudo.PublicacaoPage",
        verbose_name="Publicação",
        on_delete=models.CASCADE,
        related_name="duvidas_quiz",
    )
    pergunta_catalogo = models.ForeignKey(
        "conteudo.PerguntaQuizCatalogo",
        verbose_name="Pergunta reutilizável do quiz",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="duvidas_recebidas",
    )
    usuario = models.ForeignKey(
        "conteudo.UsuarioComentario",
        verbose_name="Usuário",
        on_delete=models.CASCADE,
        related_name="duvidas_quiz",
    )
    mensagem = models.TextField("Pergunta")
    permitir_publicacao_comentarios = models.BooleanField(
        "Permitir publicar pergunta e resposta nos comentários",
        default=False,
    )
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDENTE,
        db_index=True,
    )
    resposta = models.TextField("Resposta", blank=True)
    respondido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Respondido por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    respondido_em = models.DateTimeField("Respondido em", null=True, blank=True)
    comentario_pergunta_publicado = models.ForeignKey(
        "conteudo.ComentarioPublicacao",
        verbose_name="Comentário da pergunta publicado",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    comentario_resposta_publicado = models.ForeignKey(
        "conteudo.ComentarioPublicacao",
        verbose_name="Comentário da resposta publicado",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    publicado_como_comentario_em = models.DateTimeField(
        "Publicado nos comentários em",
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    panels = [
        FieldPanel("publicacao", read_only=True),
        FieldPanel("pergunta_catalogo", read_only=True),
        FieldPanel("usuario", read_only=True),
        FieldPanel("mensagem", read_only=True),
        FieldPanel("permitir_publicacao_comentarios", read_only=True),
        FieldPanel("status"),
        FieldPanel("resposta"),
        FieldPanel("respondido_por", read_only=True),
        FieldPanel("respondido_em", read_only=True),
        FieldPanel("comentario_pergunta_publicado", read_only=True),
        FieldPanel("comentario_resposta_publicado", read_only=True),
        FieldPanel("publicado_como_comentario_em", read_only=True),
    ]

    class Meta:
        verbose_name = "Dúvida do quiz"
        verbose_name_plural = "Dúvidas do quiz"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.publicacao.title} | {self.usuario.username}"

    @property
    def pergunta_relacionada(self):
        return self.pergunta_catalogo

    @property
    def pergunta_relacionada_texto(self):
        pergunta = self.pergunta_relacionada
        if not pergunta:
            return "Ajuda geral do quiz"
        return getattr(pergunta, "pergunta", str(pergunta))

    def clean(self):
        super().clean()
        return

    def _usuario_comentario_resposta(self):
        if self.respondido_por:
            email = (self.respondido_por.email or "").strip().lower()
            username = slugify(
                getattr(self.respondido_por, "get_full_name", lambda: "")() or self.respondido_por.username or email
            )[:80]
            nome = getattr(self.respondido_por, "get_full_name", lambda: "")() or self.respondido_por.username
            if email:
                usuario, _ = UsuarioComentario.objects.get_or_create(
                    email=email,
                    defaults={
                        "username": username or f"admin-{self.respondido_por.pk}",
                        "nome": nome,
                    },
                )
                alteracoes = []
                if nome and usuario.nome != nome:
                    usuario.nome = nome
                    alteracoes.append("nome")
                if alteracoes:
                    alteracoes.append("atualizado_em")
                    usuario.save(update_fields=alteracoes)
                return usuario

        autor = self.publicacao.autores_ordenados[0] if self.publicacao.autores_ordenados else None
        if autor and autor.email:
            usuario, _ = UsuarioComentario.objects.get_or_create(
                email=autor.email.lower(),
                defaults={
                    "username": slugify(autor.username or autor.nome_exibicao or autor.nome_completo)[:80] or f"autor-{autor.pk}",
                    "nome": autor.nome_exibicao or autor.nome_completo,
                    "orcid": autor.orcid or "",
                },
            )
            return usuario
        return None

    def publicar_em_comentarios_se_aplicavel(self):
        if (
            self.status != self.STATUS_RESPONDIDA
            or not (self.resposta or "").strip()
            or not self.permitir_publicacao_comentarios
            or self.publicado_como_comentario_em
        ):
            return

        usuario_resposta = self._usuario_comentario_resposta()
        if not usuario_resposta:
            return

        comentario_pergunta = self.comentario_pergunta_publicado
        if not comentario_pergunta:
            comentario_pergunta = ComentarioPublicacao.objects.create(
                publicacao=self.publicacao,
                usuario=self.usuario,
                texto=self.mensagem,
                status=ComentarioPublicacao.STATUS_APROVADO,
                sinalizado_conteudo=False,
            )
            self.comentario_pergunta_publicado = comentario_pergunta

        comentario_resposta = self.comentario_resposta_publicado
        if not comentario_resposta:
            comentario_resposta = ComentarioPublicacao.objects.create(
                publicacao=self.publicacao,
                usuario=usuario_resposta,
                comentario_pai=comentario_pergunta,
                texto=self.resposta,
                status=ComentarioPublicacao.STATUS_APROVADO,
                sinalizado_conteudo=False,
            )
            self.comentario_resposta_publicado = comentario_resposta

        self.publicado_como_comentario_em = timezone.now()

    def save(self, *args, **kwargs):
        if self.status == self.STATUS_RESPONDIDA and self.resposta and not self.respondido_em:
            self.respondido_em = timezone.now()
        super().save(*args, **kwargs)
        atualizacoes = []
        if self.status == self.STATUS_RESPONDIDA and self.permitir_publicacao_comentarios:
            self.publicar_em_comentarios_se_aplicavel()
            atualizacoes.extend(
                campo
                for campo in (
                    "comentario_pergunta_publicado",
                    "comentario_resposta_publicado",
                    "publicado_como_comentario_em",
                    "respondido_em",
                )
                if getattr(self, campo)
            )
        if atualizacoes:
            atualizacoes.append("atualizado_em")
            type(self).objects.filter(pk=self.pk).update(
                comentario_pergunta_publicado=self.comentario_pergunta_publicado,
                comentario_resposta_publicado=self.comentario_resposta_publicado,
                publicado_como_comentario_em=self.publicado_como_comentario_em,
                respondido_em=self.respondido_em,
                atualizado_em=timezone.now(),
            )

class PaginaInstitucionalPage(TraducaoConteudoMixin, Page):
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
    promote_panels = PROMOTE_PANELS_SEM_MENU_SITE

    translatable_fields = ("title", "seo_title", "search_description", "resumo", "corpo")
    richtext_translation_fields = ("resumo", "corpo")

    class Meta:
        verbose_name = "Página institucional"
        verbose_name_plural = "Páginas institucionais"


class QuizEstudoPage(TraducaoConteudoMixin, Page):
    introducao = RichTextField("Introdução", blank=True)
    itens_por_sessao = models.PositiveIntegerField("Perguntas por sessão", default=20)

    translatable_fields = ("title", "seo_title", "search_description", "introducao")
    richtext_translation_fields = ("introducao",)

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        FieldPanel("introducao"),
        FieldPanel("itens_por_sessao"),
    ]
    promote_panels = PROMOTE_PANELS_SEM_MENU_SITE

    class Meta:
        verbose_name = "Página de quiz de estudos"
        verbose_name_plural = "Páginas de quiz de estudos"

    def get_context(self, request):
        from .oauth_service import oauth_provider_enabled_map

        context = super().get_context(request)
        tema_slug = (request.GET.get("tema") or "").strip()
        tag_slug = (request.GET.get("tag") or "").strip()
        quiz_usuario = None
        cookie_auth = (request.COOKIES.get("ownpaper_comment_auth") or "").strip()
        if cookie_auth:
            try:
                payload = signing.loads(
                    cookie_auth,
                    salt="ownpaper_comment_auth",
                    max_age=60 * 60 * 24 * 30,
                )
                quiz_usuario = UsuarioComentario.objects.filter(id=int((payload or {}).get("uid"))).first()
            except Exception:
                quiz_usuario = None
        site = Site.find_for_request(request)
        config_site = ConfiguracaoSite.for_site(site) if site else None

        publicacoes_quiz = (
            PublicacaoPage.objects.live()
            .public()
            .filter(
                Q(quiz_habilitado=True)
                | Q(quiz_perguntas_reutilizaveis__isnull=False)
            )
            .distinct()
            .prefetch_related("tags", "quiz_perguntas_reutilizaveis__pergunta")
        )

        perguntas_catalogo_qs = (
            PerguntaQuizCatalogo.objects.filter(ativa=True)
            .filter(
                Q(publicacoes_vinculadas__publicacao__in=publicacoes_quiz)
                | Q(publicacoes_vinculadas__isnull=True)
            )
            .select_related("categoria_editorial")
            .prefetch_related(
                "opcoes",
                "tags_editoriais",
                "publicacoes_vinculadas__publicacao",
            )
            .distinct()
            .order_by("-atualizado_em", "-criado_em")
        )
        if tema_slug:
            perguntas_catalogo_qs = perguntas_catalogo_qs.filter(categoria_editorial__slug=tema_slug)
        if tag_slug:
            perguntas_catalogo_qs = perguntas_catalogo_qs.filter(tags_editoriais__slug=tag_slug)

        limite = max(1, int(self.itens_por_sessao or 20))
        perguntas_base = list(perguntas_catalogo_qs)
        random.shuffle(perguntas_base)

        perguntas = []
        for pergunta in perguntas_base:
            if len(list(pergunta.opcoes.all())) < 2:
                continue
            perguntas.append(pergunta)
            if len(perguntas) >= limite:
                break

        temas_map = {}
        for pub in publicacoes_quiz.select_related("categoria_principal"):
            if pub.categoria_principal_id:
                temas_map[(pub.categoria_principal.slug or "").strip()] = pub.categoria_principal
        for pergunta_catalogo in perguntas_catalogo_qs:
            if pergunta_catalogo.categoria_editorial_id:
                temas_map[(pergunta_catalogo.categoria_editorial.slug or "").strip()] = pergunta_catalogo.categoria_editorial
        temas = [tema for _, tema in sorted(temas_map.items(), key=lambda item: (item[1].nome or "").lower()) if _]

        tags_map = {}
        for pub in publicacoes_quiz:
            for tag in pub.tags.all():
                tags_map[(tag.slug or "").strip()] = tag
        for pergunta_catalogo in perguntas_catalogo_qs:
            for tag in pergunta_catalogo.tags_editoriais.all():
                tags_map[(tag.slug or "").strip()] = tag
        tags = [tag for _, tag in sorted(tags_map.items(), key=lambda item: (item[1].name or "").lower()) if _]

        context["tema_slug"] = tema_slug
        context["tag_slug"] = tag_slug
        context["temas_quiz"] = temas
        context["tags_quiz"] = tags
        context["quiz_perguntas"] = perguntas
        context["quiz_usuario"] = quiz_usuario
        context["comentario_oauth_providers"] = oauth_provider_enabled_map(config_site) if config_site else {}
        context["quiz_auth_pending"] = (
            (request.session.get("quiz_auth_pending") or {})
            if str((request.session.get("quiz_auth_pending") or {}).get("page_id") or "") == str(self.id)
            else {}
        )
        quiz_status = (request.GET.get("quiz_auth") or "").strip().lower()
        quiz_popup_state = "closed"
        if context["quiz_auth_pending"] and quiz_status in {
            "codigo_enviado",
            "cadastro_codigo_enviado",
            "codigo_invalido",
            "token_invalido",
        }:
            quiz_popup_state = "codigo"
        elif quiz_status in {
            "login_nao_encontrado",
            "login_campos",
            "erro_email",
            "erro_envio_email",
        }:
            quiz_popup_state = "login"
        elif quiz_status in {
            "cadastro_campos",
            "erro_usuario_email",
            "erro_usuario_duplicado",
            "erro_identidade_conflito",
            "erro_orcid_duplicado",
            "erro_orcid",
            "privacidade",
        }:
            quiz_popup_state = "cadastro"
        context["quiz_popup_state"] = quiz_popup_state
        context["quiz_popup_active_state"] = (
            quiz_popup_state if quiz_popup_state in {"login", "cadastro", "codigo"} else "login"
        )
        context["quiz_popup_open"] = quiz_popup_state != "closed"
        context["quiz_popup_error"] = quiz_status if quiz_popup_state != "closed" else ""
        context["quiz_oauth_pending"] = (
            (request.session.get("quiz_oauth_pending") or {})
            if str((request.session.get("quiz_oauth_pending") or {}).get("page_id") or "") == str(self.id)
            else {}
        )
        if quiz_usuario:
            quiz_historico_qs = quiz_usuario.quiz_sessoes.filter(pagina=self)
            context["quiz_historico_sessoes"] = list(quiz_historico_qs.order_by("-finalizado_em")[:12])
            quiz_historico_totais = quiz_historico_qs.aggregate(
                total_sessoes=Count("id"),
                total_corretas=Sum("corretas"),
                total_erradas=Sum("erradas"),
                total_puladas=Sum("puladas"),
                total_consideradas=Sum("consideradas"),
            )
            total_sessoes = int(quiz_historico_totais.get("total_sessoes") or 0)
            total_corretas = int(quiz_historico_totais.get("total_corretas") or 0)
            total_erradas = int(quiz_historico_totais.get("total_erradas") or 0)
            total_puladas = int(quiz_historico_totais.get("total_puladas") or 0)
            total_consideradas = int(quiz_historico_totais.get("total_consideradas") or 0)
            media_geral = int(round((total_corretas / total_consideradas) * 100)) if total_consideradas else 0
            pct_corretas = int(round((total_corretas / total_consideradas) * 100)) if total_consideradas else 0
            pct_erradas = int(round((total_erradas / total_consideradas) * 100)) if total_consideradas else 0
            pct_puladas = max(0, 100 - pct_corretas - pct_erradas) if total_consideradas else 0
            context["quiz_historico_resumo"] = {
                "total_sessoes": total_sessoes,
                "total_corretas": total_corretas,
                "total_erradas": total_erradas,
                "total_puladas": total_puladas,
                "total_consideradas": total_consideradas,
                "media_percentual": media_geral,
                "pct_corretas": pct_corretas,
                "pct_erradas": pct_erradas,
                "pct_puladas": pct_puladas,
                "pct_corretas_erradas": pct_corretas + pct_erradas,
            }
        else:
            context["quiz_historico_sessoes"] = []
            context["quiz_historico_resumo"] = {}
        return context

class MensagemContato(models.Model):
    STATUS_NOVO = "novo"
    STATUS_EM_ANDAMENTO = "em_andamento"
    STATUS_RESPONDIDO = "respondido"
    STATUS_ARQUIVADO = "arquivado"
    STATUS_CHOICES = [
        (STATUS_NOVO, "Novo"),
        (STATUS_EM_ANDAMENTO, "Em andamento"),
        (STATUS_RESPONDIDO, "Respondido"),
        (STATUS_ARQUIVADO, "Arquivado"),
    ]

    nome = models.CharField("Nome", max_length=255)
    email = models.EmailField("E-mail")
    mensagem = models.TextField("Mensagem")
    sinalizado_conteudo = models.BooleanField(
        "Sinalizado por conteúdo",
        default=False,
        help_text="Marcado automaticamente quando a mensagem contém padrões suspeitos.",
    )
    ip_origem = models.GenericIPAddressField("IP de origem", null=True, blank=True)
    user_agent = models.CharField("User agent", max_length=500, blank=True)
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NOVO,
        db_index=True,
    )
    atribuido_para = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Atribuído para",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mensagens_contato_atribuidas",
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)
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


class InteracaoMensagemContato(models.Model):
    TIPO_RESPOSTA = "resposta"
    TIPO_ENCAMINHAMENTO = "encaminhamento"
    TIPO_STATUS = "status"
    TIPO_ATRIBUICAO = "atribuicao"
    TIPO_CHOICES = [
        (TIPO_RESPOSTA, "Resposta"),
        (TIPO_ENCAMINHAMENTO, "Encaminhamento"),
        (TIPO_STATUS, "Alteração de status"),
        (TIPO_ATRIBUICAO, "Atribuição"),
    ]

    mensagem = models.ForeignKey(
        "conteudo.MensagemContato",
        verbose_name="Mensagem de contato",
        on_delete=models.CASCADE,
        related_name="interacoes",
    )
    tipo = models.CharField("Tipo", max_length=20, choices=TIPO_CHOICES, db_index=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Criado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    destinatario_email = models.EmailField("Destinatário", blank=True)
    assunto = models.CharField("Assunto", max_length=255, blank=True)
    corpo = models.TextField("Corpo", blank=True)
    sucesso_envio = models.BooleanField("Envio com sucesso", default=False)
    erro_envio = models.TextField("Erro de envio", blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Interação da mensagem de contato"
        verbose_name_plural = "Interações das mensagens de contato"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.mensagem.email}"


class EstatisticaTempoSite(models.Model):
    session_hash = models.CharField("Hash da sessão", max_length=64, db_index=True)
    path = models.CharField("Caminho", max_length=500, db_index=True)
    started_at = models.DateTimeField("Iniciado em", db_index=True)
    last_seen_at = models.DateTimeField("Último sinal em", db_index=True)
    duration_seconds = models.PositiveIntegerField("Duração em segundos", default=0)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Estatística de tempo no site"
        verbose_name_plural = "Estatísticas de tempo no site"
        indexes = [
            models.Index(
                fields=["started_at", "duration_seconds"],
                name="conteudo_es_started_80d23d_idx",
            ),
            models.Index(
                fields=["session_hash", "path"],
                name="conteudo_es_session_2246a1_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["session_hash", "path", "started_at"],
                name="unique_estatistica_tempo_site_sessao_pagina_inicio",
            )
        ]

    def __str__(self):
        return f"{self.path} - {self.duration_seconds}s"


class EstatisticaDiariaSite(models.Model):
    data = models.DateField("Data", db_index=True)
    path = models.CharField("Caminho", max_length=500, db_index=True)
    sessoes = models.PositiveIntegerField("Sessões", default=0)
    tempo_total_seconds = models.PositiveBigIntegerField("Tempo total em segundos", default=0)
    tempo_medio_seconds = models.PositiveIntegerField("Tempo médio em segundos", default=0)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Estatística diária do site"
        verbose_name_plural = "Estatísticas diárias do site"
        ordering = ["-data", "path"]
        constraints = [
            models.UniqueConstraint(
                fields=["data", "path"],
                name="unique_estatistica_diaria_site_data_path",
            )
        ]
        indexes = [
            models.Index(fields=["data", "path"], name="conteudo_ed_data_path_idx"),
        ]

    def __str__(self):
        return f"{self.data} - {self.path}"


class IpDinamicoIgnoradoEstatisticas(models.Model):
    nome = models.SlugField("Nome", max_length=80, default="rede-local", db_index=True)
    ip = models.GenericIPAddressField("IP público", db_index=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)
    expira_em = models.DateTimeField("Expira em", db_index=True)

    class Meta:
        verbose_name = "IP dinâmico ignorado nas estatísticas"
        verbose_name_plural = "IPs dinâmicos ignorados nas estatísticas"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome}: {self.ip}"


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

    def status_atual(self):
        return "Ativo" if self.ativo else "Inativo"
    status_atual.short_description = "Status"

    def ultimo_evento_tipo(self):
        evento = self.eventos.order_by("-criado_em").first()
        return evento.get_tipo_display() if evento else "-"
    ultimo_evento_tipo.short_description = "Último evento"

    def ultima_solicitacao_privacidade_tipo(self):
        solicitacao = SolicitacaoPrivacidadeNewsletter.objects.filter(
            email__iexact=self.email
        ).order_by("-criado_em").first()
        if not solicitacao:
            return "-"
        return f"{solicitacao.get_tipo_display()} ({solicitacao.get_status_display()})"
    ultima_solicitacao_privacidade_tipo.short_description = "Última solicitação"

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
        FieldPanel("inscrito", heading="Inscrito", read_only=True),
        FieldPanel("email", heading="E-mail", read_only=True),
        FieldPanel("tipo", heading="Tipo", read_only=True),
        FieldPanel("origem", heading="Origem", read_only=True),
        FieldPanel("detalhes", heading="Detalhes", read_only=True),
        FieldPanel("criado_em", heading="Criado em", read_only=True),
    ]

    class Meta:
        verbose_name = "Evento da newsletter"
        verbose_name_plural = "Eventos da newsletter"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.email} - {self.get_tipo_display()}"

    def tipo_legivel(self):
        return self.get_tipo_display()
    tipo_legivel.short_description = "Tipo"

    def detalhes_resumo(self):
        if not self.detalhes:
            return "-"
        texto = self.detalhes.strip()
        return texto[:120] + "..." if len(texto) > 120 else texto
    detalhes_resumo.short_description = "Detalhes"

class SolicitacaoPrivacidadeNewsletter(models.Model):
    TIPO_ACESSO = "acesso"
    TIPO_EXCLUSAO = "exclusao"

    TIPO_CHOICES = [
        (TIPO_ACESSO, "Solicitação de acesso aos dados"),
        (TIPO_EXCLUSAO, "Solicitação de exclusão dos dados"),
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
    observacoes = models.TextField("Observações", blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)
    atendida_em = models.DateTimeField("Atendida em", null=True, blank=True)
    arquivo_exportacao = models.FileField(
        "Arquivo de exportação",
        upload_to="privacidade_newsletter/",
        blank=True,
        null=True,
    )
    executada_em = models.DateTimeField("Executada em", null=True, blank=True)
    executar_apos_em = models.DateTimeField(
        "Executar após",
        null=True,
        blank=True,
    )

    confirmacao_usuario_exclusao = models.BooleanField(
        "Confirmação do usuário para exclusão",
        default=False,
    )
    confirmacao_usuario_em = models.DateTimeField(
        "Confirmação do usuário em",
        null=True,
        blank=True,
    )

    panels = [
        FieldPanel("email", heading="E-mail", read_only=True),
        FieldPanel("tipo", heading="Tipo", read_only=True),
        FieldPanel("status", heading="Status", read_only=True),
        FieldPanel("observacoes", heading="Observações", read_only=True),
        FieldPanel("atendida_em", heading="Atendida em", read_only=True),
        FieldPanel("executar_apos_em", heading="Executar após", read_only=True),
        FieldPanel("executada_em", heading="Executada em", read_only=True),
        FieldPanel(
            "confirmacao_usuario_exclusao",
            heading="Confirmação do usuário para exclusão",
            read_only=True,
        ),
        FieldPanel("confirmacao_usuario_em", heading="Confirmação do usuário em", read_only=True),
    ]

    class Meta:
        verbose_name = "Solicitação de privacidade da newsletter"
        verbose_name_plural = "Solicitações de privacidade da newsletter"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.email} - {self.get_tipo_display()}"

    def tipo_legivel(self):
        if self.tipo == self.TIPO_ACESSO:
            return "Solicitação de acesso aos dados"
        if self.tipo == self.TIPO_EXCLUSAO:
            return "Solicitação de exclusão dos dados"
        return self.tipo
    tipo_legivel.short_description = "Tipo"

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

        writer.writerow(["tipo", "campo_1", "campo_2", "campo_3", "campo_4", "campo_5", "campo_6", "campo_7"])
        for linha in coletar_linhas_privacidade_por_email(self.email):
            writer.writerow(linha)

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

            assunto = "Exportação dos seus dados da newsletter"
            corpo = (
                "O arquivo com os dados solicitados da newsletter segue em anexo.\n\n"
                "Este arquivo poderá ser removido do servidor depois de alguns dias.\n"
                "Se você precisar dele novamente no futuro, será necessário fazer uma nova solicitação.\n"
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

            executar_exclusao_privacidade_por_email(self.email)

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
            and (
                self.executar_apos_em is None
                or self.executar_apos_em <= timezone.now()
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

class InscritoNewsletterViewSet(SuperuserOnlySnippetViewSet):
    model = InscritoNewsletter
    icon = "mail"
    menu_label = "Inscritos na newsletter"
    menu_name = "inscritos-newsletter"
    list_display = [
        "email",
        "status_atual",
        "consentimento",
        "ultimo_evento_tipo",
        "ultima_solicitacao_privacidade_tipo",
        "confirmado_em",
        "origem",
        "criado_em",
    ]
    search_fields = ["email", "origem"]
    ordering = ["-criado_em"]


register_snippet(InscritoNewsletterViewSet)


class ConviteUsuarioViewSet(SuperuserOnlySnippetViewSet):
    model = ConviteUsuario
    icon = "mail"
    menu_label = "Convites de usuários"
    menu_name = "convites-usuarios"
    list_display = [
        "email",
        "resumo_papeis",
        "status",
        "enviado_em",
        "aceito_em",
        "expira_em",
        "criado_em",
    ]
    search_fields = ["email", "nome_completo", "username_sugerido", "token"]
    ordering = ["-criado_em"]

register_snippet(ConviteUsuarioViewSet)


class NewsletterEventoViewSet(SuperuserOnlySnippetViewSet):
    model = NewsletterEvento
    icon = "history"
    menu_label = "Eventos da newsletter"
    menu_name = "eventos-newsletter"
    list_display = [
        "inscrito",
        "email",
        "tipo_legivel",
        "origem",
        "detalhes_resumo",
        "criado_em",
    ]
    search_fields = ["email", "tipo", "origem", "detalhes"]
    ordering = ["-criado_em"]


register_snippet(NewsletterEventoViewSet)


class SolicitacaoPrivacidadeNewsletterViewSet(SuperuserOnlySnippetViewSet):
    model = SolicitacaoPrivacidadeNewsletter
    icon = "warning"
    menu_label = "Solicitações de privacidade"
    menu_name = "solicitacoes-privacidade-newsletter"

    list_display = [
        "email",
        "tipo_legivel",
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


class ComentarioPublicacaoViewSet(SuperuserOnlySnippetViewSet):
    model = ComentarioPublicacao
    icon = "comment"
    menu_label = "Comentários públicos"
    menu_name = "comentarios-publicos"
    list_display = [
        "publicacao",
        "usuario",
        "status",
        "sinalizado_conteudo",
        "criado_em",
    ]
    list_filter = ["status", "sinalizado_conteudo", "criado_em"]
    search_fields = [
        "publicacao__title",
        "usuario__username",
        "usuario__email",
        "texto",
    ]
    ordering = ["-criado_em"]


register_snippet(ComentarioPublicacaoViewSet)


class DuvidaQuizPublicacaoViewSet(SuperuserOnlySnippetViewSet):
    model = DuvidaQuizPublicacao
    icon = "help"
    menu_label = "Dúvidas do quiz"
    menu_name = "duvidas-quiz-publicacao"
    list_display = [
        "publicacao",
        "pergunta_relacionada_texto",
        "usuario",
        "status",
        "permitir_publicacao_comentarios",
        "respondido_em",
        "criado_em",
    ]
    list_filter = ["status", "permitir_publicacao_comentarios", "respondido_em", "criado_em"]
    search_fields = [
        "publicacao__title",
        "pergunta_catalogo__pergunta",
        "usuario__username",
        "usuario__email",
        "mensagem",
        "resposta",
    ]
    ordering = ["-criado_em"]


register_snippet(DuvidaQuizPublicacaoViewSet)


class IdentidadeExternaComentarioViewSet(SuperuserOnlySnippetViewSet):
    model = IdentidadeExternaComentario
    icon = "user"
    menu_label = "Identidades externas"
    menu_name = "identidades-externas-comentario"
    list_display = [
        "usuario",
        "provider",
        "provider_username",
        "email_externo",
        "email_verificado",
        "atualizado_em",
    ]
    list_filter = ["provider", "email_verificado", "atualizado_em"]
    search_fields = [
        "usuario__username",
        "usuario__email",
        "provider_user_id",
        "provider_username",
        "email_externo",
    ]
    ordering = ["-atualizado_em"]


register_snippet(IdentidadeExternaComentarioViewSet)


class LinkCurtoShlinkViewSet(SuperuserOnlySnippetViewSet):
    model = LinkCurtoShlink
    icon = "link"
    menu_label = "Links curtos"
    menu_name = "links-curtos-shlink"
    list_display = [
        "publicacao",
        "contexto",
        "canal",
        "short_url",
        "visits_total",
        "ultimo_sync_em",
    ]
    list_filter = ["contexto", "canal", "ultimo_sync_em", "criado_em"]
    search_fields = [
        "publicacao__title",
        "titulo",
        "long_url",
        "short_url",
        "short_code",
        "dominio",
    ]
    ordering = ["-atualizado_em"]


register_snippet(LinkCurtoShlinkViewSet)

class RegistroIndexador(ClusterableModel):
    titulo = models.CharField("Título da obra", max_length=500)
    slug = models.SlugField("Slug", max_length=255, unique=True, blank=True)
    ano_publicacao = models.CharField("Ano de publicação", max_length=20, blank=True)
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

class RegistroIndexadorViewSet(SuperuserOnlySnippetViewSet):
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

class ContatoPage(TraducaoConteudoMixin, Page):
    introducao = RichTextField("Introdução", blank=True)
    email_destino = models.EmailField("E-mail de destino", blank=True)
    mensagem_sucesso = models.CharField(
        "Mensagem de sucesso",
        max_length=255,
        default="Mensagem enviada com sucesso.",
    )

    translatable_fields = (
        "title",
        "seo_title",
        "search_description",
        "introducao",
        "mensagem_sucesso",
    )
    richtext_translation_fields = ("introducao",)

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        FieldPanel("introducao"),
        FieldPanel("email_destino"),
        FieldPanel("mensagem_sucesso"),
    ]
    promote_panels = PROMOTE_PANELS_SEM_MENU_SITE

    class Meta:
        verbose_name = "Página de contato"
        verbose_name_plural = "Páginas de contato"

class IndexadorPage(TraducaoConteudoMixin, Page):
    introducao = RichTextField("Introdução", blank=True)
    mensagem_sem_resultados = models.CharField(
        "Mensagem sem resultados",
        max_length=255,
        default="Nenhum registro encontrado.",
    )
    itens_por_pagina = models.PositiveIntegerField("Itens por página", default=10)

    translatable_fields = (
        "title",
        "seo_title",
        "search_description",
        "introducao",
        "mensagem_sem_resultados",
    )
    richtext_translation_fields = ("introducao",)

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        FieldPanel("introducao"),
        FieldPanel("mensagem_sem_resultados"),
        FieldPanel("itens_por_pagina"),
    ]
    promote_panels = PROMOTE_PANELS_SEM_MENU_SITE

    class Meta:
        verbose_name = "Página do indexador"
        verbose_name_plural = "Páginas do indexador"

    def get_context(self, request):
        context = super().get_context(request)
        from .views import _extrair_termos_busca_avancada, _normalizar_ano_filtro, filtrar_registros_indexador

        termo = request.GET.get("q", "").strip()
        ano_inicial = _normalizar_ano_filtro(request.GET.get("ano_inicial", ""))
        ano_final = _normalizar_ano_filtro(request.GET.get("ano_final", ""))
        ordenar = request.GET.get("ordenar", "recentes").strip()
        idioma_busca = (getattr(request, "LANGUAGE_CODE", "") or "pt-br").strip().lower()
        termos_avancados = _extrair_termos_busca_avancada(request)
        termos_configurados = [item for item in termos_avancados if item["termo"]]
        busca_avancada_ativa = bool(termos_configurados)
        if not busca_avancada_ativa and termo:
            termos_configurados = [{"indice": 1, "termo": termo, "operador": "and"}]

        registros = filtrar_registros_indexador(
            termo=termo,
            ano_inicial=ano_inicial,
            ano_final=ano_final,
            ordenar=ordenar,
            idioma_busca=idioma_busca,
            termos_configurados=termos_configurados,
        )

        paginator = Paginator(registros, self.itens_por_pagina or 10)
        pagina_numero = request.GET.get("pagina")
        pagina_obj = paginator.get_page(pagina_numero)
        filtros_query = request.GET.copy()
        filtros_query.pop("pagina", None)
        filtros_query.pop("idioma", None)
        anos_sugeridos = sorted(
            {
                ano.strip()
                for ano in RegistroIndexador.objects.filter(ativo=True)
                .values_list("ano_publicacao", flat=True)
                if re.fullmatch(r"\d{4}", (ano or "").strip())
            },
            reverse=True,
        )

        context["termo_busca"] = termo
        context["ano_inicial"] = ano_inicial
        context["ano_final"] = ano_final
        context["ordenacao_atual"] = ordenar
        context["termos_avancados"] = termos_avancados
        context["busca_avancada_ativa"] = busca_avancada_ativa
        context["pagina_obj"] = pagina_obj
        context["registros"] = pagina_obj.object_list
        context["anos_sugeridos"] = anos_sugeridos
        context["filtros_paginacao_querystring"] = filtros_query.urlencode()
        context["filtros_exportacao_querystring"] = filtros_query.urlencode()

        return context

class NewsletterPage(TraducaoConteudoMixin, Page):
    introducao = RichTextField("Introdução", blank=True)
    mensagem_sucesso = models.CharField(
        "Mensagem de sucesso",
        max_length=255,
        default="Inscricao realizada com sucesso.",
    )

    translatable_fields = (
        "title",
        "seo_title",
        "search_description",
        "introducao",
        "mensagem_sucesso",
    )
    richtext_translation_fields = ("introducao",)

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        FieldPanel("introducao"),
        FieldPanel("mensagem_sucesso"),
    ]
    promote_panels = PROMOTE_PANELS_SEM_MENU_SITE

    class Meta:
        verbose_name = "Página de newsletter"
        verbose_name_plural = "Páginas de newsletter"
