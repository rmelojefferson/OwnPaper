import csv
import hashlib
import io
import json
import logging
import os
import re
import secrets
import shutil
import socket
import struct
import subprocess
import tempfile
import unicodedata
import urllib.parse
import uuid
from datetime import timedelta
from pathlib import Path

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import NoReverseMatch, path, reverse
from django.utils.html import escape, strip_tags
from django.utils.html import format_html
from django.utils.html import format_html_join
from django.utils.text import slugify
from django.utils import timezone
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from wagtail import hooks
from wagtail.actions.publish_page_revision import PublishPageRevisionAction
from wagtail.admin.menu import Menu, MenuItem, SubmenuMenuItem
from wagtail.admin.rich_text import DraftailRichTextArea
from wagtail.admin.search import SearchArea
from wagtail.documents import get_document_model
from wagtail.images import get_image_model
from wagtail.models import Collection, Page, Site
from PIL import Image as PILImage, ImageOps, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter

from conteudo.audit import registrar_auditoria
from conteudo.access import (
    can_access_admin_basic,
    can_access_contact,
    can_access_publications,
    can_manage_site_settings,
    can_publish_direct,
    eligible_contact_assignees,
    get_panel_profile,
    is_admin,
    is_author,
    is_operator,
    is_reviewer,
)
from conteudo.backup_ops import (
    BACKUP_SCOPE_CHOICES,
    _backup_backend_config,
    criar_solicitacao_backup_painel,
    gerar_token_download_backup,
    label_escopo_backup,
)
from conteudo.health import avaliar_saude_operacional
from conteudo.account_security import (
    BackupCodesAccountForm,
    total_backup_codes as total_backup_codes_usuario,
    usuario_tem_totp,
    validar_token_2fa_conta,
)
from conteudo.email_ops import (
    destinatarios_por_segmento,
    enviar_publicacoes_imediata,
    enviar_publicacoes_periodicas,
    executar_disparo,
)
from conteudo.html_safety import sanitize_email_html
from conteudo.user_roles import aplicar_papeis_usuario
from conteudo.views import _normalizar_data_busca
from home.models import HomePage
from conteudo.models import (
    AuditLog,
    Autor,
    BackupExecucao,
    Categoria,
    ComentarioPublicacao,
    ConfiguracaoSite,
    ConviteUsuario,
    DisparoEmailClique,
    DisparoEmail,
    DisparoEmailDestino,
    EstatisticaDiariaSite,
    EstatisticaTempoSite,
    InteracaoMensagemContato,
    ImagemPublicacao,
    MensagemContato,
    MidiaPendente,
    NewsletterEvento,
    InscritoNewsletter,
    PerguntaQuizCatalogo,
    PublicacaoComentarioRevisao,
    PublicacaoPage,
    PublicacaoRevisao,
    PublicacaoPageAutor,
    PublicacoesIndexPage,
    RodapeLink,
    RegistroIndexador,
    RegistroIndexadorAutor,
    SolicitacaoPrivacidadeNewsletter,
    TagPublicacao,
    TemplateEmailCampanha,
    UsuarioPainelPerfil,
    SolicitacaoMudancaAdmin,
    SubmissaoPublica,
    UsuarioComentario,
    normalizar_username_publico,
)

logger = logging.getLogger(__name__)
EMAIL_EDITOR_FEATURES = ["h2", "h3", "bold", "italic", "link", "ol", "ul", "hr"]
CONFIG_SITE_SECTION_DEFS = [
    {
        "slug": "identidade-seo",
        "titulo": "Identidade e SEO",
        "eyebrow": "Identidade",
        "descricao": "Nome do projeto, SEO padrão, imagem de compartilhamento, favicon e rodapé institucional.",
        "topicos": [
            "Nome público do projeto e e-mail institucional exibido no site.",
            "Título e descrição usados por buscadores e compartilhamentos.",
            "Imagem padrão de compartilhamento, favicon e textos institucionais do rodapé.",
        ],
        "campos": [
            "nome_site",
            "seo_title_padrao",
            "descricao_padrao",
            "imagem_compartilhamento_padrao",
            "favicon",
            "email_contato",
            "copyright_texto",
            "texto_rodape",
            "texto_rodape_link",
        ],
    },
    {
        "slug": "paginas-institucionais",
        "titulo": "Páginas institucionais",
        "eyebrow": "Estrutura",
        "descricao": "Páginas base do site público e rótulos de acesso para indexador e quiz.",
        "topicos": [
            "Vincula as páginas públicas usadas por atalhos e formulários.",
            "Define os rótulos públicos do indexador e da área de quiz.",
            "Mantém a instalação em modo de site único, sem expor gestão de múltiplos sites.",
        ],
        "campos": [
            "pagina_sobre",
            "pagina_privacidade",
            "pagina_cookies",
            "pagina_contato",
            "pagina_newsletter",
            "pagina_indexador",
            "rotulo_indexador",
            "pagina_quiz_estudo",
            "rotulo_quiz_estudo",
        ],
    },
    {
        "slug": "menu-navegacao",
        "titulo": "Menu e navegação",
        "eyebrow": "Navegação",
        "descricao": "Comportamento do botão home, logos claro/escuro e parâmetros visuais do cabeçalho.",
        "topicos": [
            "Controla se o menu usa a navegação customizada do OwnPaper.",
            "Define o comportamento do botão de home e os logos usados no cabeçalho.",
            "Ajusta proporção e altura dos logos para desktop e celular.",
        ],
        "campos": [
            "usar_menu_customizado",
            "menu_home_exibir",
            "menu_home_primeiro_fixo",
            "menu_home_rotulo",
            "menu_home_imagem",
            "menu_home_imagem_claro",
            "menu_home_imagem_escuro",
            "menu_home_imagem_mobile_claro",
            "menu_home_imagem_mobile_escuro",
            "menu_home_logo_proporcao",
            "menu_home_logo_ajuste",
            "menu_home_logo_altura_desktop_px",
            "menu_home_logo_altura_mobile_px",
            "menu_padrao_categorias_ativo",
            "menu_padrao_categorias_rotulo",
            "menu_padrao_autores_ativo",
            "menu_padrao_autores_rotulo",
            "menu_padrao_tags_ativo",
            "menu_padrao_tags_rotulo",
            "menu_padrao_busca_ativo",
            "menu_padrao_busca_rotulo",
            "menu_padrao_destaques_ativo",
            "menu_padrao_destaques_rotulo",
            "menu_padrao_ultimas_ativo",
            "menu_padrao_ultimas_rotulo",
            "menu_padrao_contato_ativo",
            "menu_padrao_contato_rotulo",
            "menu_padrao_sobre_ativo",
            "menu_padrao_sobre_rotulo",
            "menu_padrao_newsletter_ativo",
            "menu_padrao_newsletter_rotulo",
            "menu_padrao_indexador_ativo",
            "menu_padrao_indexador_rotulo",
            "menu_padrao_quiz_ativo",
            "menu_padrao_quiz_rotulo",
            "menu_padrao_apoio_ativo",
            "menu_padrao_apoio_rotulo",
            "menu_padrao_privacidade_ativo",
            "menu_padrao_privacidade_rotulo",
            "menu_padrao_cookies_ativo",
            "menu_padrao_cookies_rotulo",
            "menu_padrao_rss_ativo",
            "menu_padrao_rss_rotulo",
            "rodape_padrao_contato_ativo",
            "rodape_padrao_contato_rotulo",
            "rodape_padrao_sobre_ativo",
            "rodape_padrao_sobre_rotulo",
            "rodape_padrao_privacidade_ativo",
            "rodape_padrao_privacidade_rotulo",
            "rodape_padrao_cookies_ativo",
            "rodape_padrao_cookies_rotulo",
            "rodape_padrao_newsletter_ativo",
            "rodape_padrao_newsletter_rotulo",
            "rodape_padrao_indexador_ativo",
            "rodape_padrao_indexador_rotulo",
            "rodape_padrao_quiz_ativo",
            "rodape_padrao_quiz_rotulo",
        ],
        "links_extras": [
            {"label": "Abrir Menu e rodapé", "url_name": "admin_navegacao"},
        ],
        "observacoes": [
            "Para o botão da home, prefira imagem horizontal com fundo transparente.",
            "Os campos mobile claro/escuro têm prioridade no celular; se ficarem vazios, o site usa as imagens do desktop automaticamente.",
        ],
    },
    {
        "slug": "tema-aparencia",
        "titulo": "Tema e aparência",
        "eyebrow": "Aparência",
        "descricao": "Idioma do site, tema padrão, paleta principal e links sociais públicos.",
        "topicos": [
            "Define o idioma base e o tema padrão do site público.",
            "Controla as duas cores centrais usadas pelo tema.",
            "Centraliza links sociais exibidos no site.",
        ],
        "campos": [
            "idioma_site",
            "tema_padrao_site",
            "paleta_cor_1",
            "paleta_cor_2",
            "social_facebook_url",
            "social_instagram_url",
            "social_linkedin_url",
            "social_x_url",
            "social_youtube_url",
        ],
    },
    {
        "slug": "integracoes-rastreamento",
        "titulo": "Integrações e rastreamento",
        "eyebrow": "Integrações",
        "descricao": "Verificações externas, analytics, pixel e parâmetros locais de links curtos.",
        "topicos": [
            "Configura verificações de domínio e ferramentas de analytics permitidas.",
            "Controla estatísticas internas, retenção de agregados e eventos brutos.",
            "Habilita parâmetros públicos de links curtos sem expor chaves sensíveis no painel.",
        ],
        "campos": [
            "google_search_console_verification",
            "meta_domain_verification",
            "verificacao_head_html",
            "verificacao_arquivo_nome",
            "verificacao_arquivo_conteudo",
            "google_analytics_id",
            "google_tag_manager_id",
            "meta_pixel_id",
            "plausible_domain",
            "plausible_script_url",
            "plausible_script_direto_ativo",
            "plausible_sem_consentimento_ativo",
            "umami_website_id",
            "umami_script_url",
            "matomo_site_id",
            "matomo_url",
            "estatisticas_internas_ativas",
            "estatisticas_reter_agregados_dias",
            "estatisticas_reter_eventos_brutos_dias",
            "shlink_ativo",
            "shlink_default_domain",
        ],
        "observacoes": [
            "As integrações de analytics usam campos estruturados; não há campo de script livre para reduzir risco de script malicioso.",
            "As credenciais de Shlink e OAuth permanecem no ambiente do servidor, não neste formulário.",
            "Recomendação padrão: agregados internos por 12 meses e eventos brutos por até 3 meses.",
        ],
    },
    {
        "slug": "comunicacao-comentarios",
        "titulo": "Comunicação e comentários",
        "eyebrow": "Comunicação",
        "descricao": "Comentários públicos e notificações de novas publicações por e-mail.",
        "topicos": [
            "Liga ou desliga comentários públicos e integração com newsletter.",
            "Define o modo de notificação de novas publicações por e-mail.",
            "Controla submissões públicas e exigência de ORCID.",
        ],
        "campos": [
            "comentarios_ativos",
            "comentarios_auto_newsletter",
            "notificacao_publicacoes_modo",
            "notificacao_publicacoes_periodo_horas",
            "submissoes_publicas_ativas",
            "submissoes_exigir_orcid",
            "submissoes_limite_pdf_mb",
        ],
        "readonly_campos": [
            "notificacao_publicacoes_ultimo_envio_em",
        ],
        "links_extras": [
            {"label": "Abrir e-mails de publicações", "url_name": "admin_email_publicacoes"},
        ],
    },
    {
        "slug": "apoios-doacoes",
        "titulo": "Apoios e doações",
        "eyebrow": "Apoio",
        "descricao": "Controle central da página de apoio e dos pontos de entrada de doação no site público.",
        "topicos": [
            "Liga ou desliga a área pública de apoio/doação.",
            "Define se chamadas aparecem no rodapé e no final das publicações.",
            "Centraliza texto, chave Pix e link externo de apoio.",
        ],
        "campos": [
            "doacoes_ativas",
            "doacoes_exibir_no_cabecalho",
            "doacoes_exibir_no_rodape",
            "doacoes_exibir_em_publicacoes",
            "doacoes_rotulo",
            "doacoes_titulo",
            "doacoes_descricao",
            "doacoes_pix_ativo",
            "doacoes_pix_chave",
            "doacoes_pix_qr_code",
            "doacoes_pix_copia_cola",
            "doacoes_apoiase_ativo",
            "doacoes_apoiase_url",
            "doacoes_buymeacoffee_ativo",
            "doacoes_buymeacoffee_usuario",
            "doacoes_paypal_ativo",
            "doacoes_paypal_hosted_button_id",
            "doacoes_paypal_business",
            "doacoes_paypal_url",
            "doacoes_mercadopago_ativo",
            "doacoes_mercadopago_url",
            "doacoes_github_sponsors_ativo",
            "doacoes_github_sponsors_usuario",
            "doacoes_bitcoin_ativo",
            "doacoes_bitcoin_endereco",
            "doacoes_ethereum_ativo",
            "doacoes_ethereum_endereco",
            "doacoes_link_externo",
            "doacoes_detalhes",
        ],
        "observacoes": [
            "O painel não aceita scripts livres de plataformas de pagamento; use apenas identificadores, URLs públicas ou endereços.",
            "PayPal pode usar hosted_button_id, business ou URL alternativa. Mercado Pago deve usar um link público de pagamento/checkout já criado.",
            "Métodos regulados como Pix, PayPal e Mercado Pago identificam as partes conforme regras do provedor. Para maior privacidade, use carteiras cripto informadas pelo próprio projeto.",
        ],
    },
    {
        "slug": "operacao-site",
        "titulo": "Operação do site",
        "eyebrow": "Operação",
        "descricao": "Manutenção, proteção editorial por ORCID e relatório administrativo de backup.",
        "topicos": [
            "Controla modo de manutenção e mensagem exibida ao público.",
            "Define proteção editorial relacionada a ORCID.",
            "Configura apenas o relatório administrativo de backup por e-mail; arquivos de backup seguem a política operacional.",
        ],
        "campos": [
            "modo_manutencao_ativo",
            "modo_manutencao_titulo",
            "modo_manutencao_mensagem",
            "travar_publicacao_por_orcid",
            "backup_email_destino",
            "backup_enviar_relatorio",
        ],
        "readonly_campos": [
            "backup_ultimo_envio_em",
        ],
        "links_extras": [
            {"label": "Abrir Backups", "url_name": "admin_backups"},
        ],
    },
]


class ContatoRespostaForm(forms.Form):
    assunto_resposta = forms.CharField(label="Assunto", max_length=255)
    corpo_resposta = forms.CharField(
        label="Corpo",
        widget=DraftailRichTextArea(features=EMAIL_EDITOR_FEATURES),
        required=True,
    )

    def clean_corpo_resposta(self):
        valor = sanitize_email_html(self.cleaned_data["corpo_resposta"])
        if not strip_tags(valor or "").strip():
            raise forms.ValidationError("Escreva o conteúdo da resposta.")
        return valor


class ContatoEncaminhamentoForm(forms.Form):
    email_encaminhar = forms.EmailField(label="E-mail de destino")
    assunto_encaminhamento = forms.CharField(label="Assunto", max_length=255)
    corpo_encaminhamento = forms.CharField(
        label="Mensagem complementar",
        widget=DraftailRichTextArea(features=EMAIL_EDITOR_FEATURES),
        required=False,
    )
    incluir_ultima_resposta = forms.BooleanField(
        label="Incluir a última resposta enviada",
        required=False,
    )

    def __init__(self, *args, panel_email_suggestions=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.panel_email_suggestions = [
            (email or "").strip().lower()
            for email in (panel_email_suggestions or [])
            if (email or "").strip()
        ]
        self.fields["email_encaminhar"].widget.attrs["list"] = "admin-contato-panel-emails"

    def clean_corpo_encaminhamento(self):
        return sanitize_email_html(self.cleaned_data.get("corpo_encaminhamento") or "")


def _config_site_section_map():
    return {item["slug"]: item for item in CONFIG_SITE_SECTION_DEFS}


def _widget_attrs_config_site(nome_campo, campo):
    classes = ["op-admin-input"]
    widget = campo.widget
    if isinstance(widget, forms.Textarea):
        classes.append("op-admin-textarea")
        attrs = {"rows": 4}
    elif isinstance(widget, forms.CheckboxInput):
        classes.append("op-admin-checkbox")
        attrs = {}
    elif isinstance(widget, forms.Select):
        classes.append("op-admin-select")
        attrs = {}
    else:
        classes.append("op-admin-control")
        attrs = {}
    if nome_campo in {"paleta_cor_1", "paleta_cor_2"}:
        attrs["type"] = "color"
    attrs["class"] = " ".join(classes)
    return attrs


def _criar_form_configuracao_site(section_def):
    class ConfiguracaoSiteSectionForm(forms.ModelForm):
        class Meta:
            model = ConfiguracaoSite
            fields = section_def["campos"]

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for nome, campo in self.fields.items():
                campo.widget.attrs.update(_widget_attrs_config_site(nome, campo))
                if nome == "descricao_padrao":
                    campo.label = "Descrição padrão (SEO e compartilhamento)"
                    campo.help_text = (
                        "Texto usado como descrição institucional quando a página "
                        "não tiver descrição própria."
                    )
                elif nome == "email_contato":
                    campo.label = "E-mail institucional público"
                    campo.help_text = (
                        "E-mail exibido em áreas públicas e usado como contato institucional. "
                        "O destino das mensagens do formulário de contato é configurado "
                        "na página Contato."
                    )
                elif nome in {
                    "usar_menu_customizado",
                    "menu_home_exibir",
                    "menu_home_primeiro_fixo",
                } or (nome.startswith("menu_padrao_") and nome.endswith("_ativo")):
                    classes = campo.widget.attrs.get("class", "")
                    campo.widget.attrs["class"] = f"{classes} op-admin-menu-toggle-input".strip()

    return ConfiguracaoSiteSectionForm


def _configuracao_site_admin(request):
    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    if not site:
        return None
    return ConfiguracaoSite.for_site(site)


def _url_absoluta_admin(request, url):
    if not url:
        return ""
    return request.build_absolute_uri(url)


def _logo_assinatura_email_url(request, config):
    if not config:
        return ""

    for field_name, rendition_spec in [
        ("menu_home_imagem_claro", "max-220x72"),
        ("menu_home_imagem", "max-220x72"),
        ("menu_home_imagem_escuro", "max-220x72"),
        ("favicon", "fill-72x72"),
    ]:
        image = getattr(config, field_name, None)
        if not image:
            continue
        try:
            rendition = image.get_rendition(rendition_spec)
            return _url_absoluta_admin(request, rendition.url)
        except Exception:
            try:
                return _url_absoluta_admin(request, image.file.url)
            except Exception:
                continue
    return ""


def _avatar_assinatura_email_url(request, autor):
    if not autor or not autor.foto_id:
        return ""
    try:
        rendition = autor.foto.get_rendition("fill-80x80")
        return _url_absoluta_admin(request, rendition.url)
    except Exception:
        try:
            return _url_absoluta_admin(request, autor.foto.file.url)
        except Exception:
            return ""


def _nome_assinatura_email(user, autor=None):
    if autor and (autor.nome_completo or autor.nome_exibicao):
        return (autor.nome_completo or autor.nome_exibicao).strip()
    if (user.first_name or "").strip():
        return user.first_name.strip()
    full_name = (user.get_full_name() or "").strip()
    if full_name:
        return full_name
    return (user.username or "").strip()


def _nome_site_assinatura_email(request, config):
    if config and (config.nome_site or "").strip():
        return config.nome_site.strip()
    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    if site and (site.site_name or "").strip():
        return site.site_name.strip()
    return site.hostname if site else ""


def _assinatura_email_html_para_usuario(request, user):
    config = _configuracao_site_admin(request)
    autor = _autor_vinculado_do_usuario(user)
    nome_resposta = _nome_assinatura_email(user, autor)
    nome_site = _nome_site_assinatura_email(request, config)
    avatar_url = _avatar_assinatura_email_url(request, autor)
    logo_url = _logo_assinatura_email_url(request, config)

    media_html = ""
    if avatar_url:
        media_html = format_html(
            '<img src="{}" alt="{}" width="64" height="64" '
            'style="display:block;width:64px;height:64px;border-radius:50%;object-fit:cover;border:0;">',
            avatar_url,
            nome_resposta,
        )
    elif logo_url:
        media_html = format_html(
            '<img src="{}" alt="{}" height="48" '
            'style="display:block;max-width:180px;max-height:48px;width:auto;height:48px;border:0;">',
            logo_url,
            nome_site or nome_resposta,
        )

    return format_html(
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'style="margin:0;border-collapse:collapse;">'
        '<tr>'
        '<td style="padding:0 16px 0 0;vertical-align:middle;{}">{}</td>'
        '<td style="vertical-align:middle;">'
        '<p style="margin:0;font-size:16px;line-height:1.35;font-weight:700;color:#1f2d3d;">{}</p>'
        '<p style="margin:4px 0 0;font-size:13px;line-height:1.4;color:#5f7280;">{}</p>'
        '</td>'
        '</tr>'
        '</table>',
        "width:80px;" if media_html else "display:none;",
        media_html,
        nome_resposta,
        nome_site,
    )


def _corpo_inicial_email_com_assinatura(request, user):
    return ""


def _anexar_assinatura_email_html(request, user, corpo_html):
    assinatura = _assinatura_email_html_para_usuario(request, user)
    if not assinatura:
        return corpo_html or ""
    corpo_limpo = (corpo_html or "").strip()
    if corpo_limpo:
        return format_html("{}<hr><div>{}</div>", corpo_limpo, assinatura)
    return format_html("<div>{}</div>", assinatura)


def _sanitizar_corpo_email_admin(valor):
    return sanitize_email_html((valor or "").strip())


def _ultima_resposta_sucesso_contato(mensagem):
    return (
        mensagem.interacoes.filter(
            tipo=InteracaoMensagemContato.TIPO_RESPOSTA,
            sucesso_envio=True,
        )
        .order_by("-criado_em")
        .first()
    )


def _enviar_monitoramento_resposta_contato(request, mensagem, resposta_html):
    perfil = get_panel_profile(request.user)
    if not perfil or not (perfil.email_monitoramento_respostas or "").strip():
        return

    destino = perfil.email_monitoramento_respostas.strip().lower()
    assunto = f"[Monitoramento resposta] {mensagem.nome} - {mensagem.email}"
    corpo = (
        f"<p><strong>Respondido por:</strong> {escape(request.user.username)}</p>"
        f"<p><strong>Contato original:</strong> {escape(mensagem.nome)} ({escape(mensagem.email)})</p>"
        f"<p><strong>Mensagem original:</strong><br>{escape(mensagem.mensagem).replace(chr(10), '<br>')}</p>"
        f"<hr><div>{resposta_html}</div>"
    )
    email_msg = EmailMessage(
        subject=assunto,
        body=corpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[destino],
    )
    email_msg.content_subtype = "html"
    email_msg.send(fail_silently=True)


def _negar_acesso_admin(request, mensagem="Você não tem permissão para acessar esta área."):
    if request.user.is_authenticated:
        messages.error(request, mensagem)
    return redirect("/admin/")


def _pode_acessar_admin_basico(user):
    return can_access_admin_basic(user)


def _pode_acessar_admin_superuser(user):
    return is_admin(user)


def _pode_acessar_admin_publicacoes(user):
    return can_access_publications(user)


def _pode_acessar_admin_contato(user):
    return can_access_contact(user)


def _admin_reverse(nome, *args, fallback=""):
    try:
        return reverse(nome, args=args)
    except NoReverseMatch:
        return fallback


def _admin_choice_label(model, field_name, value):
    if value in (None, ""):
        return ""
    try:
        choices = dict(model._meta.get_field(field_name).choices or [])
    except Exception:
        choices = {}
    return choices.get(value, str(value))


def _admin_data_resultado(valor):
    if not valor:
        return ""
    if hasattr(valor, "date"):
        valor = timezone.localtime(valor).date() if timezone.is_aware(valor) else valor.date()
    return valor.strftime("%d/%m/%Y") if hasattr(valor, "strftime") else str(valor)


def _admin_filtrar_periodo(queryset, campo, data_de, data_ate):
    if data_de:
        queryset = queryset.filter(**{f"{campo}__gte": data_de})
    if data_ate:
        queryset = queryset.filter(**{f"{campo}__lte": data_ate})
    return queryset


def _admin_busca_adicionar_resultado(resultados, *, tipo, titulo, url, descricao="", status="", data="", contexto=""):
    resultados.append({
        "tipo": tipo,
        "titulo": titulo,
        "url": url,
        "descricao": strip_tags(descricao or "")[:240],
        "status": status,
        "data": _admin_data_resultado(data),
        "contexto": contexto,
    })


def admin_busca_global_view(request):
    if not _pode_acessar_admin_basico(request.user):
        return _negar_acesso_admin(request)

    query = (request.GET.get("q") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()
    status = (request.GET.get("status") or "").strip()
    meus_itens = request.GET.get("meus") == "1"
    ordenar = (request.GET.get("ordenar") or "relevancia").strip()
    data_de_raw = (request.GET.get("data_de") or "").strip()
    data_ate_raw = (request.GET.get("data_ate") or "").strip()
    data_de, data_de_exibicao = _normalizar_data_busca(data_de_raw, "pt-br")
    data_ate, data_ate_exibicao = _normalizar_data_busca(data_ate_raw, "pt-br")
    tem_filtro = any([query, tipo, status, data_de_raw, data_ate_raw, meus_itens])
    resultados = []
    limite_por_tipo = 40
    status_tipos = {
        "publicado": {"publicacao"},
        "rascunho": {"publicacao"},
        "em_revisao": {"publicacao"},
        "ajustes_solicitados": {"publicacao"},
        "rejeitado": {"publicacao", "pergunta", "categoria", "tag", "comentario"},
        "agendado": {"publicacao"},
        "pendente": {"pergunta", "categoria", "tag", "comentario"},
        "aprovado": {"pergunta", "categoria", "tag", "comentario"},
        "novo": {"mensagem"},
        "em_andamento": {"mensagem"},
        "respondido": {"mensagem"},
        "arquivado": {"mensagem"},
        "ativa": {"pergunta"},
        "inativa": {"pergunta"},
        "ativo": {"usuario"},
        "inativo": {"usuario"},
    }
    if tipo and status and tipo not in status_tipos.get(status, set()):
        status = ""

    def deve_buscar(nome_tipo):
        if not tem_filtro:
            return False
        if tipo:
            return tipo == nome_tipo
        if status:
            return nome_tipo in status_tipos.get(status, set())
        return True

    if deve_buscar("publicacao") and _pode_acessar_admin_publicacoes(request.user):
        qs = PublicacaoPage.objects.select_related("categoria_principal").prefetch_related("autores_publicacao__autor")
        if not is_admin(request.user):
            filtro_permissao = Q()
            if is_author(request.user):
                filtro_permissao |= Q(autores_publicacao__autor__usuario_admin=request.user)
            if is_reviewer(request.user):
                filtro_permissao |= Q(status_editorial=PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO) | Q(revisoes__revisor=request.user)
            qs = qs.filter(filtro_permissao).distinct()
        if query:
            filtro_busca = (
                Q(title__icontains=query)
                | Q(resumo__icontains=query)
                | Q(corpo__icontains=query)
                | Q(palavras_chave__icontains=query)
                | Q(autores_publicacao__autor__nome_completo__icontains=query)
                | Q(autores_publicacao__autor__nome_exibicao__icontains=query)
                | Q(autores_publicacao__autor__username__icontains=query)
            )
            if query.isdigit():
                filtro_busca |= Q(id=int(query))
            qs = qs.filter(filtro_busca).distinct()
        if status:
            status_publicacao = _normalizar_status_publicacao_admin(status)
            if status_publicacao:
                qs = qs.filter(status_editorial=status_publicacao)
        if meus_itens:
            qs = qs.filter(
                Q(publicado_por=request.user)
                | Q(revisao_solicitada_por=request.user)
                | Q(autores_publicacao__autor__usuario_admin=request.user)
            ).distinct()
        qs = _admin_filtrar_periodo(qs, "data_publicacao", data_de, data_ate)
        qs = qs.order_by("title" if ordenar == "titulo" else "-data_publicacao", "-latest_revision_created_at")[:limite_por_tipo]
        for item in qs:
            autores = ", ".join(str(v.autor) for v in item.autores_publicacao.all()[:3] if v.autor)
            _admin_busca_adicionar_resultado(
                resultados,
                tipo="Publicação",
                titulo=item.title,
                url=(
                    f"/admin/pages/{item.id}/edit/"
                    if _usuario_pode_editar_publicacao_no_wagtail(request.user, item)
                    else reverse("admin_publicacao_fluxo_editorial", args=[item.id])
                ),
                descricao=item.resumo,
                status=_admin_choice_label(PublicacaoPage, "status_editorial", item.status_editorial),
                data=item.data_publicacao,
                contexto=autores,
            )

    if deve_buscar("pagina") and is_admin(request.user):
        qs = Page.objects.live().specific()
        if query:
            filtro_busca = Q(title__icontains=query) | Q(slug__icontains=query)
            if query.isdigit():
                filtro_busca |= Q(id=int(query))
            qs = qs.filter(filtro_busca)
        if meus_itens:
            qs = qs.filter(owner=request.user)
        qs = _admin_filtrar_periodo(qs, "first_published_at__date", data_de, data_ate)
        qs = qs.order_by("title" if ordenar == "titulo" else "-latest_revision_created_at")[:limite_por_tipo]
        for item in qs:
            if isinstance(item, PublicacaoPage):
                continue
            _admin_busca_adicionar_resultado(
                resultados,
                tipo="Página",
                titulo=item.title,
                url=f"/admin/pages/{item.id}/edit/",
                status="Publicada" if item.live else "Rascunho",
                data=item.first_published_at or item.latest_revision_created_at,
                contexto=item.get_verbose_name(),
            )

    if deve_buscar("pergunta") and _pode_acessar_admin_publicacoes(request.user):
        qs = PerguntaQuizCatalogo.objects.select_related("categoria_editorial")
        if query:
            filtro_busca = Q(pergunta__icontains=query) | Q(explicacao__icontains=query)
            if query.isdigit():
                filtro_busca |= Q(id=int(query))
            qs = qs.filter(filtro_busca)
        if status:
            if status in {"ativa", "ativo"}:
                qs = qs.filter(ativa=True)
            elif status in {"inativa", "inativo"}:
                qs = qs.filter(ativa=False)
            else:
                qs = qs.filter(aprovacao_status=status)
        if meus_itens:
            qs = qs.filter(criado_por=request.user)
        qs = _admin_filtrar_periodo(qs, "criado_em__date", data_de, data_ate)
        qs = qs.order_by("pergunta" if ordenar == "titulo" else "-atualizado_em")[:limite_por_tipo]
        for item in qs:
            _admin_busca_adicionar_resultado(
                resultados,
                tipo="Pergunta do quiz",
                titulo=f"#{item.id} · {item.pergunta}",
                url=_admin_reverse("wagtailsnippets_conteudo_perguntaquizcatalogo:edit", item.id, fallback=f"/admin/snippets/conteudo/perguntaquizcatalogo/{item.id}/"),
                descricao=item.explicacao,
                status=f"{_admin_choice_label(PerguntaQuizCatalogo, 'aprovacao_status', item.aprovacao_status)} · {'Ativa' if item.ativa else 'Inativa'}",
                data=item.criado_em,
                contexto=str(item.categoria_editorial or ""),
            )

    if deve_buscar("categoria") and _pode_acessar_admin_publicacoes(request.user):
        qs = Categoria.objects.all()
        if query:
            filtro_busca = Q(nome__icontains=query) | Q(slug__icontains=query) | Q(descricao__icontains=query)
            if query.isdigit():
                filtro_busca |= Q(id=int(query))
            qs = qs.filter(filtro_busca)
        if status:
            qs = qs.filter(aprovacao_status=status)
        if meus_itens:
            qs = qs.filter(criado_por=request.user)
        qs = qs.order_by("nome" if ordenar == "titulo" else "nome")[:limite_por_tipo]
        for item in qs:
            _admin_busca_adicionar_resultado(
                resultados,
                tipo="Categoria",
                titulo=item.nome,
                url=_admin_reverse("wagtailsnippets_conteudo_categoria:edit", item.id, fallback=f"/admin/snippets/conteudo/categoria/{item.id}/"),
                descricao=item.descricao,
                status=_admin_choice_label(Categoria, "aprovacao_status", item.aprovacao_status),
            )

    if deve_buscar("tag") and _pode_acessar_admin_publicacoes(request.user):
        qs = TagPublicacao.objects.all()
        if query:
            filtro_busca = Q(name__icontains=query) | Q(slug__icontains=query)
            if query.isdigit():
                filtro_busca |= Q(id=int(query))
            qs = qs.filter(filtro_busca)
        if status:
            qs = qs.filter(aprovacao_status=status)
        if meus_itens:
            qs = qs.filter(criado_por=request.user)
        qs = qs.order_by("name")[:limite_por_tipo]
        for item in qs:
            _admin_busca_adicionar_resultado(
                resultados,
                tipo="Tag",
                titulo=item.name,
                url=_admin_reverse("wagtailsnippets_conteudo_tagpublicacao:edit", item.id, fallback=f"/admin/snippets/conteudo/tagpublicacao/{item.id}/"),
                status=_admin_choice_label(TagPublicacao, "aprovacao_status", item.aprovacao_status),
            )

    if deve_buscar("mensagem") and _pode_acessar_admin_contato(request.user):
        qs = MensagemContato.objects.select_related("atribuido_para")
        if not is_admin(request.user):
            qs = qs.filter(atribuido_para=request.user)
        if query:
            filtro_busca = Q(nome__icontains=query) | Q(email__icontains=query) | Q(mensagem__icontains=query)
            if query.isdigit():
                filtro_busca |= Q(id=int(query))
            qs = qs.filter(filtro_busca)
        if status:
            qs = qs.filter(status=status)
        if meus_itens:
            qs = qs.filter(atribuido_para=request.user)
        qs = _admin_filtrar_periodo(qs, "criado_em__date", data_de, data_ate)
        qs = qs.order_by("nome" if ordenar == "titulo" else "-criado_em")[:limite_por_tipo]
        for item in qs:
            _admin_busca_adicionar_resultado(
                resultados,
                tipo="Mensagem de contato",
                titulo=f"{item.nome} <{item.email}>",
                url=reverse("admin_contato_mensagem", args=[item.id]),
                descricao=item.mensagem,
                status=_admin_choice_label(MensagemContato, "status", item.status),
                data=item.criado_em,
                contexto=f"Responsável: {item.atribuido_para.get_username()}" if item.atribuido_para else "Sem responsável",
            )

    if deve_buscar("comentario") and is_admin(request.user):
        qs = ComentarioPublicacao.objects.select_related("publicacao", "usuario")
        if query:
            filtro_busca = Q(texto__icontains=query) | Q(publicacao__title__icontains=query) | Q(usuario__nome__icontains=query) | Q(usuario__email__icontains=query)
            if query.isdigit():
                filtro_busca |= Q(id=int(query))
            qs = qs.filter(filtro_busca)
        if status:
            qs = qs.filter(status=status)
        if meus_itens:
            qs = qs.filter(publicacao__autores_publicacao__autor__usuario_admin=request.user).distinct()
        qs = _admin_filtrar_periodo(qs, "criado_em__date", data_de, data_ate)
        qs = qs.order_by("publicacao__title" if ordenar == "titulo" else "-criado_em")[:limite_por_tipo]
        for item in qs:
            _admin_busca_adicionar_resultado(
                resultados,
                tipo="Comentário",
                titulo=str(item.publicacao),
                url=_admin_reverse("wagtailsnippets_conteudo_comentariopublicacao:edit", item.id, fallback=f"/admin/snippets/conteudo/comentariopublicacao/{item.id}/"),
                descricao=item.texto,
                status=_admin_choice_label(ComentarioPublicacao, "status", item.status),
                data=item.criado_em,
                contexto=str(item.usuario),
            )

    if deve_buscar("autor") and is_admin(request.user):
        qs = Autor.objects.select_related("usuario_admin")
        if query:
            filtro_busca = Q(nome_completo__icontains=query) | Q(nome_exibicao__icontains=query) | Q(username__icontains=query) | Q(email__icontains=query)
            if query.isdigit():
                filtro_busca |= Q(id=int(query))
            qs = qs.filter(filtro_busca)
        if meus_itens:
            qs = qs.filter(usuario_admin=request.user)
        qs = qs.order_by("nome_completo")[:limite_por_tipo]
        for item in qs:
            _admin_busca_adicionar_resultado(
                resultados,
                tipo="Autor",
                titulo=str(item),
                url=_admin_reverse("wagtailsnippets_conteudo_autor:edit", item.id, fallback=f"/admin/snippets/conteudo/autor/{item.id}/"),
                descricao=item.mini_bio,
                contexto=item.email,
            )

    if deve_buscar("usuario") and is_admin(request.user):
        User = get_user_model()
        qs = User.objects.all()
        if query:
            filtro_busca = Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(email__icontains=query)
            if query.isdigit():
                filtro_busca |= Q(id=int(query))
            qs = qs.filter(filtro_busca)
        if meus_itens:
            qs = qs.filter(id=request.user.id)
        if status == "ativo":
            qs = qs.filter(is_active=True)
        elif status == "inativo":
            qs = qs.filter(is_active=False)
        qs = _admin_filtrar_periodo(qs, "date_joined__date", data_de, data_ate)
        qs = qs.order_by("username" if ordenar == "titulo" else "-date_joined")[:limite_por_tipo]
        for item in qs:
            _admin_busca_adicionar_resultado(
                resultados,
                tipo="Usuário",
                titulo=item.get_full_name() or item.get_username(),
                url=reverse("admin_usuario_editar", args=[item.id]),
                status="Ativo" if item.is_active else "Inativo",
                data=item.date_joined,
                contexto=item.email,
            )

    if deve_buscar("imagem") and is_admin(request.user):
        Image = get_image_model()
        qs = Image.objects.all()
        if query:
            filtro_busca = Q(title__icontains=query) | Q(file__icontains=query)
            if query.isdigit():
                filtro_busca |= Q(id=int(query))
            qs = qs.filter(filtro_busca)
        if meus_itens:
            qs = qs.filter(uploaded_by_user=request.user)
        qs = _admin_filtrar_periodo(qs, "created_at__date", data_de, data_ate)
        qs = qs.order_by("title" if ordenar == "titulo" else "-created_at")[:limite_por_tipo]
        for item in qs:
            _admin_busca_adicionar_resultado(
                resultados,
                tipo="Imagem",
                titulo=item.title,
                url=_admin_reverse("wagtailimages:edit", item.id, fallback=f"/admin/images/{item.id}/"),
                data=item.created_at,
            )

    if deve_buscar("documento") and is_admin(request.user):
        Document = get_document_model()
        qs = Document.objects.all()
        if query:
            filtro_busca = Q(title__icontains=query) | Q(file__icontains=query)
            if query.isdigit():
                filtro_busca |= Q(id=int(query))
            qs = qs.filter(filtro_busca)
        if meus_itens:
            qs = qs.filter(uploaded_by_user=request.user)
        qs = _admin_filtrar_periodo(qs, "created_at__date", data_de, data_ate)
        qs = qs.order_by("title" if ordenar == "titulo" else "-created_at")[:limite_por_tipo]
        for item in qs:
            _admin_busca_adicionar_resultado(
                resultados,
                tipo="Documento",
                titulo=item.title,
                url=_admin_reverse("wagtaildocs:edit", item.id, fallback=f"/admin/documents/edit/{item.id}/"),
                data=item.created_at,
            )

    if ordenar == "titulo":
        resultados = sorted(resultados, key=lambda item: (item["titulo"] or "").lower())
    elif ordenar == "data_desc":
        resultados = sorted(resultados, key=lambda item: item["data"] or "", reverse=True)

    querystring = request.GET.copy()
    querystring.pop("pagina", None)
    paginator = Paginator(resultados, 40)
    pagina_atual = paginator.get_page(request.GET.get("pagina"))

    context = {
        "resultados": pagina_atual,
        "total_resultados": len(resultados),
        "busca_executada": tem_filtro,
        "filtro_q": query,
        "filtro_tipo": tipo,
        "filtro_status": status,
        "filtro_data_de": data_de_exibicao,
        "filtro_data_ate": data_ate_exibicao,
        "filtro_meus": meus_itens,
        "filtro_ordenar": ordenar,
        "query_string_sem_pagina": querystring.urlencode(),
        "tipos": [
            ("", "Todos"),
            ("publicacao", "Publicações"),
            ("pagina", "Páginas"),
            ("pergunta", "Perguntas do quiz"),
            ("categoria", "Categorias"),
            ("tag", "Tags"),
            ("mensagem", "Mensagens de contato"),
            ("comentario", "Comentários"),
            ("autor", "Autores"),
            ("usuario", "Usuários"),
            ("imagem", "Imagens"),
            ("documento", "Documentos"),
        ],
        "status_opcoes": [
            {"valor": "", "rotulo": "Todos", "tipos": ""},
            {"valor": "publicado", "rotulo": "Publicado", "tipos": "publicacao"},
            {"valor": "rascunho", "rotulo": "Rascunho", "tipos": "publicacao"},
            {"valor": "em_revisao", "rotulo": "Em revisão", "tipos": "publicacao"},
            {"valor": "ajustes_solicitados", "rotulo": "Ajustes solicitados", "tipos": "publicacao"},
            {"valor": "rejeitado", "rotulo": "Rejeitado", "tipos": "publicacao pergunta categoria tag comentario"},
            {"valor": "agendado", "rotulo": "Agendado", "tipos": "publicacao"},
            {"valor": "pendente", "rotulo": "Pendente", "tipos": "pergunta categoria tag comentario"},
            {"valor": "aprovado", "rotulo": "Aprovado", "tipos": "pergunta categoria tag comentario"},
            {"valor": "novo", "rotulo": "Novo", "tipos": "mensagem"},
            {"valor": "em_andamento", "rotulo": "Em andamento", "tipos": "mensagem"},
            {"valor": "respondido", "rotulo": "Respondido", "tipos": "mensagem"},
            {"valor": "arquivado", "rotulo": "Arquivado", "tipos": "mensagem"},
            {"valor": "ativa", "rotulo": "Ativa", "tipos": "pergunta"},
            {"valor": "inativa", "rotulo": "Inativa", "tipos": "pergunta"},
            {"valor": "ativo", "rotulo": "Usuário ativo", "tipos": "usuario"},
            {"valor": "inativo", "rotulo": "Usuário inativo", "tipos": "usuario"},
        ],
        "ordenacoes": [
            ("relevancia", "Relevância"),
            ("data_desc", "Data mais recente"),
            ("titulo", "Título"),
        ],
    }
    return render(request, "conteudo/admin_busca_global.html", context)


def _resolver_site_admin(request):
    return (
        Site.find_for_request(request)
        or Site.objects.filter(is_default_site=True).first()
        or Site.objects.first()
    )


INDEXADOR_CSV_MAX_BYTES = 5 * 1024 * 1024
INDEXADOR_CSV_MAX_ROWS = 10000
INDEXADOR_CSV_COLUNAS = [
    "titulo",
    "ano_publicacao",
    "dados_editoriais",
    "resumo",
    "palavras_chave",
    "doi",
    "url_acesso",
    "autores",
    "orcids",
    "ativo",
]
INDEXADOR_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _sanitizar_celula_csv_indexador(valor):
    texto = strip_tags((valor or "").replace("\x00", " ").strip())
    texto = "".join(ch for ch in texto if ch.isprintable() or ch in "\n\t")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    if texto.startswith(INDEXADOR_CSV_FORMULA_PREFIXES):
        texto = "'" + texto
    return texto


def _validar_url_csv_indexador(valor):
    if not valor:
        return ""
    parsed = urllib.parse.urlparse(valor)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("url_acesso deve ser uma URL http ou https válida.")
    return valor[:2000]


def _validar_orcid_csv_indexador(valor):
    if not valor:
        return ""
    if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-[\dX]{4}", valor, flags=re.IGNORECASE):
        raise ValidationError("ORCID inválido.")
    return valor.upper()


def _ler_csv_indexador_seguro(arquivo_csv):
    nome = (getattr(arquivo_csv, "name", "") or "").lower()
    if not nome.endswith(".csv"):
        raise ValidationError("Envie um arquivo .csv.")
    if (getattr(arquivo_csv, "size", 0) or 0) > INDEXADOR_CSV_MAX_BYTES:
        raise ValidationError("CSV acima do limite de 5 MB.")
    conteudo_bytes = arquivo_csv.read()
    if not conteudo_bytes:
        raise ValidationError("Arquivo CSV vazio.")
    if len(conteudo_bytes) > INDEXADOR_CSV_MAX_BYTES:
        raise ValidationError("CSV acima do limite de 5 MB.")
    if b"\x00" in conteudo_bytes:
        raise ValidationError("CSV contém bytes nulos e foi bloqueado.")
    _verificar_clamav_bytes(conteudo_bytes)
    texto_csv = None
    for codificacao in ["utf-8-sig", "cp1252", "latin-1"]:
        try:
            texto_csv = conteudo_bytes.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    if texto_csv is None:
        raise ValidationError("Não foi possível ler o CSV. Use UTF-8, ANSI ou Latin-1.")
    leitor = csv.DictReader(io.StringIO(texto_csv), restkey="__extras__")
    if not leitor.fieldnames:
        raise ValidationError("O arquivo CSV parece estar vazio.")
    fieldnames = [_sanitizar_celula_csv_indexador(nome or "") for nome in leitor.fieldnames]
    extras = [col for col in fieldnames if col not in INDEXADOR_CSV_COLUNAS]
    faltando = [col for col in INDEXADOR_CSV_COLUNAS if col not in fieldnames]
    if extras:
        raise ValidationError("Colunas extras não são aceitas: " + ", ".join(extras))
    if faltando:
        raise ValidationError("Faltam colunas no CSV: " + ", ".join(faltando))
    linhas = []
    erros = []
    for numero_linha, linha in enumerate(leitor, start=2):
        if numero_linha > INDEXADOR_CSV_MAX_ROWS + 1:
            raise ValidationError(f"CSV acima do limite de {INDEXADOR_CSV_MAX_ROWS} linhas.")
        if linha.get("__extras__"):
            erros.append(f"Linha {numero_linha}: colunas excedentes ou separador inválido.")
            continue
        normalizada = {}
        for coluna in INDEXADOR_CSV_COLUNAS:
            valor = _sanitizar_celula_csv_indexador(linha.get(coluna) or "")
            if len(valor) > 20000:
                erros.append(f"Linha {numero_linha}: campo {coluna} muito longo.")
                valor = valor[:20000]
            normalizada[coluna] = valor
        linhas.append((numero_linha, normalizada))
    return linhas, erros


def importar_csv_indexador_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "A importação do indexador é restrita a administradores.",
        )

    if request.method == "POST":
        arquivo_csv = request.FILES.get("arquivo_csv")

        if not arquivo_csv:
            messages.error(request, "Selecione um arquivo CSV para importar.")
            return redirect("admin_indexador_importar_csv")

        try:
            linhas, erros = _ler_csv_indexador_seguro(arquivo_csv)
            total = 0
            criados = 0
            atualizados = 0
            ignorados = 0

            with transaction.atomic():
                for numero_linha, linha in linhas:
                    total += 1
                    titulo = linha["titulo"][:500]
                    ano_publicacao = linha["ano_publicacao"][:20]
                    dados_editoriais = linha["dados_editoriais"]
                    resumo = linha["resumo"]
                    palavras_chave = linha["palavras_chave"][:500]
                    doi = linha["doi"][:255]
                    autores_brutos = linha["autores"]
                    orcids_brutos = linha["orcids"]
                    ativo_bruto = linha["ativo"].lower()

                    try:
                        url_acesso = _validar_url_csv_indexador(linha["url_acesso"])
                    except ValidationError as exc:
                        ignorados += 1
                        erros.append(f"Linha {numero_linha}: {exc.messages[0]}")
                        continue

                    if (
                        titulo == "Título de exemplo"
                        and resumo == "Resumo de exemplo."
                        and autores_brutos == "Autor Um; Autor Dois"
                    ):
                        ignorados += 1
                        continue

                    if not titulo:
                        ignorados += 1
                        erros.append(f"Linha {numero_linha}: título obrigatório ausente.")
                        continue

                    autores = [_sanitizar_celula_csv_indexador(item) for item in autores_brutos.split(";") if item.strip()]
                    if not resumo:
                        erros.append(f"Linha {numero_linha}: importado sem resumo.")
                    if not autores:
                        erros.append(f"Linha {numero_linha}: importado sem autor.")

                    autores_validos = []
                    for autor in autores:
                        if len(autor) > 1000:
                            erros.append(f"Linha {numero_linha}: autor truncado para 1000 caracteres.")
                            autor = autor[:1000]
                        if autor:
                            autores_validos.append(autor)

                    orcids_validos = []
                    for orcid in [item.strip() for item in orcids_brutos.split(";") if item.strip()]:
                        try:
                            orcids_validos.append(_validar_orcid_csv_indexador(orcid))
                        except ValidationError as exc:
                            erros.append(f"Linha {numero_linha}: {exc.messages[0]}")
                            orcids_validos.append("")

                    ativo = ativo_bruto not in ["0", "false", "nao", "não", "inativo"]
                    registro = RegistroIndexador.objects.filter(doi__iexact=doi).first() if doi else None

                    if registro is None:
                        registro = RegistroIndexador.objects.create(
                            titulo=titulo,
                            ano_publicacao=ano_publicacao,
                            dados_editoriais=dados_editoriais,
                            resumo=resumo,
                            palavras_chave=palavras_chave,
                            doi=doi,
                            url_acesso=url_acesso,
                            ativo=ativo,
                        )
                        criados += 1
                    else:
                        registro.titulo = titulo
                        registro.ano_publicacao = ano_publicacao
                        registro.dados_editoriais = dados_editoriais
                        registro.resumo = resumo
                        registro.palavras_chave = palavras_chave
                        registro.doi = doi
                        registro.url_acesso = url_acesso
                        registro.ativo = ativo
                        registro.save()
                        atualizados += 1

                    registro.autores_registro.all().delete()
                    for indice, nome_autor in enumerate(autores_validos):
                        RegistroIndexadorAutor.objects.create(
                            registro=registro,
                            nome=nome_autor,
                            orcid=orcids_validos[indice] if indice < len(orcids_validos) else "",
                            sort_order=indice,
                        )

            registrar_auditoria(
                request=request,
                acao="indexador_csv_importado",
                detalhes=f"Total: {total}. Criados: {criados}. Atualizados: {atualizados}. Ignorados: {ignorados}.",
            )
            messages.success(
                request,
                f"Importação concluída. Total de linhas: {total}. Criados: {criados}. Atualizados: {atualizados}. Ignorados: {ignorados}.",
            )
            for erro in erros[:10]:
                messages.warning(request, erro)
            if len(erros) > 10:
                messages.warning(request, f"Há mais {len(erros) - 10} erro(s) ou aviso(s) não exibidos.")
            return redirect("admin_indexador_importar_csv")

        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect("admin_indexador_importar_csv")
        except Exception:
            logger.exception("Falha na importação de CSV do indexador.")
            messages.error(request, "Erro ao importar CSV do indexador. Verifique o arquivo e tente novamente.")
            return redirect("admin_indexador_importar_csv")

    return render(request, "conteudo/admin_indexador_importar_csv.html", {})


def indexador_admin_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "A gestão do indexador é restrita a administradores.",
        )

    context = {
        "registros_total": RegistroIndexador.objects.count(),
        "registros_ativos": RegistroIndexador.objects.filter(ativo=True).count(),
        "registros_inativos": RegistroIndexador.objects.filter(ativo=False).count(),
        "registros_url": reverse("wagtailsnippets_conteudo_registroindexador:list"),
        "importar_url": reverse("admin_indexador_importar_csv"),
        "modelo_url": reverse("admin_indexador_modelo_csv"),
    }
    return render(request, "conteudo/admin_indexador.html", context)


def modelo_csv_indexador_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "O modelo CSV do indexador é restrito a administradores.",
        )

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="modelo_indexador.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "titulo",
        "ano_publicacao",
        "dados_editoriais",
        "resumo",
        "palavras_chave",
        "doi",
        "url_acesso",
        "autores",
        "orcids",
        "ativo",
    ])
    writer.writerow([
        "Título de exemplo",
        "2024",
        "Revista Exemplo, v. 1, n. 2",
        "Resumo de exemplo.",
        "palavra-chave um; palavra-chave dois",
        "10.0000/exemplo",
        "https://exemplo.com/artigo",
        "Autor Um; Autor Dois",
        "0000-0001-1111-1111; 0000-0002-2222-2222",
        "1",
    ])

    return response


def importar_csv_newsletter_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "A importação de inscritos é restrita a administradores.",
        )

    if request.method == "POST":
        arquivo_csv = request.FILES.get("arquivo_csv")
        status_padrao = (request.POST.get("status_inicial") or "ativo").strip().lower()
        consentimento_padrao = (request.POST.get("consentimento_padrao") or "1").strip() in {
            "1", "true", "True", "on", "yes", "sim"
        }
        origem_padrao = (request.POST.get("origem_padrao") or "importacao_csv_admin").strip()[:100]

        if not arquivo_csv:
            messages.error(request, "Selecione um arquivo CSV para importar.")
            return redirect("admin_newsletter_importar_csv")

        if status_padrao not in {"ativo", "inativo"}:
            status_padrao = "ativo"

        try:
            conteudo_bytes = arquivo_csv.read()
            texto_csv = None
            for codificacao in ["utf-8-sig", "cp1252", "latin-1"]:
                try:
                    texto_csv = conteudo_bytes.decode(codificacao)
                    break
                except UnicodeDecodeError:
                    continue

            if texto_csv is None:
                messages.error(
                    request,
                    "Não foi possível ler o arquivo CSV. Salve em UTF-8, ANSI ou Latin-1.",
                )
                return redirect("admin_newsletter_importar_csv")

            leitor = csv.DictReader(texto_csv.splitlines())
            if not leitor.fieldnames:
                messages.error(request, "O arquivo CSV parece estar vazio.")
                return redirect("admin_newsletter_importar_csv")

            campos = [campo.strip().lower() for campo in leitor.fieldnames if campo]
            if "email" not in campos:
                messages.error(
                    request,
                    "A coluna obrigatória 'email' não foi encontrada no CSV.",
                )
                return redirect("admin_newsletter_importar_csv")

            total = 0
            criados = 0
            atualizados = 0
            ignorados = 0
            erros = []
            exemplos_ignorados = 0

            with transaction.atomic():
                for numero_linha, linha in enumerate(leitor, start=2):
                    total += 1
                    normalizada = {
                        (chave or "").strip().lower(): (valor or "").strip()
                        for chave, valor in (linha or {}).items()
                    }
                    email = (normalizada.get("email") or "").strip().lower()
                    origem = (normalizada.get("origem") or origem_padrao).strip()[:100]

                    if not email:
                        ignorados += 1
                        erros.append(f"Linha {numero_linha}: e-mail vazio.")
                        continue

                    if email in {"email@exemplo.com", "usuario@exemplo.com"}:
                        exemplos_ignorados += 1
                        ignorados += 1
                        continue

                    try:
                        validate_email(email)
                    except ValidationError:
                        ignorados += 1
                        erros.append(f"Linha {numero_linha}: e-mail inválido ({email}).")
                        continue

                    ativo = status_padrao == "ativo"
                    consentimento = consentimento_padrao

                    if "ativo" in normalizada:
                        ativo_bruto = (normalizada.get("ativo") or "").strip().lower()
                        if ativo_bruto in {"1", "true", "on", "yes", "sim", "ativo"}:
                            ativo = True
                        elif ativo_bruto in {"0", "false", "off", "no", "nao", "não", "inativo"}:
                            ativo = False

                    if "consentimento" in normalizada:
                        consent_bruto = (normalizada.get("consentimento") or "").strip().lower()
                        if consent_bruto in {"1", "true", "on", "yes", "sim"}:
                            consentimento = True
                        elif consent_bruto in {"0", "false", "off", "no", "nao", "não"}:
                            consentimento = False

                    inscrito, criado = InscritoNewsletter.objects.get_or_create(
                        email=email,
                        defaults={
                            "ativo": ativo,
                            "consentimento": consentimento,
                            "origem": origem,
                            "confirmado_em": timezone.now() if ativo else None,
                        },
                    )
                    if criado:
                        criados += 1
                        NewsletterEvento.objects.create(
                            inscrito=inscrito,
                            email=inscrito.email,
                            tipo=NewsletterEvento.TIPO_INSCRICAO_CONFIRMADA if ativo else NewsletterEvento.TIPO_INSCRICAO_SOLICITADA,
                            origem=origem or "importacao_csv_admin",
                            detalhes="Importação em lote via painel administrativo.",
                        )
                        continue

                    mudou = False
                    if inscrito.ativo != ativo:
                        inscrito.ativo = ativo
                        mudou = True
                    if inscrito.consentimento != consentimento:
                        inscrito.consentimento = consentimento
                        mudou = True
                    if origem and inscrito.origem != origem:
                        inscrito.origem = origem
                        mudou = True
                    if ativo and not inscrito.confirmado_em:
                        inscrito.confirmado_em = timezone.now()
                        mudou = True

                    if mudou:
                        inscrito.save(update_fields=["ativo", "consentimento", "origem", "confirmado_em", "atualizado_em"])
                        atualizados += 1
                    else:
                        ignorados += 1

            registrar_auditoria(
                request=request,
                acao="newsletter_import_csv",
                alvo=request.user,
                detalhes=(
                    f"Importação CSV newsletter: total={total}, criados={criados}, "
                    f"atualizados={atualizados}, ignorados={ignorados}, exemplos={exemplos_ignorados}."
                ),
            )

            messages.success(
                request,
                (
                    f"Importação concluída. Linhas: {total}. "
                    f"Criados: {criados}. Atualizados: {atualizados}. Ignorados: {ignorados}."
                ),
            )
            if exemplos_ignorados:
                messages.info(request, f"Linha(s) de exemplo ignoradas: {exemplos_ignorados}.")
            for erro in erros[:15]:
                messages.warning(request, erro)
            if len(erros) > 15:
                messages.warning(request, f"Há mais {len(erros) - 15} erro(s) não exibidos.")

            return redirect("admin_newsletter_importar_csv")
        except Exception:
            logger.exception("Falha na importação de CSV da newsletter.")
            messages.error(
                request,
                "Erro ao importar CSV da newsletter. Verifique o arquivo e tente novamente.",
            )
            return redirect("admin_newsletter_importar_csv")

    return render(request, "conteudo/admin_newsletter_importar_csv.html", {})


def modelo_csv_newsletter_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "O modelo CSV da newsletter é restrito a administradores.",
        )

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="modelo_newsletter.csv"'
    writer = csv.writer(response)
    writer.writerow(["email", "origem", "ativo", "consentimento"])
    writer.writerow(["email@exemplo.com", "landing_page", "1", "1"])
    writer.writerow(["usuario@exemplo.com", "evento_presencial", "0", "1"])
    return response


MAX_MIDIA_PENDENTE_BYTES = 25 * 1024 * 1024
DEFAULT_VIDEO_UPLOAD_MAX_MB = 500
DEFAULT_VIDEO_UPLOAD_MAX_BYTES = DEFAULT_VIDEO_UPLOAD_MAX_MB * 1024 * 1024
IMAGE_CONTENT_TYPES = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}
VIDEO_CONTENT_TYPES = {
    ".mp4": ("mp4", "video/mp4"),
    ".webm": ("webm", "video/webm"),
}
PDF_TOKENS_BLOQUEADOS = [
    b"/JavaScript",
    b"/JS",
    b"/OpenAction",
    b"/AA",
    b"/AcroForm",
    b"/RichMedia",
    b"/Launch",
    b"/EmbeddedFile",
]

RICHTEXT_IMAGE_EMBED_RE = re.compile(
    r"<embed\b(?=[^>]*\bembedtype=[\"']image[\"'])(?=[^>]*\bid=[\"'](\d+)[\"'])[^>]*/?>",
    re.IGNORECASE,
)
RICHTEXT_DOCUMENT_LINK_RE = re.compile(
    r"<a\b(?=[^>]*\blinktype=[\"']document[\"'])(?=[^>]*\bid=[\"'](\d+)[\"'])[^>]*>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)


class MidiaPendenteUploadForm(forms.Form):
    titulo = forms.CharField(label="Título", max_length=255)
    tipo = forms.ChoiceField(label="Tipo", choices=MidiaPendente.TIPO_CHOICES)
    arquivo = forms.FileField(label="Arquivo")


class _BytesUpload:
    def __init__(self, data, name):
        self._data = data
        self.name = name
        self.size = len(data)

    def chunks(self):
        yield self._data


def _pode_aprovar_midia(user):
    return is_admin(user) or is_reviewer(user)


def _clamav_ativo():
    return str(os.getenv("OWNPAPER_CLAMAV_ENABLED", "false")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _verificar_clamav_bytes(data):
    if not _clamav_ativo():
        return

    host = os.getenv("OWNPAPER_CLAMAV_HOST", "clamav")
    porta = int(os.getenv("OWNPAPER_CLAMAV_PORT", "3310"))
    timeout = int(os.getenv("OWNPAPER_CLAMAV_TIMEOUT", "30"))
    try:
        with socket.create_connection((host, porta), timeout=timeout) as conexao:
            conexao.settimeout(timeout)
            conexao.sendall(b"zINSTREAM\0")
            stream = io.BytesIO(data)
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                conexao.sendall(struct.pack("!I", len(chunk)))
                conexao.sendall(chunk)
            conexao.sendall(struct.pack("!I", 0))
            resposta = conexao.recv(4096).decode("utf-8", errors="replace").strip("\0\r\n ")
    except Exception as exc:
        raise ValidationError("ClamAV indisponível. Upload bloqueado por segurança.") from exc

    if resposta.endswith(": OK") or resposta == "stream: OK":
        return
    assinatura = ""
    match = re.search(r":\s*(?P<assinatura>.+?)\s+FOUND$", resposta)
    if match:
        assinatura = match.group("assinatura")
    raise ValidationError(
        f"Arquivo bloqueado pelo antivírus{f': {assinatura}' if assinatura else ''}."
    )


def _video_upload_max_bytes():
    try:
        max_mb = int(os.getenv("OWNPAPER_VIDEO_MAX_MB", str(DEFAULT_VIDEO_UPLOAD_MAX_MB)))
    except (TypeError, ValueError):
        max_mb = DEFAULT_VIDEO_UPLOAD_MAX_MB
    return max(1, max_mb) * 1024 * 1024


def _ler_upload_midia(uploaded_file, limite_bytes=MAX_MIDIA_PENDENTE_BYTES):
    tamanho = getattr(uploaded_file, "size", 0) or 0
    limite_mb = max(1, limite_bytes // 1024 // 1024)
    if tamanho > limite_bytes:
        raise ValidationError(f"Arquivo acima do limite de {limite_mb} MB.")
    data = b"".join(uploaded_file.chunks())
    if not data:
        raise ValidationError("Arquivo vazio.")
    if len(data) > limite_bytes:
        raise ValidationError(f"Arquivo acima do limite de {limite_mb} MB.")
    _verificar_clamav_bytes(data)
    return data


def _nome_midia_sanitizada(titulo, extensao):
    base = slugify(titulo or "midia")[:80] or "midia"
    return f"{base}-{uuid.uuid4().hex[:10]}.{extensao}"


def _sanitizar_imagem_upload(uploaded_file, titulo):
    data = _ler_upload_midia(uploaded_file)
    nome_original = (getattr(uploaded_file, "name", "") or "").lower()
    if nome_original.endswith(".svg") or b"<svg" in data[:1024].lower():
        raise ValidationError("SVG não é aceito por padrão.")

    try:
        with PILImage.open(io.BytesIO(data)) as imagem_verificacao:
            imagem_verificacao.verify()
        with PILImage.open(io.BytesIO(data)) as imagem:
            formato = (imagem.format or "").upper()
            if formato not in IMAGE_CONTENT_TYPES:
                raise ValidationError("Formato de imagem não aceito. Use JPG, PNG ou WebP.")

            imagem = ImageOps.exif_transpose(imagem)
            extensao, content_type = IMAGE_CONTENT_TYPES[formato]
            saida = io.BytesIO()

            if formato == "JPEG":
                if imagem.mode not in ("RGB", "L"):
                    imagem = imagem.convert("RGB")
                imagem.save(saida, format="JPEG", quality=90, optimize=True)
            elif formato == "PNG":
                if imagem.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                    imagem = imagem.convert("RGBA")
                imagem.save(saida, format="PNG", optimize=True)
            else:
                if imagem.mode not in ("RGB", "RGBA"):
                    imagem = imagem.convert("RGBA" if "A" in imagem.getbands() else "RGB")
                imagem.save(saida, format="WEBP", quality=90, method=6)
    except UnidentifiedImageError as exc:
        raise ValidationError("Arquivo de imagem inválido.") from exc

    bytes_sanitizados = saida.getvalue()
    return {
        "bytes": bytes_sanitizados,
        "nome": _nome_midia_sanitizada(titulo, extensao),
        "content_type": content_type,
        "tamanho": len(bytes_sanitizados),
    }


def _sanitizar_pdf_upload(uploaded_file, titulo):
    data = _ler_upload_midia(uploaded_file)
    if not data.startswith(b"%PDF-"):
        raise ValidationError("Documento inválido. Apenas PDF é aceito.")
    for token in PDF_TOKENS_BLOQUEADOS:
        if token in data:
            raise ValidationError("PDF bloqueado por conter recursos ativos ou anexos.")

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ValidationError("PDF criptografado não é aceito.")
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.add_metadata({"/Producer": "OwnPaper"})
        saida = io.BytesIO()
        writer.write(saida)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("PDF inválido ou não sanitizável.") from exc

    bytes_sanitizados = saida.getvalue()
    for token in PDF_TOKENS_BLOQUEADOS:
        if token in bytes_sanitizados:
            raise ValidationError("PDF sanitizado ainda contém recurso bloqueado.")
    return {
        "bytes": bytes_sanitizados,
        "nome": _nome_midia_sanitizada(titulo, "pdf"),
        "content_type": "application/pdf",
        "tamanho": len(bytes_sanitizados),
    }


def _executavel_midia_obrigatorio(nome):
    caminho = shutil.which(nome)
    if not caminho:
        raise ValidationError(
            f"{nome} indisponível. Upload de vídeo bloqueado por segurança."
        )
    return caminho


def _ffprobe_video(path):
    ffprobe = _executavel_midia_obrigatorio("ffprobe")
    resultado = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            path,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if resultado.returncode != 0:
        raise ValidationError("Vídeo inválido ou não verificável.")
    try:
        return json.loads(resultado.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ValidationError("Vídeo inválido ou não verificável.") from exc


def _validar_metadados_video(path):
    metadados = _ffprobe_video(path)
    streams = metadados.get("streams") or []
    video_streams = [item for item in streams if item.get("codec_type") == "video"]
    if not video_streams:
        raise ValidationError("Arquivo sem stream de vídeo válido.")
    if len(video_streams) > 1:
        raise ValidationError("Vídeo com múltiplas trilhas de vídeo não é aceito.")

    video = video_streams[0]
    codec = (video.get("codec_name") or "").lower()
    if codec not in {"h264", "vp8", "vp9", "av1"}:
        raise ValidationError("Codec de vídeo não aceito por padrão.")
    for stream in streams:
        tipo = stream.get("codec_type")
        if tipo not in {"video", "audio"}:
            raise ValidationError("Vídeo com trilhas de dados, legendas ou anexos não é aceito.")
        if tipo == "audio" and (stream.get("codec_name") or "").lower() not in {
            "aac",
            "mp3",
            "opus",
            "vorbis",
        }:
            raise ValidationError("Codec de áudio não aceito por padrão.")


def _sanitizar_video_upload(uploaded_file, titulo):
    data = _ler_upload_midia(uploaded_file, limite_bytes=_video_upload_max_bytes())
    nome_original = (getattr(uploaded_file, "name", "") or "").lower()
    _, extensao = os.path.splitext(nome_original)
    if extensao not in VIDEO_CONTENT_TYPES:
        raise ValidationError("Formato de vídeo não aceito. Use MP4 ou WebM.")

    ffmpeg = _executavel_midia_obrigatorio("ffmpeg")
    extensao_final, content_type = VIDEO_CONTENT_TYPES[extensao]
    with tempfile.TemporaryDirectory(prefix="ownpaper-video-") as tempdir:
        entrada = os.path.join(tempdir, f"entrada{extensao}")
        saida = os.path.join(tempdir, f"saida.{extensao_final}")
        with open(entrada, "wb") as arquivo:
            arquivo.write(data)

        _validar_metadados_video(entrada)
        comando = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            entrada,
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-map_metadata",
            "-1",
            "-c",
            "copy",
        ]
        if extensao == ".mp4":
            comando.extend(["-movflags", "+faststart"])
        comando.append(saida)
        resultado = subprocess.run(
            comando,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if resultado.returncode != 0 or not os.path.exists(saida):
            raise ValidationError("Vídeo inválido ou não sanitizável.")

        _validar_metadados_video(saida)
        with open(saida, "rb") as arquivo:
            bytes_sanitizados = arquivo.read()

    if len(bytes_sanitizados) > _video_upload_max_bytes():
        raise ValidationError(
            f"Vídeo sanitizado acima do limite de {_video_upload_max_bytes() // 1024 // 1024} MB."
        )
    return {
        "bytes": bytes_sanitizados,
        "nome": _nome_midia_sanitizada(titulo, extensao_final),
        "content_type": content_type,
        "tamanho": len(bytes_sanitizados),
    }


def _sanitizar_midia_upload(uploaded_file, tipo, titulo):
    if tipo == MidiaPendente.TIPO_IMAGEM:
        return _sanitizar_imagem_upload(uploaded_file, titulo)
    if tipo == MidiaPendente.TIPO_DOCUMENTO:
        return _sanitizar_pdf_upload(uploaded_file, titulo)
    if tipo == MidiaPendente.TIPO_VIDEO:
        return _sanitizar_video_upload(uploaded_file, titulo)
    raise ValidationError("Tipo de mídia inválido.")


def _sanitizar_midia_wagtail(objeto, tipo, titulo):
    with objeto.file.open("rb") as arquivo:
        data = arquivo.read()
    nome = os.path.basename(getattr(objeto.file, "name", "") or getattr(objeto, "title", "") or "midia")
    return _sanitizar_midia_upload(_BytesUpload(data, nome), tipo, titulo)


def _midia_wagtail_foi_enviada_pelo_usuario(objeto, user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    uploaded_by = getattr(objeto, "uploaded_by_user_id", None)
    return bool(uploaded_by and uploaded_by == user.id)


def _midia_wagtail_parece_upload_recente(objeto, minutos=15):
    criado_em = getattr(objeto, "created_at", None)
    if not criado_em:
        return True
    return criado_em >= timezone.now() - timedelta(minutes=minutos)


def _midia_wagtail_deve_ir_para_quarentena(objeto, user):
    return (
        _midia_wagtail_foi_enviada_pelo_usuario(objeto, user)
        and _midia_wagtail_parece_upload_recente(objeto)
    )


def _imagem_aprovada_por_quarentena(imagem):
    return bool(
        imagem
        and MidiaPendente.objects.filter(
            tipo=MidiaPendente.TIPO_IMAGEM,
            status=MidiaPendente.STATUS_APROVADO,
            imagem_aprovada=imagem,
        ).exists()
    )


def _documento_aprovado_por_quarentena(documento):
    return bool(
        documento
        and MidiaPendente.objects.filter(
            tipo=MidiaPendente.TIPO_DOCUMENTO,
            status=MidiaPendente.STATUS_APROVADO,
            documento_aprovado=documento,
        ).exists()
    )


def _criar_midia_pendente_de_objeto_wagtail(objeto, tipo, user, titulo=None, token="", texto_link=""):
    titulo_final = (titulo or getattr(objeto, "title", "") or "Mídia pendente").strip()[:255]
    sanitizado = _sanitizar_midia_wagtail(objeto, tipo, titulo_final)
    midia = MidiaPendente.objects.create(
        titulo=titulo_final,
        tipo=tipo,
        arquivo=ContentFile(sanitizado["bytes"], name=sanitizado["nome"]),
        nome_original=os.path.basename(getattr(objeto.file, "name", "") or "")[:255],
        content_type=sanitizado["content_type"],
        tamanho_bytes=sanitizado["tamanho"],
        criado_por=user,
        substituicao_token=token,
        texto_link=(texto_link or titulo_final)[:255],
    )
    return midia


def _criar_midia_wagtail_aprovada(midia, usuario):
    with midia.arquivo.open("rb") as arquivo:
        data = arquivo.read()
    nome = os.path.basename(midia.arquivo.name)
    colecao = Collection.get_first_root_node()

    if midia.tipo == MidiaPendente.TIPO_IMAGEM:
        ImageModel = get_image_model()
        kwargs = {"title": midia.titulo, "file": ContentFile(data, name=nome)}
        if hasattr(ImageModel, "collection"):
            kwargs["collection"] = colecao
        if hasattr(ImageModel, "uploaded_by_user"):
            kwargs["uploaded_by_user"] = usuario
        return ImageModel.objects.create(**kwargs)

    if midia.tipo == MidiaPendente.TIPO_VIDEO:
        midia.video_aprovado.save(nome, ContentFile(data), save=False)
        return None

    DocumentModel = get_document_model()
    kwargs = {"title": midia.titulo, "file": ContentFile(data, name=nome)}
    if hasattr(DocumentModel, "collection"):
        kwargs["collection"] = colecao
    if hasattr(DocumentModel, "uploaded_by_user"):
        kwargs["uploaded_by_user"] = usuario
    return DocumentModel.objects.create(**kwargs)


def _remover_objeto_wagtail_quarentenado(objeto):
    try:
        objeto.delete()
    except Exception:
        logger.warning("Não foi possível remover mídia Wagtail quarentenada %s.", getattr(objeto, "id", "?"), exc_info=True)


def _proximo_sort_order_imagem_publicacao(publicacao):
    ultimo = publicacao.imagens_publicacao.order_by("-sort_order").values_list("sort_order", flat=True).first()
    return (ultimo if ultimo is not None else -1) + 1


def _quarentenar_imagem_publicacao_item(item, user):
    imagem = item.imagem
    if not imagem or _imagem_aprovada_por_quarentena(imagem):
        return False
    if not _midia_wagtail_deve_ir_para_quarentena(imagem, user):
        return False

    try:
        midia = _criar_midia_pendente_de_objeto_wagtail(
            imagem,
            MidiaPendente.TIPO_IMAGEM,
            user,
            titulo=item.titulo or imagem.title,
        )
    except ValidationError:
        item.imagem = None
        item.save(update_fields=["imagem"])
        _remover_objeto_wagtail_quarentenado(imagem)
        raise
    item.midia_pendente = midia
    item.imagem = None
    item.save(update_fields=["midia_pendente", "imagem"])
    _remover_objeto_wagtail_quarentenado(imagem)
    return True


def _quarentenar_capa_publicacao(publicacao, user):
    imagem = publicacao.imagem_capa
    if not imagem or _imagem_aprovada_por_quarentena(imagem):
        return False
    if not _midia_wagtail_deve_ir_para_quarentena(imagem, user):
        return False

    try:
        midia = _criar_midia_pendente_de_objeto_wagtail(
            imagem,
            MidiaPendente.TIPO_IMAGEM,
            user,
            titulo=imagem.title,
        )
    except ValidationError:
        PublicacaoPage.objects.filter(id=publicacao.id).update(imagem_capa=None)
        publicacao.imagem_capa = None
        _remover_objeto_wagtail_quarentenado(imagem)
        raise
    PublicacaoPage.objects.filter(id=publicacao.id).update(
        imagem_capa=None,
        imagem_capa_pendente=midia,
    )
    publicacao.imagem_capa = None
    publicacao.imagem_capa_pendente = midia
    _remover_objeto_wagtail_quarentenado(imagem)
    return True


def _quarentenar_richtext_publicacao(publicacao, campo, user):
    valor = str(getattr(publicacao, campo, "") or "")
    if not valor:
        return False

    ImageModel = get_image_model()
    DocumentModel = get_document_model()
    alterado = False

    def substituir_imagem(match):
        nonlocal alterado
        imagem_id = int(match.group(1))
        imagem = ImageModel.objects.filter(id=imagem_id).first()
        if not imagem or _imagem_aprovada_por_quarentena(imagem):
            return match.group(0)
        if not _midia_wagtail_deve_ir_para_quarentena(imagem, user):
            return match.group(0)

        try:
            midia = _criar_midia_pendente_de_objeto_wagtail(
                imagem,
                MidiaPendente.TIPO_IMAGEM,
                user,
                titulo=imagem.title,
            )
        except ValidationError:
            _remover_objeto_wagtail_quarentenado(imagem)
            alterado = True
            return "Imagem removida por segurança."
        marcador = f"img-pendente-{midia.id}"
        ImagemPublicacao.objects.create(
            publicacao=publicacao,
            midia_pendente=midia,
            titulo=imagem.title,
            marcador=marcador,
            sort_order=_proximo_sort_order_imagem_publicacao(publicacao),
        )
        _remover_objeto_wagtail_quarentenado(imagem)
        alterado = True
        return f"[[i:{marcador}]]"

    def substituir_documento(match):
        nonlocal alterado
        documento_id = int(match.group(1))
        documento = DocumentModel.objects.filter(id=documento_id).first()
        if not documento or _documento_aprovado_por_quarentena(documento):
            return match.group(0)
        if not _midia_wagtail_deve_ir_para_quarentena(documento, user):
            return match.group(0)

        texto_link = strip_tags(match.group(2) or "").strip() or documento.title
        token = f"[[documento-pendente:{uuid.uuid4().hex[:12]}]]"
        try:
            midia = _criar_midia_pendente_de_objeto_wagtail(
                documento,
                MidiaPendente.TIPO_DOCUMENTO,
                user,
                titulo=documento.title,
                token=token,
                texto_link=texto_link,
            )
        except ValidationError:
            _remover_objeto_wagtail_quarentenado(documento)
            alterado = True
            return "Documento removido por segurança."
        token_final = f"[[documento-pendente:{midia.id}]]"
        MidiaPendente.objects.filter(id=midia.id).update(substituicao_token=token_final)
        _remover_objeto_wagtail_quarentenado(documento)
        alterado = True
        return token_final

    novo_valor = RICHTEXT_IMAGE_EMBED_RE.sub(substituir_imagem, valor)
    novo_valor = RICHTEXT_DOCUMENT_LINK_RE.sub(substituir_documento, novo_valor)
    if alterado and novo_valor != valor:
        setattr(publicacao, campo, novo_valor)
        PublicacaoPage.objects.filter(id=publicacao.id).update(**{campo: novo_valor})
    return alterado


def _reintegrar_documento_pendente_em_publicacoes(midia, documento, usuario):
    token = (midia.substituicao_token or "").strip()
    if not token:
        return 0
    texto = escape(midia.texto_link or midia.titulo or documento.title)
    link = f'<a linktype="document" id="{documento.id}">{texto}</a>'
    atualizadas = 0
    for publicacao in PublicacaoPage.objects.filter(Q(corpo__contains=token) | Q(resumo__contains=token)):
        campos = []
        for campo in ("resumo", "corpo"):
            valor = str(getattr(publicacao, campo, "") or "")
            if token in valor:
                setattr(publicacao, campo, valor.replace(token, link))
                campos.append(campo)
        if campos:
            publicacao.save(update_fields=campos)
            publicacao.save_revision(user=usuario)
            atualizadas += 1
    return atualizadas


def _salvar_revisao_midia_reintegrada(publicacao, usuario):
    revisao = publicacao.save_revision(user=usuario)
    if publicacao.live:
        revisao.publish(user=usuario)


def _reintegrar_imagem_pendente_em_publicacoes(midia, imagem, usuario):
    atualizadas = 0
    ids_publicacoes = set()

    for item in ImagemPublicacao.objects.filter(midia_pendente=midia, imagem__isnull=True):
        item.imagem = imagem
        item.save(update_fields=["imagem"])
        ids_publicacoes.add(item.publicacao_id)

    for publicacao in PublicacaoPage.objects.filter(imagem_capa_pendente=midia, imagem_capa__isnull=True):
        publicacao.imagem_capa = imagem
        publicacao.save(update_fields=["imagem_capa"])
        ids_publicacoes.add(publicacao.id)

    for publicacao in PublicacaoPage.objects.filter(id__in=ids_publicacoes):
        _salvar_revisao_midia_reintegrada(publicacao, usuario)
        atualizadas += 1

    return atualizadas


def _quarentenar_midias_publicacao_diretas(request, publicacao):
    alteracoes = 0
    try:
        if _quarentenar_capa_publicacao(publicacao, request.user):
            alteracoes += 1
        for item in list(publicacao.imagens_publicacao.select_related("imagem", "midia_pendente")):
            if _quarentenar_imagem_publicacao_item(item, request.user):
                alteracoes += 1
        for campo in ("resumo", "corpo"):
            if _quarentenar_richtext_publicacao(publicacao, campo, request.user):
                alteracoes += 1
    except ValidationError as exc:
        messages.error(request, "Mídia enviada diretamente bloqueada: " + "; ".join(exc.messages))
        registrar_auditoria(
            request=request,
            acao="midia_direta_bloqueada",
            alvo=publicacao,
            detalhes="Mídia direta bloqueada durante sanitização: " + "; ".join(exc.messages),
        )
    except Exception:
        logger.exception("Falha ao quarentenar mídia direta da publicação %s.", publicacao.id)
        messages.error(request, "Não foi possível colocar uma mídia direta em quarentena. Revise a publicação antes de publicar.")
    if alteracoes:
        publicacao.save_revision(user=request.user)
        messages.warning(
            request,
            f"{alteracoes} mídia(s) enviada(s) diretamente foram movidas para quarentena e serão inseridas após aprovação.",
        )
        registrar_auditoria(
            request=request,
            acao="midia_direta_quarentenada",
            alvo=publicacao,
            detalhes=f"{alteracoes} mídia(s) direta(s) movida(s) para quarentena.",
        )
    return alteracoes


def _registrar_atualizador_publicacao(request, publicacao):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return
    if not publicacao.pk:
        return
    PublicacaoPage.objects.filter(id=publicacao.id).update(atualizado_por=user)
    publicacao.atualizado_por = user


def midias_pendentes_admin_view(request):
    if not _pode_acessar_admin_publicacoes(request.user):
        return _negar_acesso_admin(
            request,
            "Seu usuário precisa ser autor, revisor ou administrador para acessar mídias pendentes.",
        )

    form = MidiaPendenteUploadForm()
    if request.method == "POST" and request.POST.get("acao") in {"bulk_aprovar", "bulk_rejeitar"}:
        if not _pode_aprovar_midia(request.user):
            return _negar_acesso_admin(
                request,
                "Apenas administradores e revisores podem revisar mídias pendentes.",
            )
        ids = [
            int(valor)
            for valor in request.POST.getlist("midia_ids")
            if str(valor).isdigit()
        ]
        if not ids:
            messages.warning(request, "Selecione ao menos uma mídia pendente.")
            return redirect("admin_midias_pendentes")

        midias_selecionadas = MidiaPendente.objects.filter(
            id__in=ids,
            status=MidiaPendente.STATUS_PENDENTE,
        )
        processadas = 0
        falhas = 0
        acao_bulk = request.POST.get("acao")
        for midia in midias_selecionadas:
            try:
                if acao_bulk == "bulk_aprovar":
                    _aprovar_midia_pendente(midia, request.user)
                    acao_auditoria = "midia_pendente_aprovada_massa"
                    detalhe = f"Mídia pendente #{midia.id} aprovada em massa."
                else:
                    _rejeitar_midia_pendente(midia, request.user)
                    acao_auditoria = "midia_pendente_rejeitada_massa"
                    detalhe = f"Mídia pendente #{midia.id} rejeitada em massa."
                registrar_auditoria(
                    request=request,
                    acao=acao_auditoria,
                    alvo=midia,
                    detalhes=detalhe,
                )
                processadas += 1
            except Exception:
                logger.exception("Falha ao processar mídia pendente %s em massa.", midia.id)
                falhas += 1

        if processadas:
            verbo = "aprovada(s)" if acao_bulk == "bulk_aprovar" else "rejeitada(s)"
            messages.success(request, f"{processadas} mídia(s) {verbo} em massa.")
        if falhas:
            messages.error(request, f"{falhas} mídia(s) não puderam ser processadas.")
        return redirect("admin_midias_pendentes")

    if request.method == "POST" and request.POST.get("acao") == "upload":
        form = MidiaPendenteUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                titulo = form.cleaned_data["titulo"].strip()
                tipo = form.cleaned_data["tipo"]
                arquivo = request.FILES["arquivo"]
                sanitizado = _sanitizar_midia_upload(arquivo, tipo, titulo)
                midia = MidiaPendente.objects.create(
                    titulo=titulo,
                    tipo=tipo,
                    arquivo=ContentFile(sanitizado["bytes"], name=sanitizado["nome"]),
                    nome_original=getattr(arquivo, "name", "")[:255],
                    content_type=sanitizado["content_type"],
                    tamanho_bytes=sanitizado["tamanho"],
                    criado_por=request.user,
                )
                registrar_auditoria(
                    request=request,
                    acao="midia_pendente_upload",
                    alvo=midia,
                    detalhes=f"Mídia pendente #{midia.id} enviada e sanitizada.",
                )
                messages.success(request, "Mídia enviada para aprovação com segurança.")
                return redirect("admin_midias_pendentes")
            except ValidationError as exc:
                form.add_error("arquivo", exc)
                registrar_auditoria(
                    request=request,
                    acao="midia_pendente_bloqueada",
                    detalhes=(
                        "Upload de mídia pendente bloqueado durante sanitização: "
                        + "; ".join(exc.messages)
                    ),
                )

    qs = MidiaPendente.objects.select_related(
        "criado_por",
        "revisado_por",
        "imagem_aprovada",
        "documento_aprovado",
    )
    if not _pode_aprovar_midia(request.user):
        qs = qs.filter(criado_por=request.user)

    filtro_status = (request.GET.get("status") or "").strip()
    filtro_tipo = (request.GET.get("tipo") or "").strip()
    filtro_q = (request.GET.get("q") or "").strip()
    if filtro_status:
        qs = qs.filter(status=filtro_status)
    if filtro_tipo:
        qs = qs.filter(tipo=filtro_tipo)
    if filtro_q:
        qs = qs.filter(
            Q(titulo__icontains=filtro_q)
            | Q(nome_original__icontains=filtro_q)
            | Q(criado_por__username__icontains=filtro_q)
        )

    paginator = Paginator(qs, 25)
    pagina = paginator.get_page(request.GET.get("p"))
    for midia in pagina.object_list:
        try:
            midia.arquivo_disponivel = bool(
                midia.arquivo and midia.arquivo.storage.exists(midia.arquivo.name)
            )
        except Exception:
            midia.arquivo_disponivel = False
    return render(
        request,
        "conteudo/admin_midias_pendentes.html",
        {
            "form": form,
            "pagina": pagina,
            "midias": pagina.object_list,
            "pode_aprovar": _pode_aprovar_midia(request.user),
            "filtro_status": filtro_status,
            "filtro_tipo": filtro_tipo,
            "filtro_q": filtro_q,
            "status_choices": MidiaPendente.STATUS_CHOICES,
            "tipo_choices": MidiaPendente.TIPO_CHOICES,
            "max_upload_mb": MAX_MIDIA_PENDENTE_BYTES // 1024 // 1024,
            "max_video_upload_mb": _video_upload_max_bytes() // 1024 // 1024,
        },
    )


def midia_pendente_preview_admin_view(request, midia_id):
    midia = get_object_or_404(MidiaPendente, id=midia_id)
    if not _pode_aprovar_midia(request.user) and midia.criado_por_id != request.user.id:
        return _negar_acesso_admin(
            request,
            "Você não tem permissão para visualizar esta mídia pendente.",
        )
    if not midia.arquivo:
        return HttpResponse("Arquivo não encontrado.", status=404)
    if not midia.arquivo.storage.exists(midia.arquivo.name):
        return HttpResponse("Arquivo de quarentena indisponível.", status=404)
    arquivo = midia.arquivo.open("rb")
    response = FileResponse(arquivo, content_type=midia.content_type or "application/octet-stream")
    response["Content-Disposition"] = f'inline; filename="{os.path.basename(midia.arquivo.name)}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _aprovar_midia_pendente(midia, usuario):
    objeto = _criar_midia_wagtail_aprovada(midia, usuario)
    midia.status = MidiaPendente.STATUS_APROVADO
    midia.revisado_por = usuario
    midia.revisado_em = timezone.now()
    if midia.tipo == MidiaPendente.TIPO_IMAGEM:
        midia.imagem_aprovada = objeto
    elif midia.tipo == MidiaPendente.TIPO_DOCUMENTO:
        midia.documento_aprovado = objeto
    midia.save(
        update_fields=[
            "status",
            "revisado_por",
            "revisado_em",
            "imagem_aprovada",
            "documento_aprovado",
            "video_aprovado",
            "observacao",
        ]
    )
    if midia.tipo == MidiaPendente.TIPO_IMAGEM:
        _reintegrar_imagem_pendente_em_publicacoes(midia, objeto, usuario)
    elif midia.tipo == MidiaPendente.TIPO_DOCUMENTO:
        _reintegrar_documento_pendente_em_publicacoes(midia, objeto, usuario)
    return objeto


def _rejeitar_midia_pendente(midia, usuario, observacao=""):
    midia.status = MidiaPendente.STATUS_REJEITADO
    midia.revisado_por = usuario
    midia.revisado_em = timezone.now()
    midia.observacao = observacao.strip()
    midia.save(update_fields=["status", "revisado_por", "revisado_em", "observacao"])


def midia_pendente_acao_admin_view(request, midia_id, acao):
    if not _pode_aprovar_midia(request.user):
        return _negar_acesso_admin(
            request,
            "Apenas administradores e revisores podem revisar mídias pendentes.",
        )
    if request.method != "POST":
        return redirect("admin_midias_pendentes")

    midia = get_object_or_404(MidiaPendente, id=midia_id)
    if midia.status != MidiaPendente.STATUS_PENDENTE:
        messages.warning(request, "Essa mídia já foi revisada.")
        return redirect("admin_midias_pendentes")

    if acao == "aprovar":
        try:
            midia.observacao = (request.POST.get("observacao") or "").strip()
            _aprovar_midia_pendente(midia, request.user)
            registrar_auditoria(
                request=request,
                acao="midia_pendente_aprovada",
                alvo=midia,
                detalhes=f"Mídia pendente #{midia.id} aprovada.",
            )
            messages.success(request, "Mídia aprovada e liberada na biblioteca do Wagtail.")
        except Exception:
            logger.exception("Falha ao aprovar mídia pendente %s.", midia.id)
            messages.error(request, "Não foi possível aprovar a mídia.")
        return redirect("admin_midias_pendentes")

    if acao == "rejeitar":
        _rejeitar_midia_pendente(
            midia,
            request.user,
            observacao=(request.POST.get("observacao") or ""),
        )
        registrar_auditoria(
            request=request,
            acao="midia_pendente_rejeitada",
            alvo=midia,
            detalhes=f"Mídia pendente #{midia.id} rejeitada.",
        )
        messages.success(request, "Mídia rejeitada.")
        return redirect("admin_midias_pendentes")

    messages.error(request, "Ação inválida.")
    return redirect("admin_midias_pendentes")


def publicacoes_admin_view(request):
    if not _pode_acessar_admin_publicacoes(request.user):
        return _negar_acesso_admin(
            request,
            "Seu usuário precisa estar vinculado a um autor ou ser administrador para acessar Publicações.",
        )

    query = (request.GET.get("q") or "").strip()
    categoria_id = (request.GET.get("categoria") or "").strip()
    autor_id = (request.GET.get("autor") or "").strip()
    status = _normalizar_status_publicacao_admin((request.GET.get("status") or "").strip())
    data_de_raw = (request.GET.get("data_de") or "").strip()
    data_ate_raw = (request.GET.get("data_ate") or "").strip()
    data_de_iso, data_de_exibicao = _normalizar_data_busca(data_de_raw, "pt-br")
    data_ate_iso, data_ate_exibicao = _normalizar_data_busca(data_ate_raw, "pt-br")

    queryset = (
        PublicacaoPage.objects.all()
        .select_related("categoria_principal")
        .prefetch_related("autores_publicacao__autor", "revisoes__revisor")
        .order_by("-data_publicacao", "-latest_revision_created_at")
    )

    if not is_admin(request.user):
        filtro_permissao = Q()
        if is_author(request.user):
            filtro_permissao |= Q(autores_publicacao__autor__usuario_admin=request.user)
        if is_reviewer(request.user):
            filtro_permissao |= Q(status_editorial=PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO)
            filtro_permissao |= Q(revisoes__revisor=request.user)
        queryset = queryset.filter(filtro_permissao).distinct()

    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(resumo__icontains=query)
            | Q(autores_publicacao__autor__nome_completo__icontains=query)
            | Q(autores_publicacao__autor__nome_exibicao__icontains=query)
            | Q(autores_publicacao__autor__username__icontains=query)
        ).distinct()

    if categoria_id.isdigit():
        queryset = queryset.filter(categoria_principal_id=int(categoria_id))

    if autor_id.isdigit():
        queryset = queryset.filter(autores_publicacao__autor_id=int(autor_id)).distinct()

    if status == "__com_alteracoes__":
        queryset = queryset.filter(has_unpublished_changes=True)
    elif status:
        queryset = queryset.filter(status_editorial=status)

    if data_de_iso:
        queryset = queryset.filter(data_publicacao__gte=data_de_iso)
    if data_ate_iso:
        queryset = queryset.filter(data_publicacao__lte=data_ate_iso)

    paginator = Paginator(queryset, 25)
    pagina_atual = paginator.get_page(request.GET.get("pagina"))

    querystring = request.GET.copy()
    querystring.pop("pagina", None)

    pasta_publicacoes = PublicacoesIndexPage.objects.first()
    url_nova_publicacao = ""
    if pasta_publicacoes:
        url_nova_publicacao = reverse(
            "wagtailadmin_pages:add_subpage",
            args=[pasta_publicacoes.id],
        )

    context = {
        "publicacoes": pagina_atual,
        "publicacoes_editaveis_ids": {
            item.id
            for item in pagina_atual
            if _usuario_pode_editar_publicacao_no_wagtail(request.user, item)
        },
        "filtro_q": query,
        "filtro_categoria": categoria_id,
        "filtro_autor": autor_id,
        "filtro_status": status,
        "filtro_data_de": data_de_exibicao,
        "filtro_data_ate": data_ate_exibicao,
        "categorias": Categoria.objects.order_by("nome"),
        "autores": Autor.objects.order_by("nome_completo"),
        "total_publicacoes": PublicacaoPage.objects.count(),
        "total_publicadas": PublicacaoPage.objects.filter(status_editorial=PublicacaoPage.STATUS_EDITORIAL_PUBLICADO).count(),
        "total_rascunhos": PublicacaoPage.objects.filter(status_editorial=PublicacaoPage.STATUS_EDITORIAL_RASCUNHO).count(),
        "total_com_alteracoes": PublicacaoPage.objects.filter(has_unpublished_changes=True).count(),
        "total_aguardando_aprovacao": PublicacaoPage.objects.filter(status_editorial=PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO).count(),
        "query_string_sem_pagina": querystring.urlencode(),
        "url_nova_publicacao": url_nova_publicacao,
        "tem_pasta_publicacoes": bool(pasta_publicacoes),
    }
    return render(request, "conteudo/admin_publicacoes_lista.html", context)


def _normalizar_status_publicacao_admin(valor):
    valor = (valor or "").strip().lower()
    aliases = {
        "rascunho": PublicacaoPage.STATUS_EDITORIAL_RASCUNHO,
        "draft": PublicacaoPage.STATUS_EDITORIAL_RASCUNHO,
        "em_revisao": PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO,
        "em revisão": PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO,
        "revisao": PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO,
        "revisão": PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO,
        "ajustes_solicitados": PublicacaoPage.STATUS_EDITORIAL_AJUSTES,
        "ajustes": PublicacaoPage.STATUS_EDITORIAL_AJUSTES,
        "rejeitado": PublicacaoPage.STATUS_EDITORIAL_REJEITADO,
        "rejeitada": PublicacaoPage.STATUS_EDITORIAL_REJEITADO,
        "agendado": PublicacaoPage.STATUS_EDITORIAL_AGENDADO,
        "agendada": PublicacaoPage.STATUS_EDITORIAL_AGENDADO,
        "publicado": PublicacaoPage.STATUS_EDITORIAL_PUBLICADO,
        "publicada": PublicacaoPage.STATUS_EDITORIAL_PUBLICADO,
        "aguardando_aprovacao": PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO,
        "com_alteracoes": "__com_alteracoes__",
    }
    return aliases.get(valor, valor)


def quiz_catalogo_admin_view(request):
    if not _pode_acessar_admin_publicacoes(request.user):
        return _negar_acesso_admin(
            request,
            "Seu usuário precisa estar vinculado a um autor ou ser administrador para acessar Perguntas do quiz.",
        )

    query = (request.GET.get("q") or "").strip()
    categoria_id = (request.GET.get("categoria") or "").strip()
    tag_id = (request.GET.get("tag") or "").strip()
    status = (request.GET.get("status") or "").strip()
    aprovacao = (request.GET.get("aprovacao") or "").strip()
    uso = (request.GET.get("uso") or "").strip()
    ordenar = (request.GET.get("ordenar") or "").strip() or "atualizado_desc"
    data_de_raw = (request.GET.get("data_de") or "").strip()
    data_ate_raw = (request.GET.get("data_ate") or "").strip()
    data_de_iso, data_de_exibicao = _normalizar_data_busca(data_de_raw, "pt-br")
    data_ate_iso, data_ate_exibicao = _normalizar_data_busca(data_ate_raw, "pt-br")

    queryset = (
        PerguntaQuizCatalogo.objects.all()
        .select_related("categoria_editorial")
        .prefetch_related(
            "tags_editoriais",
            "publicacoes_vinculadas__publicacao__categoria_principal",
            "publicacoes_vinculadas__publicacao__tags",
        )
        .annotate(total_usos=Count("publicacoes_vinculadas", distinct=True))
    )

    if not (is_admin(request.user) or is_reviewer(request.user)):
        queryset = queryset.filter(
            Q(aprovacao_status=PerguntaQuizCatalogo.STATUS_APROVADO)
            | Q(criado_por=request.user)
        )

    if query:
        filtro_q = Q(pergunta__icontains=query) | Q(explicacao__icontains=query)
        if query.isdigit():
            filtro_q |= Q(id=int(query))
        queryset = queryset.filter(filtro_q)

    if categoria_id.isdigit():
        queryset = queryset.filter(categoria_editorial_id=int(categoria_id))

    if tag_id.isdigit():
        queryset = queryset.filter(tags_editoriais__id=int(tag_id)).distinct()

    if status == "ativa":
        queryset = queryset.filter(ativa=True)
    elif status == "inativa":
        queryset = queryset.filter(ativa=False)

    if aprovacao in {
        PerguntaQuizCatalogo.STATUS_PENDENTE,
        PerguntaQuizCatalogo.STATUS_APROVADO,
        PerguntaQuizCatalogo.STATUS_REJEITADO,
    }:
        queryset = queryset.filter(aprovacao_status=aprovacao)

    if uso == "em_uso":
        queryset = queryset.filter(publicacoes_vinculadas__isnull=False).distinct()
    elif uso == "sem_uso":
        queryset = queryset.filter(publicacoes_vinculadas__isnull=True)

    if data_de_iso:
        queryset = queryset.filter(atualizado_em__date__gte=data_de_iso)
    if data_ate_iso:
        queryset = queryset.filter(atualizado_em__date__lte=data_ate_iso)

    ordenacoes = {
        "pergunta_asc": ["pergunta", "id"],
        "pergunta_desc": ["-pergunta", "-id"],
        "criado_desc": ["-criado_em", "-id"],
        "criado_asc": ["criado_em", "id"],
        "atualizado_desc": ["-atualizado_em", "-id"],
        "atualizado_asc": ["atualizado_em", "id"],
        "uso_desc": ["-total_usos", "-atualizado_em"],
        "uso_asc": ["total_usos", "-atualizado_em"],
    }
    queryset = queryset.order_by(*ordenacoes.get(ordenar, ordenacoes["atualizado_desc"]))

    paginator = Paginator(queryset, 25)
    pagina_atual = paginator.get_page(request.GET.get("pagina"))

    querystring = request.GET.copy()
    querystring.pop("pagina", None)

    context = {
        "perguntas": pagina_atual,
        "filtro_q": query,
        "filtro_categoria": categoria_id,
        "filtro_tag": tag_id,
        "filtro_status": status,
        "filtro_aprovacao": aprovacao,
        "filtro_uso": uso,
        "filtro_ordenar": ordenar,
        "filtro_data_de": data_de_exibicao,
        "filtro_data_ate": data_ate_exibicao,
        "categorias": Categoria.objects.order_by("nome"),
        "tags": TagPublicacao.objects.order_by("name"),
        "total_perguntas": PerguntaQuizCatalogo.objects.count(),
        "total_ativas": PerguntaQuizCatalogo.objects.filter(ativa=True).count(),
        "total_em_uso": PerguntaQuizCatalogo.objects.filter(publicacoes_vinculadas__isnull=False).distinct().count(),
        "total_sem_uso": PerguntaQuizCatalogo.objects.filter(publicacoes_vinculadas__isnull=True).count(),
        "url_nova_pergunta": reverse("wagtailsnippets_conteudo_perguntaquizcatalogo:add"),
        "query_string_sem_pagina": querystring.urlencode(),
    }
    return render(request, "conteudo/admin_quiz_catalogo_lista.html", context)


def categorias_tags_admin_view(request):
    if not _pode_acessar_admin_publicacoes(request.user):
        return _negar_acesso_admin(
            request,
            "Seu usuário precisa estar vinculado a um autor ou ser administrador para acessar Categorias e Tags.",
        )

    context = {
        "categorias_total": Categoria.objects.count(),
        "categorias_pendentes": Categoria.objects.filter(aprovacao_status=Categoria.STATUS_PENDENTE).count(),
        "tags_total": TagPublicacao.objects.count(),
        "tags_pendentes": TagPublicacao.objects.filter(aprovacao_status=TagPublicacao.STATUS_PENDENTE).count(),
        "categorias_url": reverse("wagtailsnippets_conteudo_categoria:list"),
        "tags_url": reverse("wagtailsnippets_conteudo_tagpublicacao:list"),
    }
    return render(request, "conteudo/admin_categorias_tags.html", context)


def newsletter_admin_view(request):
    if not is_admin(request.user):
        return _negar_acesso_admin(
            request,
            "Seu usuário precisa ser administrador para acessar Newsletter.",
        )

    context = {
        "inscritos_total": InscritoNewsletter.objects.count(),
        "inscritos_ativos": InscritoNewsletter.objects.filter(ativo=True).count(),
        "eventos_total": NewsletterEvento.objects.count(),
        "solicitacoes_pendentes": SolicitacaoPrivacidadeNewsletter.objects.filter(
            status=SolicitacaoPrivacidadeNewsletter.STATUS_PENDENTE
        ).count(),
        "inscritos_url": reverse("wagtailsnippets_conteudo_inscritonewsletter:list"),
        "eventos_url": reverse("wagtailsnippets_conteudo_newsletterevento:list"),
        "privacidade_url": reverse("wagtailsnippets_conteudo_solicitacaoprivacidadenewsletter:list"),
        "importar_url": reverse("admin_newsletter_importar_csv"),
    }
    return render(request, "conteudo/admin_newsletter.html", context)


def _revisores_eligiveis_para_publicacao(publicacao):
    User = get_user_model()
    autores_vinculados = set(
        publicacao.autores_publicacao.values_list("autor__usuario_admin_id", flat=True)
    )
    queryset = (
        User.objects.filter(is_active=True, is_staff=True)
        .filter(Q(is_superuser=True) | Q(groups__name="Revisores"))
        .distinct()
        .order_by("username")
    )
    if autores_vinculados:
        queryset = queryset.exclude(pk__in=[uid for uid in autores_vinculados if uid])
    return queryset


def _revisao_atribuida_para_usuario(publicacao, user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return publicacao.revisoes.filter(revisor=user).exists()


def _revisao_pendente_atribuida_para_usuario(publicacao, user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return publicacao.revisoes.filter(
        revisor=user,
        decisao=PublicacaoRevisao.DECISAO_PENDENTE,
    ).exists()


def _revisoes_pendentes_publicacao(publicacao):
    return PublicacaoRevisao.objects.filter(
        publicacao=publicacao,
        decisao=PublicacaoRevisao.DECISAO_PENDENTE,
    )


def _usuario_pode_editar_publicacao_no_wagtail(user, publicacao):
    if is_admin(user):
        return True
    autor = _autor_vinculado_do_usuario(user)
    return bool(
        autor
        and _publicacao_pertence_ao_autor(publicacao, autor)
        and not (is_reviewer(user) and not is_author(user))
        and (
            publicacao.status_editorial
            not in {
                PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO,
                PublicacaoPage.STATUS_EDITORIAL_AGENDADO,
                PublicacaoPage.STATUS_EDITORIAL_PUBLICADO,
            }
        )
    )


def _enviar_alerta_publicacao_para_admins(publicacao, assunto, mensagem_html):
    admins = list(
        get_user_model().objects.filter(is_active=True, is_superuser=True)
        .exclude(email__isnull=True)
        .exclude(email__exact="")
        .values_list("email", flat=True)
        .distinct()
    )
    if not admins:
        return

    msg = EmailMessage(
        subject=assunto,
        body=mensagem_html,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=admins,
    )
    msg.content_subtype = "html"
    msg.send(fail_silently=True)


def _enviar_alerta_publicacao_para_admins_e_revisores(publicacao, assunto, mensagem_html):
    destinatarios = set(
        get_user_model().objects.filter(is_active=True, is_superuser=True)
        .exclude(email__isnull=True)
        .exclude(email__exact="")
        .values_list("email", flat=True)
    )
    destinatarios.update(
        publicacao.revisoes.select_related("revisor")
        .exclude(revisor__email__isnull=True)
        .exclude(revisor__email__exact="")
        .values_list("revisor__email", flat=True)
    )
    destinatarios = sorted(email for email in destinatarios if email)
    if not destinatarios:
        return

    msg = EmailMessage(
        subject=assunto,
        body=mensagem_html,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=destinatarios,
    )
    msg.content_subtype = "html"
    msg.send(fail_silently=True)


def _emails_autores_publicacao(publicacao):
    emails = set()
    autorias = publicacao.autores_publicacao.select_related("autor__usuario_admin", "autor")
    for autoria in autorias:
        autor = autoria.autor
        if autor.usuario_admin_id and autor.usuario_admin.email:
            emails.add(autor.usuario_admin.email.strip().lower())
        if autor.email:
            emails.add(autor.email.strip().lower())
    return sorted(email for email in emails if email)


def _enviar_alerta_publicacao_para_autores(publicacao, assunto, mensagem_html):
    destinatarios = _emails_autores_publicacao(publicacao)
    if not destinatarios:
        return

    msg = EmailMessage(
        subject=assunto,
        body=mensagem_html,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=destinatarios,
    )
    msg.content_subtype = "html"
    msg.send(fail_silently=True)


def _link_fluxo_editorial_publicacao(publicacao):
    try:
        return reverse("admin_publicacao_fluxo_editorial", args=[publicacao.id])
    except NoReverseMatch:
        return ""


def _publicar_ou_agendar_publicacao_aprovada(publicacao, user):
    if motivo_pendencia := _publicacao_tem_dependencias_editoriais_pendentes_sem_autoria_pendente(publicacao):
        return "", motivo_pendencia
    if _publicacao_tem_autoria_pendente(publicacao) and not is_admin(user):
        return "", "Há autoria pendente de confirmação nesta publicação."

    revision = publicacao.get_latest_revision()
    if revision is None:
        revision = publicacao.save_revision(user=user, log_action=True)

    revision_object = revision.as_object()
    go_live_at = getattr(revision_object, "go_live_at", None)
    agendada = bool(go_live_at and go_live_at > timezone.now())

    action = PublishPageRevisionAction(revision, user=user)
    action.execute(skip_permission_checks=True)

    PublicacaoPage.objects.filter(id=publicacao.id).update(
        status_editorial=(
            PublicacaoPage.STATUS_EDITORIAL_AGENDADO
            if agendada
            else PublicacaoPage.STATUS_EDITORIAL_PUBLICADO
        ),
        publicado_em=None if agendada else timezone.now(),
        publicado_por=user,
        reabertura_solicitada=False,
    )
    publicacao.refresh_from_db()
    return (
        PublicacaoPage.STATUS_EDITORIAL_AGENDADO
        if agendada
        else PublicacaoPage.STATUS_EDITORIAL_PUBLICADO
    ), ""


def publicacao_fluxo_editorial_admin_view(request, publicacao_id):
    if not _pode_acessar_admin_publicacoes(request.user):
        return _negar_acesso_admin(
            request,
            "O fluxo editorial é restrito a autores, revisores e administradores.",
        )

    publicacao = get_object_or_404(
        PublicacaoPage.objects.select_related("categoria_principal")
        .prefetch_related("autores_publicacao__autor", "revisoes__revisor"),
        pk=publicacao_id,
    )

    autor_vinculado = _autor_vinculado_do_usuario_incluindo_admin(request.user)
    if not is_admin(request.user) and not is_reviewer(request.user):
        if not autor_vinculado or not publicacao.autores_publicacao.filter(autor=autor_vinculado).exists():
            return _negar_acesso_admin(request, "Você não pode acessar o fluxo editorial desta publicação.")
    elif (
        publicacao.status_editorial == PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO
        and not _revisao_atribuida_para_usuario(publicacao, request.user)
    ):
        messages.warning(
            request,
            "Esta publicação não está atribuída ao seu usuário, mas a revisão permanece acessível com alerta.",
        )

    if request.method == "POST":
        acao = (request.POST.get("acao") or "").strip()
        if acao in {"confirmar_autoria", "rejeitar_autoria"}:
            autoria_id = (request.POST.get("autoria_id") or "").strip()
            autoria = (
                publicacao.autores_publicacao.select_related("autor__usuario_admin", "autor")
                .filter(pk=autoria_id)
                .first()
                if autoria_id.isdigit()
                else None
            )
            if not autoria:
                messages.error(request, "Autoria não encontrada.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            if not autoria.autor.usuario_admin_id or autoria.autor.usuario_admin_id != request.user.id:
                messages.error(request, "Apenas o próprio autor vinculado pode decidir esta atribuição.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)

            if acao == "confirmar_autoria":
                autoria.confirmacao_status = PublicacaoPageAutor.STATUS_CONFIRMACAO_CONFIRMADO
                autoria.confirmado_por = request.user
                autoria.confirmado_em = timezone.now()
                autoria.rejeitado_por = None
                autoria.rejeitado_em = None
                autoria.observacao_confirmacao = ""
                autoria.save(update_fields=[
                    "confirmacao_status",
                    "confirmado_por",
                    "confirmado_em",
                    "rejeitado_por",
                    "rejeitado_em",
                    "observacao_confirmacao",
                ])
                registrar_auditoria(
                    request=request,
                    acao="publicacao_autoria_confirmada",
                    alvo=publicacao,
                    detalhes=f"Autoria confirmada por {request.user.username}: {autoria.autor}.",
                )
                messages.success(request, "Autoria confirmada.")
            else:
                observacao = strip_tags((request.POST.get("observacao_confirmacao") or "").strip())[:2000]
                autoria.confirmacao_status = PublicacaoPageAutor.STATUS_CONFIRMACAO_REJEITADO
                autoria.rejeitado_por = request.user
                autoria.rejeitado_em = timezone.now()
                autoria.observacao_confirmacao = observacao
                autoria.confirmado_por = None
                autoria.confirmado_em = None
                autoria.save(update_fields=[
                    "confirmacao_status",
                    "rejeitado_por",
                    "rejeitado_em",
                    "observacao_confirmacao",
                    "confirmado_por",
                    "confirmado_em",
                ])
                registrar_auditoria(
                    request=request,
                    acao="publicacao_autoria_rejeitada",
                    alvo=publicacao,
                    detalhes=f"Autoria rejeitada por {request.user.username}: {autoria.autor}.",
                )
                messages.success(request, "Autoria rejeitada.")
            return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)

        if acao == "solicitar_revisao":
            if not autor_vinculado or not _publicacao_pertence_ao_autor(publicacao, autor_vinculado):
                messages.error(request, "Apenas o autor vinculado pode solicitar revisão.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            publicacao.status_editorial = PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO
            publicacao.revisao_solicitada_em = timezone.now()
            publicacao.revisao_solicitada_por = request.user
            publicacao.save(update_fields=["status_editorial", "revisao_solicitada_em", "revisao_solicitada_por"])
            revisores_anteriores = (
                PublicacaoRevisao.objects.filter(publicacao=publicacao)
                .exclude(revisor_id=request.user.id)
                .values_list("revisor_id", flat=True)
                .distinct()
            )
            for revisor_id in revisores_anteriores:
                if not PublicacaoRevisao.objects.filter(
                    publicacao=publicacao,
                    revisor_id=revisor_id,
                    decisao=PublicacaoRevisao.DECISAO_PENDENTE,
                ).exists():
                    PublicacaoRevisao.objects.create(
                        publicacao=publicacao,
                        revisor_id=revisor_id,
                        atribuido_por=request.user,
                        modo_atribuicao=PublicacaoRevisao.MODO_MANUAL,
                    )
            _enviar_alerta_publicacao_para_admins(
                publicacao,
                f"[OwnPaper] Publicação aguardando revisão: {publicacao.title}",
                (
                    f"<p>A publicação <strong>{escape(publicacao.title)}</strong> foi enviada para revisão por "
                    f"<strong>{escape(request.user.username)}</strong>.</p>"
                ),
            )
            registrar_auditoria(
                request=request,
                acao="publicacao_solicitou_revisao",
                alvo=publicacao,
                detalhes="Publicação enviada para revisão editorial.",
            )
            messages.success(request, "Publicação enviada para revisão.")
            return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)

        if acao == "atribuir_revisor":
            if not is_admin(request.user):
                messages.error(request, "Apenas admins podem atribuir revisores.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            revisor_ids = [
                int(revisor_id)
                for revisor_id in request.POST.getlist("revisor_ids")
                if str(revisor_id).isdigit()
            ]
            revisores = list(_revisores_eligiveis_para_publicacao(publicacao).filter(pk__in=revisor_ids))
            if not revisores:
                messages.error(request, "Selecione pelo menos um revisor válido.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            criados = []
            for revisor in revisores:
                revisao_pendente = PublicacaoRevisao.objects.filter(
                    publicacao=publicacao,
                    revisor=revisor,
                    decisao=PublicacaoRevisao.DECISAO_PENDENTE,
                ).first()
                if revisao_pendente:
                    continue
                PublicacaoRevisao.objects.create(
                    publicacao=publicacao,
                    revisor=revisor,
                    atribuido_por=request.user,
                    modo_atribuicao=PublicacaoRevisao.MODO_MANUAL,
                )
                criados.append(revisor.username)
            publicacao.status_editorial = PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO
            publicacao.save(update_fields=["status_editorial"])
            registrar_auditoria(
                request=request,
                acao="publicacao_revisores_atribuidos",
                alvo=publicacao,
                detalhes=f"Revisores atribuídos manualmente: {', '.join(criados) or 'nenhum novo'}.",
            )
            if not criados:
                messages.info(request, "Os revisores selecionados já tinham revisões pendentes.")
            else:
                messages.success(
                    request,
                    "Revisor atribuído." if len(criados) == 1 else f"{len(criados)} revisores atribuídos.",
                )
            return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)

        if acao == "sortear_revisor":
            if not is_admin(request.user):
                messages.error(request, "Apenas admins podem sortear revisores.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            quantidade = (request.POST.get("quantidade_revisores") or "1").strip()
            quantidade = int(quantidade) if quantidade.isdigit() else 1
            quantidade = max(1, min(quantidade, 10))
            candidatos = list(
                _revisores_eligiveis_para_publicacao(publicacao).exclude(
                    revisoes_atribuidas__publicacao=publicacao,
                    revisoes_atribuidas__decisao=PublicacaoRevisao.DECISAO_PENDENTE,
                )
            )
            if not candidatos:
                messages.error(request, "Não há revisores elegíveis disponíveis para sorteio.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            sorteados = []
            for _ in range(min(quantidade, len(candidatos))):
                indice = secrets.randbelow(len(candidatos))
                revisor = candidatos.pop(indice)
                PublicacaoRevisao.objects.create(
                    publicacao=publicacao,
                    revisor=revisor,
                    atribuido_por=request.user,
                    modo_atribuicao=PublicacaoRevisao.MODO_ALEATORIA,
                )
                sorteados.append(revisor.username)
            publicacao.status_editorial = PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO
            publicacao.save(update_fields=["status_editorial"])
            registrar_auditoria(
                request=request,
                acao="publicacao_revisores_sorteados",
                alvo=publicacao,
                detalhes=f"Revisores atribuídos aleatoriamente: {', '.join(sorteados)}.",
            )
            messages.success(request, f"Revisores sorteados: {', '.join(sorteados)}.")
            return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)

        if acao == "adicionar_comentario_revisao":
            if not (is_admin(request.user) or is_reviewer(request.user)):
                messages.error(request, "Apenas revisores ou admins podem registrar comentários de revisão.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            trecho = strip_tags((request.POST.get("trecho_revisao") or "").strip())[:2000]
            contexto_antes = strip_tags((request.POST.get("contexto_antes_revisao") or "").strip())[:1000]
            contexto_depois = strip_tags((request.POST.get("contexto_depois_revisao") or "").strip())[:1000]
            sugestao = strip_tags((request.POST.get("sugestao_revisao") or "").strip())[:4000]
            comentario = strip_tags((request.POST.get("comentario_revisao") or "").strip())
            if not trecho:
                messages.error(request, "Selecione um trecho da prévia antes de comentar.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            if not comentario:
                messages.error(request, "Informe o comentário de revisão.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            revisao_pendente = PublicacaoRevisao.objects.filter(
                publicacao=publicacao,
                revisor=request.user,
                decisao=PublicacaoRevisao.DECISAO_PENDENTE,
            ).order_by("-criado_em").first()
            comentario_revisao = PublicacaoComentarioRevisao.objects.create(
                publicacao=publicacao,
                revisao=revisao_pendente,
                criado_por=request.user,
                trecho=trecho,
                contexto_antes=contexto_antes,
                contexto_depois=contexto_depois,
                sugestao=sugestao,
                comentario=comentario,
            )
            registrar_auditoria(
                request=request,
                acao="publicacao_comentario_revisao_criado",
                alvo=publicacao,
                detalhes=f"Comentário de revisão #{comentario_revisao.id} criado por {request.user.username}.",
            )
            _enviar_alerta_publicacao_para_autores(
                publicacao,
                f"[OwnPaper] Novo comentário de revisão: {publicacao.title}",
                (
                    f"<p>Há um novo comentário de revisão na publicação "
                    f"<strong>{escape(publicacao.title)}</strong>.</p>"
                    f"<p>Acesse o fluxo editorial para verificar as marcações e responder aos ajustes.</p>"
                ),
            )
            messages.success(request, "Comentário de revisão registrado.")
            return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)

        if acao == "resolver_comentario_revisao":
            comentario_id = (request.POST.get("comentario_id") or "").strip()
            comentario_revisao = (
                PublicacaoComentarioRevisao.objects.filter(publicacao=publicacao, pk=comentario_id).first()
                if comentario_id.isdigit()
                else None
            )
            if not comentario_revisao:
                messages.error(request, "Comentário de revisão não encontrado.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            autor_pode_resolver = bool(autor_vinculado and _publicacao_pertence_ao_autor(publicacao, autor_vinculado))
            if not (is_admin(request.user) or is_reviewer(request.user) or autor_pode_resolver):
                messages.error(request, "Você não pode resolver comentários desta publicação.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            comentario_revisao.resolvido = True
            comentario_revisao.resolvido_por = request.user
            comentario_revisao.resolvido_em = timezone.now()
            comentario_revisao.save(update_fields=["resolvido", "resolvido_por", "resolvido_em"])
            registrar_auditoria(
                request=request,
                acao="publicacao_comentario_revisao_resolvido",
                alvo=publicacao,
                detalhes=f"Comentário de revisão #{comentario_revisao.id} marcado como resolvido por {request.user.username}.",
            )
            messages.success(request, "Comentário marcado como resolvido.")
            return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)

        if acao == "decidir_revisao":
            if not (is_admin(request.user) or is_reviewer(request.user)):
                messages.error(request, "Apenas revisores ou admins podem decidir revisões.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            if not is_admin(request.user) and autor_vinculado and _publicacao_pertence_ao_autor(publicacao, autor_vinculado):
                messages.error(request, "Revisores não podem aprovar o próprio conteúdo.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            decisao = (request.POST.get("decisao") or "").strip()
            observacoes = (request.POST.get("observacoes_revisao") or "").strip()
            if decisao not in {
                PublicacaoRevisao.DECISAO_APROVAR,
                PublicacaoRevisao.DECISAO_AJUSTES,
                PublicacaoRevisao.DECISAO_REJEITAR,
            }:
                messages.error(request, "Escolha uma decisão válida.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            revisao = PublicacaoRevisao.objects.filter(
                publicacao=publicacao,
                revisor=request.user,
                decisao=PublicacaoRevisao.DECISAO_PENDENTE,
            ).order_by("-criado_em").first()
            if revisao is None:
                revisao = PublicacaoRevisao.objects.create(
                    publicacao=publicacao,
                    revisor=request.user,
                    atribuido_por=request.user if is_admin(request.user) else None,
                    modo_atribuicao=PublicacaoRevisao.MODO_MANUAL,
                )
            revisao.decisao = decisao
            revisao.observacoes = observacoes
            revisao.concluido_em = timezone.now()
            revisao.save()
            if decisao == PublicacaoRevisao.DECISAO_APROVAR:
                revisoes_pendentes = _revisoes_pendentes_publicacao(publicacao)
                if revisoes_pendentes.exists():
                    publicacao.status_editorial = PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO
                    publicacao.save(update_fields=["status_editorial"])
                    status_resultado = PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO
                    erro_publicacao = ""
                else:
                    status_resultado, erro_publicacao = _publicar_ou_agendar_publicacao_aprovada(
                        publicacao,
                        request.user,
                    )
                    if erro_publicacao:
                        messages.error(request, erro_publicacao)
                        return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
                    if _publicacao_tem_autoria_pendente(publicacao) and is_admin(request.user):
                        messages.warning(
                            request,
                            (
                                "Há autoria pendente de confirmação. Até o autor confirmar, "
                                f"a publicação será exibida no nome do usuário {request.user.get_username()}."
                            ),
                        )
                        registrar_auditoria(
                            request=request,
                            acao="publicacao_publicada_com_autoria_pendente",
                            alvo=publicacao,
                            detalhes=(
                                "Admin publicou via fluxo editorial com autoria pendente; "
                                f"exibição pública temporária no usuário {request.user.get_username()}."
                            ),
                        )
            elif decisao == PublicacaoRevisao.DECISAO_AJUSTES:
                publicacao.status_editorial = PublicacaoPage.STATUS_EDITORIAL_AJUSTES
                publicacao.save(update_fields=["status_editorial"])
                _enviar_alerta_publicacao_para_autores(
                    publicacao,
                    f"[OwnPaper] Ajustes solicitados: {publicacao.title}",
                    (
                        f"<p>A publicação <strong>{escape(publicacao.title)}</strong> recebeu solicitação "
                        f"de ajustes por <strong>{escape(request.user.username)}</strong>.</p>"
                        f"<p>Consulte o fluxo editorial para ver comentários, sugestões e observações.</p>"
                    ),
                )
            else:
                publicacao.status_editorial = PublicacaoPage.STATUS_EDITORIAL_REJEITADO
                publicacao.save(update_fields=["status_editorial"])
                _enviar_alerta_publicacao_para_autores(
                    publicacao,
                    f"[OwnPaper] Publicação rejeitada: {publicacao.title}",
                    (
                        f"<p>A publicação <strong>{escape(publicacao.title)}</strong> foi rejeitada por "
                        f"<strong>{escape(request.user.username)}</strong>.</p>"
                        f"<p>Consulte o fluxo editorial para ver as observações registradas.</p>"
                    ),
                )
            registrar_auditoria(
                request=request,
                acao="publicacao_revisao_decidida",
                alvo=publicacao,
                detalhes=f"Decisão {decisao} por {request.user.username}.",
            )
            if decisao == PublicacaoRevisao.DECISAO_APROVAR:
                revisoes_pendentes_count = _revisoes_pendentes_publicacao(publicacao).count()
                if status_resultado == PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO:
                    messages.success(
                        request,
                        f"Aprovação registrada. Ainda há {revisoes_pendentes_count} revisão(ões) pendente(s).",
                    )
                    return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
                if status_resultado == PublicacaoPage.STATUS_EDITORIAL_AGENDADO:
                    mensagem_status = "aprovada e agendada para publicação"
                    assunto = f"[OwnPaper] Publicação agendada após revisão: {publicacao.title}"
                else:
                    mensagem_status = "aprovada e publicada"
                    assunto = f"[OwnPaper] Publicação publicada após revisão: {publicacao.title}"
                _enviar_alerta_publicacao_para_admins_e_revisores(
                    publicacao,
                    assunto,
                    (
                        f"<p>A publicação <strong>{escape(publicacao.title)}</strong> foi "
                        f"{mensagem_status} por <strong>{escape(request.user.username)}</strong>.</p>"
                    ),
                )
                messages.success(request, f"Publicação {mensagem_status}.")
            else:
                messages.success(request, "Decisão de revisão registrada.")
            return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)

        if acao == "solicitar_reabertura":
            if not autor_vinculado or not _publicacao_pertence_ao_autor(publicacao, autor_vinculado):
                messages.error(request, "Apenas o autor vinculado pode solicitar reabertura.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            publicacao.reabertura_solicitada = True
            publicacao.reabertura_solicitada_em = timezone.now()
            publicacao.reabertura_solicitada_por = request.user
            publicacao.save(update_fields=["reabertura_solicitada", "reabertura_solicitada_em", "reabertura_solicitada_por"])
            registrar_auditoria(
                request=request,
                acao="publicacao_solicitou_reabertura",
                alvo=publicacao,
                detalhes="Autor solicitou reabertura da publicação.",
            )
            messages.success(request, "Solicitação de reabertura registrada.")
            return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)

        if acao == "liberar_reabertura":
            if not (is_admin(request.user) or is_reviewer(request.user)):
                messages.error(request, "Apenas revisores ou admins podem liberar reabertura.")
                return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)
            publicacao.reabertura_solicitada = False
            publicacao.status_editorial = PublicacaoPage.STATUS_EDITORIAL_AJUSTES
            publicacao.save(update_fields=["reabertura_solicitada", "status_editorial"])
            registrar_auditoria(
                request=request,
                acao="publicacao_reabertura_liberada",
                alvo=publicacao,
                detalhes=f"Reabertura liberada por {request.user.username}.",
            )
            messages.success(request, "Reabertura liberada para edição.")
            return redirect("admin_publicacao_fluxo_editorial", publicacao_id=publicacao.id)

    return render(
        request,
        "conteudo/admin_publicacao_fluxo_editorial.html",
        {
            "publicacao": publicacao,
            "autor_vinculado": autor_vinculado,
            "revisoes": publicacao.revisoes.select_related("revisor", "atribuido_por").all(),
            "revisores_eligiveis": _revisores_eligiveis_para_publicacao(publicacao),
            "is_admin": is_admin(request.user),
            "is_reviewer": is_reviewer(request.user),
            "pode_editar_publicacao": _usuario_pode_editar_publicacao_no_wagtail(request.user, publicacao),
            "comentarios_revisao": publicacao.comentarios_revisao.select_related(
                "criado_por",
                "resolvido_por",
            ).all(),
            "revisao_atribuida_ao_usuario": _revisao_atribuida_para_usuario(publicacao, request.user),
            "revisoes_pendentes_count": _revisoes_pendentes_publicacao(publicacao).count(),
        },
    )


def _autor_vinculado_do_usuario(user):
    if not user.is_authenticated or user.is_superuser:
        return None

    return Autor.objects.filter(usuario_admin=user).first()


def _autor_vinculado_do_usuario_incluindo_admin(user):
    if not user or not user.is_authenticated:
        return None
    return Autor.objects.filter(usuario_admin=user).first()


def _publicacao_pertence_ao_autor(publicacao, autor):
    if not autor:
        return False

    return publicacao.autores_publicacao.filter(
        autor=autor,
        confirmacao_status=PublicacaoPageAutor.STATUS_CONFIRMACAO_CONFIRMADO,
    ).exists()


def _autores_enviados_no_formulario(request):
    if request.method != "POST":
        return []

    autores_ids = []
    for key, value in request.POST.items():
        if key.startswith("autores_publicacao-") and key.endswith("-autor"):
            val = (value or "").strip()
            if val.isdigit():
                autores_ids.append(int(val))
    return autores_ids


def _site_atual(request):
    return (
        Site.find_for_request(request)
        or Site.objects.filter(is_default_site=True).first()
        or Site.objects.first()
    )


def _trava_publicacao_orcid_ativa(request):
    site = _site_atual(request)
    if not site:
        return False
    return bool(ConfiguracaoSite.for_site(site).travar_publicacao_por_orcid)


def _tem_autor_sem_orcid(publicacao):
    return publicacao.autores_publicacao.filter(
        Q(autor__orcid__isnull=True) | Q(autor__orcid__exact="")
    ).exists()


def _publicacao_tem_dependencias_editoriais_pendentes(publicacao):
    if publicacao.autores_publicacao.filter(
        confirmacao_status=PublicacaoPageAutor.STATUS_CONFIRMACAO_REJEITADO
    ).exists():
        return "Há autoria rejeitada nesta publicação. Ajuste os autores antes de publicar."

    if publicacao.autores_publicacao.filter(
        confirmacao_status=PublicacaoPageAutor.STATUS_CONFIRMACAO_PENDENTE
    ).exists():
        return "Há autoria pendente de confirmação nesta publicação."

    if (
        publicacao.categoria_principal_id
        and getattr(publicacao.categoria_principal, "aprovacao_status", "") != Categoria.STATUS_APROVADO
    ):
        return "A categoria principal da publicação ainda não foi aprovada."

    tags_pendentes = publicacao.tags.exclude(aprovacao_status=TagPublicacao.STATUS_APROVADO)
    if tags_pendentes.exists():
        return "Há tags editoriais vinculadas que ainda não foram aprovadas."

    perguntas_pendentes = publicacao.quiz_perguntas_reutilizaveis.exclude(
        pergunta__aprovacao_status=PerguntaQuizCatalogo.STATUS_APROVADO
    )
    if perguntas_pendentes.exists():
        return "Há perguntas do quiz vinculadas que ainda não foram aprovadas."

    return ""


def _publicacao_tem_autoria_pendente(publicacao):
    return publicacao.autores_publicacao.filter(
        confirmacao_status=PublicacaoPageAutor.STATUS_CONFIRMACAO_PENDENTE
    ).exists()


def _publicacao_tem_autoria_rejeitada(publicacao):
    return publicacao.autores_publicacao.filter(
        confirmacao_status=PublicacaoPageAutor.STATUS_CONFIRMACAO_REJEITADO
    ).exists()


def _publicacao_tem_dependencias_editoriais_pendentes_sem_autoria_pendente(publicacao):
    if _publicacao_tem_autoria_rejeitada(publicacao):
        return "Há autoria rejeitada nesta publicação. Ajuste os autores antes de publicar."

    if (
        publicacao.categoria_principal_id
        and getattr(publicacao.categoria_principal, "aprovacao_status", "") != Categoria.STATUS_APROVADO
    ):
        return "A categoria principal da publicação ainda não foi aprovada."

    tags_pendentes = publicacao.tags.exclude(aprovacao_status=TagPublicacao.STATUS_APROVADO)
    if tags_pendentes.exists():
        return "Há tags editoriais vinculadas que ainda não foram aprovadas."

    perguntas_pendentes = publicacao.quiz_perguntas_reutilizaveis.exclude(
        pergunta__aprovacao_status=PerguntaQuizCatalogo.STATUS_APROVADO
    )
    if perguntas_pendentes.exists():
        return "Há perguntas do quiz vinculadas que ainda não foram aprovadas."

    return ""


def _sincronizar_confirmacoes_autoria(request, publicacao, autores_antes=None):
    autores_antes = set(autores_antes or [])
    autores_atuais = set()
    agora = timezone.now()
    user = request.user

    for autoria in publicacao.autores_publicacao.select_related("autor__usuario_admin", "autor").order_by("sort_order"):
        autores_atuais.add(autoria.autor_id)
        update_fields = []
        nova_autoria = autoria.autor_id not in autores_antes

        if not autoria.atribuido_por_id:
            autoria.atribuido_por = user
            update_fields.append("atribuido_por")
        if not autoria.atribuido_em:
            autoria.atribuido_em = agora
            update_fields.append("atribuido_em")

        autor_usuario_id = getattr(autoria.autor, "usuario_admin_id", None)
        if autor_usuario_id == user.id:
            if autoria.confirmacao_status != PublicacaoPageAutor.STATUS_CONFIRMACAO_CONFIRMADO:
                autoria.confirmacao_status = PublicacaoPageAutor.STATUS_CONFIRMACAO_CONFIRMADO
                autoria.confirmado_por = user
                autoria.confirmado_em = agora
                autoria.rejeitado_por = None
                autoria.rejeitado_em = None
                autoria.observacao_confirmacao = ""
                update_fields.extend([
                    "confirmacao_status",
                    "confirmado_por",
                    "confirmado_em",
                    "rejeitado_por",
                    "rejeitado_em",
                    "observacao_confirmacao",
                ])
                registrar_auditoria(
                    request=request,
                    acao="publicacao_autoria_confirmada_auto",
                    alvo=publicacao,
                    detalhes=f"Autoria confirmada automaticamente para {autoria.autor}.",
                )
        elif nova_autoria:
            autoria.confirmacao_status = PublicacaoPageAutor.STATUS_CONFIRMACAO_PENDENTE
            autoria.confirmado_por = None
            autoria.confirmado_em = None
            autoria.rejeitado_por = None
            autoria.rejeitado_em = None
            autoria.observacao_confirmacao = ""
            update_fields.extend([
                "confirmacao_status",
                "confirmado_por",
                "confirmado_em",
                "rejeitado_por",
                "rejeitado_em",
                "observacao_confirmacao",
            ])
            registrar_auditoria(
                request=request,
                acao="publicacao_autoria_atribuida_pendente",
                alvo=publicacao,
                detalhes=f"Autoria atribuída a {autoria.autor}; aguardando confirmação do autor.",
            )

        if update_fields:
            autoria.save(update_fields=sorted(set(update_fields)))

    autores_removidos = autores_antes - autores_atuais
    for autor_id in autores_removidos:
        autor = Autor.objects.filter(pk=autor_id).first()
        registrar_auditoria(
            request=request,
            acao="publicacao_autoria_removida",
            alvo=publicacao,
            detalhes=f"Autoria removida: {autor or autor_id}.",
        )


def _autoria_alterada_no_formulario(publicacao, autores_ids_formulario):
    if not autores_ids_formulario:
        return False
    autores_atuais = set(
        publicacao.autores_publicacao.values_list("autor_id", flat=True)
    )
    autores_enviados = set(autores_ids_formulario)
    return autores_atuais != autores_enviados


def _bloquear_com_mensagem(request, mensagem):
    messages.error(request, mensagem)
    return redirect("admin_publicacoes_lista")


def navegacao_admin_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "A configuração de navegação é restrita a administradores.",
        )

    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    if not site:
        messages.error(request, "Site não encontrado.")
        return redirect("/admin/")

    config = ConfiguracaoSite.for_site(site)
    menu_grupos = config.menu_grupos.all().prefetch_related("subitens")
    rodape_links = config.rodape_links.all()

    return render(
        request,
        "conteudo/admin_navegacao.html",
        {
            "site": site,
            "config_site": config,
            "menu_grupos": menu_grupos,
            "rodape_links": rodape_links,
        },
    )


def backups_admin_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "A área de backups é restrita a administradores.",
        )

    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    if not site:
        messages.error(request, "Site não encontrado.")
        return redirect("/admin/")

    config = ConfiguracaoSite.for_site(site)

    if request.method == "POST":
        acao = (request.POST.get("acao") or "").strip()
        if acao == "salvar_config":
            erros_config = []
            email_destino = strip_tags((request.POST.get("backup_email_destino") or "").strip())[:254]
            enviar_relatorio = request.POST.get("backup_enviar_relatorio") == "on"

            if email_destino:
                try:
                    validate_email(email_destino)
                except ValidationError:
                    erros_config.append("Informe um e-mail de backup válido.")
            if enviar_relatorio and not email_destino:
                erros_config.append("Informe o e-mail de destino para enviar relatórios de backup.")
            if erros_config:
                for erro in erros_config:
                    messages.error(request, erro)
                return redirect("admin_backups")

            config.backup_email_destino = email_destino
            config.backup_enviar_relatorio = enviar_relatorio
            config.save(
                update_fields=[
                    "backup_email_destino",
                    "backup_enviar_relatorio",
                ]
            )
            registrar_auditoria(
                request=request,
                acao="backup_config_atualizada",
                alvo=config,
                detalhes=f"email={email_destino}; relatorio={enviar_relatorio}.",
            )
            messages.success(request, "Configuração de relatório de backup salva.")
            return redirect("admin_backups")

        if acao == "solicitar_backup":
            erros_backup = []
            escopo = (request.POST.get("escopo") or "").strip()
            senha_atual = request.POST.get("senha_atual") or ""
            token_2fa = request.POST.get("token_2fa") or ""
            confirmou = request.POST.get("confirmar_backup") == "on"

            if escopo not in {item[0] for item in BACKUP_SCOPE_CHOICES}:
                erros_backup.append("Selecione um escopo de backup válido.")
            if not request.user.check_password(senha_atual):
                erros_backup.append("A senha atual informada está incorreta.")
            if not usuario_tem_totp(request.user):
                erros_backup.append("Configure o autenticador em duas etapas antes de solicitar backups pelo painel.")
            else:
                token_valido, mensagem_token = validar_token_2fa_conta(request.user, token_2fa)
                if not token_valido:
                    erros_backup.append(mensagem_token or "Código do autenticador inválido.")
            if not confirmou:
                erros_backup.append("Confirme que entende que o backup será gerado no servidor.")

            if erros_backup:
                for erro in erros_backup:
                    messages.error(request, erro)
                return redirect("admin_backups")

            execucao = criar_solicitacao_backup_painel(site, request.user, escopo)
            registrar_auditoria(
                request=request,
                acao="backup_painel_solicitado",
                alvo=execucao,
                detalhes=f"escopo={escopo}; label={label_escopo_backup(escopo)}.",
            )
            messages.success(
                request,
                "Backup solicitado e colocado na fila. A execução será feita pelo scheduler sem bloquear o painel.",
            )
            return redirect("admin_backups")

        if acao in {"executar_backup_total", "gerar_download"}:
            erros_confirmacao = _validar_confirmacao_backup_sensivel(request)
            if erros_confirmacao:
                for erro in erros_confirmacao:
                    messages.error(request, erro)
                return redirect("admin_backups")

            if acao == "executar_backup_total":
                execucao = criar_solicitacao_backup_painel(site, request.user, "total")
                registrar_auditoria(
                    request=request,
                    acao="backup_externo_total_solicitado",
                    alvo=execucao,
                    detalhes="Backup total solicitado pela tela de backups.",
                )
                messages.success(request, "Backup total colocado na fila. O scheduler executará e enviará ao WebDAV se estiver configurado.")
                return redirect("admin_backups")

            if acao == "gerar_download":
                backup_id = request.POST.get("backup_id")
                backup = BackupExecucao.objects.filter(id=backup_id, site=site, status=BackupExecucao.STATUS_CONCLUIDO).first()
                if not backup or not backup.arquivo_caminho or not Path(backup.arquivo_caminho).exists():
                    messages.error(request, "Backup indisponível para download.")
                    return redirect("admin_backups")
                token, _expira_em = gerar_token_download_backup(backup, origem="painel", horas_validade=1)
                registrar_auditoria(
                    request=request,
                    acao="backup_download_temporario_gerado",
                    alvo=backup,
                    detalhes="Link temporário de download gerado após senha e 2FA.",
                )
                return redirect("admin_backup_download", backup_id=backup.id, token=token)

        messages.error(request, "Ação de backup não reconhecida.")
        return redirect("admin_backups")

    historico = BackupExecucao.objects.filter(site=site).select_related("solicitado_por")[:30]
    return render(
        request,
        "conteudo/admin_backups.html",
        {
            "site": site,
            "config_site": config,
            "backup_backend_config": _backup_backend_config(config=config),
            "backup_scope_choices": BACKUP_SCOPE_CHOICES,
            "historico": historico,
        },
    )


def _validar_confirmacao_backup_sensivel(request):
    erros = []
    senha_atual = request.POST.get("senha_atual") or ""
    token_2fa = request.POST.get("token_2fa") or ""
    if not request.user.check_password(senha_atual):
        erros.append("A senha atual informada está incorreta.")
    if not usuario_tem_totp(request.user):
        erros.append("Configure o autenticador em duas etapas antes de alterar backups.")
    else:
        token_valido, mensagem_token = validar_token_2fa_conta(request.user, token_2fa)
        if not token_valido:
            erros.append(mensagem_token or "Código do autenticador inválido.")
    return erros


def backup_download_temporario_admin_view(request, backup_id, token):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(request, "Download de backup restrito a administradores.")

    backup = get_object_or_404(BackupExecucao, id=backup_id, status=BackupExecucao.STATUS_CONCLUIDO)
    detalhes = dict(backup.detalhes or {})
    download_manual = dict(detalhes.get("download_manual") or {})
    token_hash = hashlib.sha256((token or "").encode("utf-8")).hexdigest()
    if not token or download_manual.get("token_hash") != token_hash:
        messages.error(request, "Link temporário de backup inválido.")
        return redirect("admin_backups")
    if download_manual.get("usado_em"):
        messages.error(request, "Este link de backup já foi utilizado.")
        return redirect("admin_backups")
    expira_em_raw = download_manual.get("expira_em") or ""
    expira_em = None
    if expira_em_raw:
        try:
            expira_em = timezone.datetime.fromisoformat(expira_em_raw)
            if timezone.is_naive(expira_em):
                expira_em = timezone.make_aware(expira_em)
        except (TypeError, ValueError):
            expira_em = None
    if not expira_em or timezone.now() > expira_em:
        messages.error(request, "Link temporário de backup expirado.")
        return redirect("admin_backups")
    caminho = Path(backup.arquivo_caminho)
    if not caminho.exists() or caminho.suffix != ".zip":
        messages.error(request, "Arquivo de backup não encontrado.")
        return redirect("admin_backups")
    if backup.checksum_sha256:
        from conteudo.backup_ops import _sha256_arquivo

        if _sha256_arquivo(caminho) != backup.checksum_sha256:
            messages.error(request, "Checksum do backup mudou desde a geração do link.")
            return redirect("admin_backups")

    if request.method != "POST":
        return render(
            request,
            "conteudo/admin_backup_download_confirm.html",
            {
                "backup": backup,
                "expira_em": expira_em,
            },
        )

    erros = _validar_confirmacao_backup_sensivel(request)
    confirmar = request.POST.get("confirmar_download") == "on"
    if not confirmar:
        erros.append("Confirme que entende que o download expõe um backup completo ou parcial do sistema.")
    if erros:
        for erro in erros:
            messages.error(request, erro)
        return redirect("admin_backup_download", backup_id=backup.id, token=token)

    download_manual["usado_em"] = timezone.now().isoformat()
    download_manual["usado_por_id"] = request.user.id
    detalhes["download_manual"] = download_manual
    backup.detalhes = detalhes
    backup.save(update_fields=["detalhes"])

    registrar_auditoria(
        request=request,
        acao="backup_download_temporario_usado",
        alvo=backup,
        detalhes=f"arquivo={caminho.name}; tamanho={backup.arquivo_tamanho_bytes}.",
    )
    return FileResponse(open(caminho, "rb"), as_attachment=True, filename=caminho.name)


def saude_operacional_admin_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "A saúde operacional é restrita a administradores.",
        )

    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    resultado = avaliar_saude_operacional(site=site)
    return render(
        request,
        "conteudo/admin_saude_operacional.html",
        {
            "resultado": resultado,
            "site": site,
        },
    )


def configuracoes_site_admin_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "As configurações do site são restritas a administradores.",
        )

    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    if not site:
        return redirect("/admin/")

    config = ConfiguracaoSite.for_site(site)
    secoes = []
    for item in CONFIG_SITE_SECTION_DEFS:
        secao = item.copy()
        secao["url"] = reverse("admin_configuracoes_site_secao", args=[item["slug"]])
        secoes.append(secao)

    return render(
        request,
        "conteudo/admin_configuracoes_site_hub.html",
        {
            "site": site,
            "config_site": config,
            "secoes": secoes,
            "url_admin_inicio": reverse("wagtailadmin_home"),
        },
    )


def configuracoes_site_secao_admin_view(request, secao_slug):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "As configurações do site são restritas a administradores.",
        )

    site = _resolver_site_admin(request)
    if not site:
        return redirect("/admin/")

    section_def = _config_site_section_map().get(secao_slug)
    if not section_def:
        messages.error(request, "Seção de configuração não encontrada.")
        return redirect("admin_configuracoes_site")

    config = ConfiguracaoSite.for_site(site)
    form_class = _criar_form_configuracao_site(section_def)
    form = form_class(request.POST or None, request.FILES or None, instance=config)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            registrar_auditoria(
                request=request,
                acao="configuracao_site_secao_atualizada",
                alvo=config,
                detalhes=f"Seção atualizada: {section_def['slug']}.",
            )
            messages.success(request, "Seção atualizada com sucesso.")
            return redirect("admin_configuracoes_site_secao", secao_slug=secao_slug)
        messages.error(request, "Corrija os campos destacados.")

    secoes = []
    for item in CONFIG_SITE_SECTION_DEFS:
        secao = item.copy()
        secao["url"] = reverse("admin_configuracoes_site_secao", args=[item["slug"]])
        secao["ativa"] = item["slug"] == secao_slug
        secoes.append(secao)

    campos_readonly = []
    for nome in section_def.get("readonly_campos", []):
        field = config._meta.get_field(nome)
        valor = getattr(config, nome)
        campos_readonly.append(
            {
                "label": field.verbose_name,
                "valor": valor if valor not in ("", None) else "—",
            }
        )

    links_extras = []
    for item in section_def.get("links_extras", []):
        links_extras.append(
            {
                "label": item["label"],
                "url": reverse(item["url_name"]),
            }
        )

    return render(
        request,
        "conteudo/admin_configuracoes_site_secao.html",
        {
            "site": site,
            "config_site": config,
            "secao": section_def,
            "form": form,
            "secoes": secoes,
            "campos_readonly": campos_readonly,
            "links_extras": links_extras,
        },
    )


def configuracoes_site_imagem_preview_admin_view(request, image_id):
    if not _pode_acessar_admin_superuser(request.user):
        return JsonResponse({"error": "Acesso negado."}, status=403)

    spec = request.GET.get("spec") or "fill-320x180"
    specs_permitidas = {"fill-320x180", "fill-96x96", "max-320x140"}
    if spec not in specs_permitidas:
        return JsonResponse({"error": "Tamanho de preview inválido."}, status=400)

    ImageModel = get_image_model()
    imagem = get_object_or_404(ImageModel, id=image_id)
    try:
        rendition = imagem.get_rendition(spec)
        url = rendition.url
    except Exception:
        url = imagem.file.url if imagem.file else ""

    return JsonResponse(
        {
            "id": imagem.id,
            "title": imagem.title,
            "url": url,
        }
    )


def configuracoes_home_admin_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "As configurações da home são restritas a administradores.",
        )

    home = HomePage.objects.first()
    if not home:
        messages.error(request, "Página Início não encontrada.")
        return redirect("/admin/")

    return render(
        request,
        "conteudo/admin_home_central.html",
        {
            "home": home,
            "url_home_explorador": reverse("wagtailadmin_explore", args=[home.id]),
            "url_home_editar": reverse("wagtailadmin_pages:edit", args=[home.id]),
            "url_publicacoes": reverse("admin_publicacoes_lista"),
            "url_admin_inicio": reverse("wagtailadmin_home"),
        },
    )


def usuarios_reset_senha_admin_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "O disparo de reset de senha é restrito a administradores.",
        )

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()

        if not email:
            messages.error(request, "Informe um e-mail válido.")
            return redirect("admin_usuarios_reset_senha")

        form = PasswordResetForm({"email": email})
        if form.is_valid():
            form.save(
                request=request,
                from_email=settings.DEFAULT_FROM_EMAIL,
                use_https=request.is_secure(),
                subject_template_name="registration/password_reset_subject.txt",
                email_template_name="registration/password_reset_email.txt",
                html_email_template_name="registration/password_reset_email.html",
            )
            registrar_auditoria(
                request=request,
                acao="usuario_disparou_reset_senha",
                detalhes=f"E-mail alvo: {email}",
            )

        messages.success(
            request,
            "Se o e-mail existir, o link de redefinição foi enviado.",
        )
        return redirect("admin_usuarios_reset_senha")

    return render(
        request,
        "conteudo/admin_usuarios_reset_senha.html",
        {},
    )


def usuarios_reset_2fa_admin_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "O reset de 2FA é restrito a administradores.",
        )

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        if not email:
            messages.error(request, "Informe um e-mail válido.")
            return redirect("admin_usuarios_reset_2fa")

        User = get_user_model()
        usuario = User.objects.filter(email__iexact=email).first()
        if not usuario:
            registrar_auditoria(
                request=request,
                acao="usuario_reset_2fa_tentativa_sem_usuario",
                detalhes=f"E-mail informado: {email}",
            )
            messages.success(
                request,
                "Se o usuário existir, o 2FA foi redefinido e o aviso foi enviado.",
            )
            return redirect("admin_usuarios_reset_2fa")

        total_totp = TOTPDevice.objects.filter(user=usuario).count()
        total_backup = StaticToken.objects.filter(device__user=usuario).count()
        StaticDevice.objects.filter(user=usuario).delete()
        TOTPDevice.objects.filter(user=usuario).delete()

        assunto = "2FA redefinido pelo administrador"
        url_login = f"{getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/')}/account/login/"
        corpo = (
            "<p>O acesso em duas etapas (2FA) da sua conta foi redefinido por um administrador.</p>"
            "<p>No próximo acesso ao painel, você deverá configurar um novo autenticador.</p>"
            f"<p><a href=\"{url_login}\">Acessar login</a></p>"
        )
        email_msg = EmailMessage(
            subject=assunto,
            body=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[usuario.email],
        )
        email_msg.content_subtype = "html"
        try:
            email_msg.send(fail_silently=False)
        except Exception:
            messages.warning(
                request,
                "2FA redefinido, mas não foi possível enviar o e-mail de aviso.",
            )

        registrar_auditoria(
            request=request,
            acao="usuario_reset_2fa_admin",
            alvo=usuario,
            detalhes=(
                f"Reset de 2FA executado. Dispositivos TOTP removidos: {total_totp}. "
                f"Códigos de backup removidos: {total_backup}."
            ),
        )
        messages.success(
            request,
            "2FA redefinido com sucesso. O usuário precisará configurar novamente no próximo login.",
        )
        return redirect("admin_usuarios_reset_2fa")

    return render(
        request,
        "conteudo/admin_usuarios_reset_2fa.html",
        {},
    )


def logs_atividade_admin_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "Os logs de atividade são restritos a administradores.",
        )

    filtro_q = (request.GET.get("q") or "").strip()
    filtro_acao = (request.GET.get("acao") or "").strip()
    filtro_usuario = (request.GET.get("usuario") or "").strip()
    exportar_csv = request.GET.get("export") == "csv"

    logs = AuditLog.objects.select_related("usuario").all()

    if filtro_q:
        logs = logs.filter(
            Q(detalhes__icontains=filtro_q)
            | Q(alvo_repr__icontains=filtro_q)
            | Q(usuario_email__icontains=filtro_q)
            | Q(usuario_username__icontains=filtro_q)
        )

    if filtro_acao:
        logs = logs.filter(acao=filtro_acao)

    if filtro_usuario.isdigit():
        logs = logs.filter(usuario_id_ref=int(filtro_usuario))

    if exportar_csv:
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="logs_atividade.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "sequencia",
                "criado_em",
                "assinado_em",
                "acao",
                "usuario_id",
                "usuario_username",
                "usuario_email",
                "alvo_tipo",
                "alvo_id",
                "alvo",
                "ip",
                "detalhes",
                "hash_anterior",
                "hash_registro",
            ]
        )
        for log in logs.order_by("-criado_em"):
            writer.writerow(
                [
                    log.sequencia or "",
                    log.criado_em.isoformat(),
                    log.assinado_em.isoformat() if log.assinado_em else "",
                    log.acao,
                    log.usuario_id_ref or "",
                    log.usuario_username,
                    log.usuario_email,
                    log.alvo_tipo,
                    log.alvo_id,
                    log.alvo_repr,
                    log.ip,
                    log.detalhes,
                    log.hash_anterior,
                    log.hash_registro,
                ]
            )
        return response

    integridade_logs = AuditLog.verificar_integridade()
    acoes_disponiveis = (
        AuditLog.objects.values_list("acao", flat=True).distinct().order_by("acao")
    )
    paginator = Paginator(logs, 30)
    pagina_atual = paginator.get_page(request.GET.get("pagina"))
    qs = request.GET.copy()
    qs.pop("pagina", None)

    return render(
        request,
        "conteudo/admin_logs_atividade.html",
        {
            "logs": pagina_atual,
            "filtro_q": filtro_q,
            "filtro_acao": filtro_acao,
            "filtro_usuario": filtro_usuario,
            "acoes_disponiveis": acoes_disponiveis,
            "query_string_sem_pagina": qs.urlencode(),
            "integridade_logs": integridade_logs,
        },
    )


def _formatar_duracao_curta(segundos):
    segundos = int(segundos or 0)
    minutos, resto = divmod(segundos, 60)
    horas, minutos = divmod(minutos, 60)
    if horas:
        return f"{horas}h {minutos}min"
    if minutos:
        return f"{minutos}min {resto}s"
    return f"{resto}s"


def estatisticas_admin_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "As estatísticas do site são restritas a administradores.",
        )

    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    config = ConfiguracaoSite.for_site(site) if site else None

    leituras_total = PublicacaoPage.objects.aggregate(total=Sum("total_visualizacoes"))["total"] or 0
    publicacoes_total = PublicacaoPage.objects.count()
    publicacoes_publicadas = PublicacaoPage.objects.filter(
        status_editorial=PublicacaoPage.STATUS_EDITORIAL_PUBLICADO
    ).count()
    comentarios_total = ComentarioPublicacao.objects.count()
    comentarios_pendentes = ComentarioPublicacao.objects.filter(
        status=ComentarioPublicacao.STATUS_PENDENTE
    ).count()
    mensagens_total = MensagemContato.objects.count()
    mensagens_pendentes = MensagemContato.objects.filter(
        status__in=[MensagemContato.STATUS_NOVO, MensagemContato.STATUS_EM_ANDAMENTO]
    ).count()
    destinos_agregado = DisparoEmailDestino.objects.aggregate(
        enviados=Count("id", filter=Q(status=DisparoEmailDestino.STATUS_ENVIADO)),
        falhas=Count("id", filter=Q(status=DisparoEmailDestino.STATUS_FALHOU)),
        aberturas=Sum("total_aberturas"),
        cliques=Sum("total_cliques"),
    )
    tempo_agregado = EstatisticaTempoSite.objects.filter(duration_seconds__gte=5).aggregate(
        media=Avg("duration_seconds"),
        total=Count("id"),
    )
    agregado_diario = EstatisticaDiariaSite.objects.aggregate(
        sessoes=Sum("sessoes"),
        tempo_total=Sum("tempo_total_seconds"),
    )
    sessoes_agregadas = agregado_diario["sessoes"] or 0
    tempo_total_agregado = agregado_diario["tempo_total"] or 0
    tempo_medio_agregado = (
        tempo_total_agregado / sessoes_agregadas
        if sessoes_agregadas
        else (tempo_agregado["media"] or 0)
    )
    top_tempo = (
        EstatisticaDiariaSite.objects.values("path")
        .annotate(
            sessoes_total=Sum("sessoes"),
            tempo_total=Sum("tempo_total_seconds"),
        )
        .order_by("-sessoes_total", "path")[:8]
    )

    top_publicacoes = (
        PublicacaoPage.objects.live()
        .filter(status_editorial=PublicacaoPage.STATUS_EDITORIAL_PUBLICADO)
        .annotate(comentarios_total=Count("comentarios_publicacao"))
        .order_by("-total_visualizacoes", "title")[:8]
    )
    top_comentadas = (
        PublicacaoPage.objects.live()
        .filter(status_editorial=PublicacaoPage.STATUS_EDITORIAL_PUBLICADO)
        .annotate(
            comentarios_total=Count("comentarios_publicacao")
        )
        .filter(comentarios_total__gt=0)
        .order_by("-comentarios_total", "title")[:8]
    )

    def _status_rows(model, queryset):
        labels = dict(getattr(model, "STATUS_CHOICES", []))
        return [
            {"status": labels.get(row["status"], row["status"]), "total": row["total"]}
            for row in queryset.values("status").annotate(total=Count("id")).order_by("status")
        ]

    status_editorial_labels = dict(PublicacaoPage.STATUS_EDITORIAL_CHOICES)
    publicacoes_status = [
        {"status": status_editorial_labels.get(row["status_editorial"], row["status_editorial"]), "total": row["total"]}
        for row in PublicacaoPage.objects.values("status_editorial")
        .annotate(total=Count("id"))
        .order_by("status_editorial")
    ]

    return render(
        request,
        "conteudo/admin_estatisticas.html",
        {
            "metricas": {
                "leituras_total": leituras_total,
                "publicacoes_total": publicacoes_total,
                "publicacoes_publicadas": publicacoes_publicadas,
                "comentarios_total": comentarios_total,
                "comentarios_pendentes": comentarios_pendentes,
                "mensagens_total": mensagens_total,
                "mensagens_pendentes": mensagens_pendentes,
                "usuarios_ativos": get_user_model().objects.filter(is_active=True).count(),
                "usuarios_total": get_user_model().objects.count(),
                "newsletter_ativos": InscritoNewsletter.objects.filter(ativo=True).count(),
                "emails_enviados_total": destinos_agregado["enviados"] or 0,
                "emails_falhas_total": destinos_agregado["falhas"] or 0,
                "emails_aberturas_total": destinos_agregado["aberturas"] or 0,
                "emails_cliques_total": destinos_agregado["cliques"] or 0,
                "tempo_medio_site": _formatar_duracao_curta(tempo_medio_agregado),
                "tempo_amostras_total": sessoes_agregadas or tempo_agregado["total"] or 0,
            },
            "estatisticas_config": {
                "internas_ativas": bool(config and config.estatisticas_internas_ativas),
                "retencao_agregados": config.estatisticas_reter_agregados_dias if config else 365,
                "retencao_brutos": config.estatisticas_reter_eventos_brutos_dias if config else 90,
            },
            "top_publicacoes": top_publicacoes,
            "top_comentadas": top_comentadas,
            "top_tempo": top_tempo,
            "publicacoes_status": publicacoes_status,
            "comentarios_status": _status_rows(ComentarioPublicacao, ComentarioPublicacao.objects.all()),
            "mensagens_status": _status_rows(MensagemContato, MensagemContato.objects.all()),
        },
    )


def _contar_admins_ativos(excluir_usuario_id=None):
    queryset = get_user_model().objects.filter(is_active=True, is_staff=True, is_superuser=True)
    if excluir_usuario_id:
        queryset = queryset.exclude(pk=excluir_usuario_id)
    return queryset.count()


def _payload_roles_usuario(request):
    return {
        "papel_admin": request.POST.get("papel_admin") == "1",
        "papel_autor": request.POST.get("papel_autor") == "1",
        "papel_revisor": request.POST.get("papel_revisor") == "1",
        "papel_operacao": request.POST.get("papel_operacao") == "1",
        "pode_publicar_direto": request.POST.get("pode_publicar_direto") == "1",
        "email_monitoramento_respostas": (request.POST.get("email_monitoramento_respostas") or "").strip().lower(),
    }


def _papel_payload_legivel(payload):
    papeis = []
    if payload.get("papel_admin"):
        papeis.append("Admin")
    if payload.get("papel_autor") or payload.get("papel_admin"):
        papeis.append("Autor")
    if payload.get("papel_revisor"):
        papeis.append("Revisor")
    if payload.get("papel_operacao"):
        papeis.append("Operação")
    return " / ".join(dict.fromkeys(papeis)) or "Sem papel"


def usuarios_admin_lista_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "A gestão de usuários é restrita a administradores.",
        )

    filtro_q = (request.GET.get("q") or "").strip()
    filtro_papel = (request.GET.get("papel") or "").strip()
    filtro_status = (request.GET.get("status") or "").strip()

    User = get_user_model()
    usuarios = User.objects.all().select_related("painel_perfil", "autor_vinculado").order_by("username")

    if filtro_q:
        usuarios = usuarios.filter(
            Q(username__icontains=filtro_q)
            | Q(email__icontains=filtro_q)
            | Q(first_name__icontains=filtro_q)
        )

    if filtro_status == "ativos":
        usuarios = usuarios.filter(is_active=True)
    elif filtro_status == "inativos":
        usuarios = usuarios.filter(is_active=False)

    if filtro_papel == "admin":
        usuarios = usuarios.filter(is_superuser=True)
    elif filtro_papel == "autor":
        usuarios = usuarios.filter(groups__name="Autores / Escritores").distinct()
    elif filtro_papel == "revisor":
        usuarios = usuarios.filter(groups__name="Revisores").distinct()
    elif filtro_papel == "operacao":
        usuarios = usuarios.filter(groups__name="Operadores / Atendimento").distinct()

    mudancas_pendentes = (
        SolicitacaoMudancaAdmin.objects.select_related("usuario_alvo", "solicitado_por")
        .filter(status=SolicitacaoMudancaAdmin.STATUS_PENDENTE)
        .order_by("-criado_em")
    )

    return render(
        request,
        "conteudo/admin_usuarios_lista.html",
        {
            "usuarios": usuarios,
            "filtro_q": filtro_q,
            "filtro_papel": filtro_papel,
            "filtro_status": filtro_status,
            "mudancas_pendentes": mudancas_pendentes,
        },
    )


def usuario_admin_editar_view(request, usuario_id):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "A gestão de usuários é restrita a administradores.",
        )

    User = get_user_model()
    usuario = get_object_or_404(User.objects.select_related("painel_perfil", "autor_vinculado"), pk=usuario_id)

    if request.method == "POST":
        nome = (request.POST.get("nome") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        username = (request.POST.get("username") or "").strip()
        is_active = request.POST.get("is_active") == "1"
        payload = {
            "nome": nome,
            "email": email,
            "username": username,
            "is_active": is_active,
            **_payload_roles_usuario(request),
        }

        erros = []
        if not username:
            erros.append("Informe um nome de usuário.")
        if username.lower() == "admin" and usuario.username.lower() != "admin":
            erros.append("O nome de usuário 'admin' é reservado.")
        if User.objects.exclude(pk=usuario.pk).filter(username__iexact=username).exists():
            erros.append("Este nome de usuário já está em uso.")
        if email and User.objects.exclude(pk=usuario.pk).filter(email__iexact=email).exists():
            erros.append("Este e-mail já está em uso.")
        if not any(
            payload[chave]
            for chave in ["papel_admin", "papel_autor", "papel_revisor", "papel_operacao"]
        ):
            erros.append("Selecione pelo menos um papel para o usuário.")
        if payload["email_monitoramento_respostas"]:
            try:
                validate_email(payload["email_monitoramento_respostas"])
            except ValidationError:
                erros.append("O e-mail de monitoramento é inválido.")

        remover_admin = usuario.is_superuser and not payload["papel_admin"]
        desativar_admin = usuario.is_superuser and not is_active
        if (remover_admin or desativar_admin) and _contar_admins_ativos(excluir_usuario_id=usuario.id) == 0:
            erros.append("Não é permitido remover ou desativar o último admin ativo.")

        if erros:
            for erro in erros:
                messages.error(request, erro)
        else:
            if remover_admin or desativar_admin:
                tipo = (
                    SolicitacaoMudancaAdmin.TIPO_DESATIVAR_USUARIO
                    if desativar_admin else SolicitacaoMudancaAdmin.TIPO_REMOVER_ADMIN
                )
                solicitacao = SolicitacaoMudancaAdmin.objects.create(
                    usuario_alvo=usuario,
                    solicitado_por=request.user,
                    tipo=tipo,
                    payload=payload,
                )
                registrar_auditoria(
                    request=request,
                    acao="usuario_solicitou_mudanca_admin_sensivel",
                    alvo=usuario,
                    detalhes=f"Solicitação #{solicitacao.id} criada para {_papel_payload_legivel(payload)}.",
                )
                messages.warning(request, "Mudança sensível criada. Outro admin precisa confirmar.")
                return redirect("admin_usuarios_lista")

            usuario.first_name = nome
            usuario.email = email
            usuario.username = username
            usuario.is_active = is_active
            usuario.save()
            aplicar_papeis_usuario(usuario, **_payload_roles_usuario(request))
            registrar_auditoria(
                request=request,
                acao="usuario_atualizado_por_admin",
                alvo=usuario,
                detalhes=f"Papéis: {_papel_payload_legivel(payload)}.",
            )
            messages.success(request, "Usuário atualizado com sucesso.")
            return redirect("admin_usuario_editar", usuario_id=usuario.id)

    return render(
        request,
        "conteudo/admin_usuario_editar.html",
        {
            "usuario_obj": usuario,
            "perfil": get_panel_profile(usuario),
            "papel_admin": is_admin(usuario),
            "papel_autor": is_author(usuario),
            "papel_revisor": is_reviewer(usuario),
            "papel_operacao": is_operator(usuario),
        },
    )


def usuario_admin_confirmar_mudanca_view(request, solicitacao_id):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "A confirmação de mudanças sensíveis é restrita a administradores.",
        )

    solicitacao = get_object_or_404(
        SolicitacaoMudancaAdmin.objects.select_related("usuario_alvo", "solicitado_por"),
        pk=solicitacao_id,
        status=SolicitacaoMudancaAdmin.STATUS_PENDENTE,
    )

    if solicitacao.solicitado_por_id == request.user.id:
        messages.error(request, "Outro admin precisa confirmar esta mudança.")
        return redirect("admin_usuarios_lista")

    if request.method != "POST":
        return render(
            request,
            "conteudo/admin_usuario_confirmar_mudanca.html",
            {"solicitacao": solicitacao},
        )

    payload = solicitacao.payload or {}
    usuario = solicitacao.usuario_alvo
    usuario.first_name = (payload.get("nome") or "").strip()
    usuario.email = (payload.get("email") or "").strip().lower()
    usuario.username = (payload.get("username") or "").strip()
    usuario.is_active = bool(payload.get("is_active"))
    usuario.save()
    aplicar_papeis_usuario(
        usuario,
        papel_admin=bool(payload.get("papel_admin")),
        papel_autor=bool(payload.get("papel_autor")),
        papel_revisor=bool(payload.get("papel_revisor")),
        papel_operacao=bool(payload.get("papel_operacao")),
        pode_publicar_direto=bool(payload.get("pode_publicar_direto")),
        email_monitoramento_respostas=payload.get("email_monitoramento_respostas", ""),
    )
    solicitacao.status = SolicitacaoMudancaAdmin.STATUS_CONFIRMADA
    solicitacao.confirmado_por = request.user
    solicitacao.confirmado_em = timezone.now()
    solicitacao.save(update_fields=["status", "confirmado_por", "confirmado_em"])
    registrar_auditoria(
        request=request,
        acao="usuario_mudanca_admin_confirmada",
        alvo=usuario,
        detalhes=f"Solicitação #{solicitacao.id} confirmada por {request.user.username}.",
    )
    messages.success(request, "Mudança sensível confirmada e aplicada.")
    return redirect("admin_usuarios_lista")


def _pode_ver_mensagem_contato(user, mensagem):
    if not user.is_authenticated or not user.is_staff:
        return False
    if is_admin(user):
        return True
    return mensagem.atribuido_para_id == user.id


def contato_inbox_admin_view(request):
    if not _pode_acessar_admin_contato(request.user):
        return _negar_acesso_admin(
            request,
            "A inbox de contato é restrita a usuários da equipe.",
        )

    filtro_q = (request.GET.get("q") or "").strip()
    filtro_status = (request.GET.get("status") or "").strip()
    filtro_responsavel = (request.GET.get("responsavel") or "").strip()
    filtro_sem_responsavel = request.GET.get("sem_responsavel") == "1"
    data_de_raw = (request.GET.get("data_de") or "").strip()
    data_ate_raw = (request.GET.get("data_ate") or "").strip()
    data_de_iso, data_de_exibicao = _normalizar_data_busca(data_de_raw, "pt-br")
    data_ate_iso, data_ate_exibicao = _normalizar_data_busca(data_ate_raw, "pt-br")

    mensagens = MensagemContato.objects.select_related("pagina", "atribuido_para").all()

    if not is_admin(request.user):
        mensagens = mensagens.filter(atribuido_para=request.user)

    if filtro_q:
        mensagens = mensagens.filter(
            Q(nome__icontains=filtro_q)
            | Q(email__icontains=filtro_q)
            | Q(mensagem__icontains=filtro_q)
        )
    if filtro_status:
        mensagens = mensagens.filter(status=filtro_status)
    if is_admin(request.user) and filtro_responsavel.isdigit():
        mensagens = mensagens.filter(atribuido_para_id=int(filtro_responsavel))
    if filtro_sem_responsavel and is_admin(request.user):
        mensagens = mensagens.filter(atribuido_para__isnull=True)
    if data_de_iso:
        mensagens = mensagens.filter(criado_em__date__gte=data_de_iso)
    if data_ate_iso:
        mensagens = mensagens.filter(criado_em__date__lte=data_ate_iso)

    paginator = Paginator(mensagens.order_by("-criado_em"), 30)
    pagina_atual = paginator.get_page(request.GET.get("pagina"))
    qs = request.GET.copy()
    qs.pop("pagina", None)

    responsaveis = eligible_contact_assignees()
    panel_email_suggestions = list(
        responsaveis.exclude(email__isnull=True)
        .exclude(email__exact="")
        .values_list("email", flat=True)
        .distinct()
    )

    return render(
        request,
        "conteudo/admin_contato_inbox.html",
        {
            "mensagens": pagina_atual,
            "filtro_q": filtro_q,
            "filtro_status": filtro_status,
            "filtro_responsavel": filtro_responsavel,
            "filtro_sem_responsavel": filtro_sem_responsavel,
            "filtro_data_de": data_de_exibicao,
            "filtro_data_ate": data_ate_exibicao,
            "status_choices": MensagemContato.STATUS_CHOICES,
            "responsaveis": responsaveis,
            "query_string_sem_pagina": qs.urlencode(),
            "is_admin": is_admin(request.user),
        },
    )


def contato_mensagem_admin_view(request, mensagem_id):
    if not _pode_acessar_admin_contato(request.user):
        return _negar_acesso_admin(
            request,
            "A inbox de contato é restrita a usuários da equipe.",
        )

    mensagem = get_object_or_404(
        MensagemContato.objects.select_related("pagina", "atribuido_para"),
        pk=mensagem_id,
    )
    if not _pode_ver_mensagem_contato(request.user, mensagem):
        messages.error(request, "Você não tem permissão para acessar esta mensagem.")
        return redirect("admin_contato_inbox")

    responsaveis = eligible_contact_assignees()
    panel_email_suggestions = list(
        responsaveis.exclude(email__isnull=True)
        .exclude(email__exact="")
        .values_list("email", flat=True)
        .distinct()
    )
    interacoes = mensagem.interacoes.select_related("criado_por").all()
    ultima_resposta = _ultima_resposta_sucesso_contato(mensagem)
    resposta_form = ContatoRespostaForm(
        initial={
            "assunto_resposta": f"Re: Contato - {mensagem.pagina.title}",
            "corpo_resposta": _corpo_inicial_email_com_assinatura(request, request.user),
        }
    )
    encaminhamento_form = ContatoEncaminhamentoForm(
        panel_email_suggestions=panel_email_suggestions,
        initial={
            "assunto_encaminhamento": f"[Encaminhamento contato] {mensagem.nome} - {mensagem.email}",
            "corpo_encaminhamento": _corpo_inicial_email_com_assinatura(request, request.user),
            "incluir_ultima_resposta": bool(ultima_resposta),
        }
    )

    if request.method == "POST":
        acao = (request.POST.get("acao") or "").strip()

        if acao == "atribuir":
            if not is_admin(request.user):
                messages.error(request, "Apenas administradores podem atribuir mensagens.")
                return redirect("admin_contato_mensagem", mensagem_id=mensagem.id)
            user_id = (request.POST.get("responsavel_id") or "").strip()
            destino = responsaveis.filter(pk=user_id).first() if user_id.isdigit() else None
            mensagem.atribuido_para = destino
            if mensagem.status == MensagemContato.STATUS_NOVO and destino:
                mensagem.status = MensagemContato.STATUS_EM_ANDAMENTO
            mensagem.save(update_fields=["atribuido_para", "status", "atualizado_em"])
            InteracaoMensagemContato.objects.create(
                mensagem=mensagem,
                tipo=InteracaoMensagemContato.TIPO_ATRIBUICAO,
                criado_por=request.user,
                corpo=f"Atribuído para: {destino.username if destino else 'sem responsável'}",
                sucesso_envio=True,
            )
            registrar_auditoria(
                request=request,
                acao="contato_mensagem_atribuida",
                alvo=mensagem,
                detalhes=f"Mensagem atribuída para user_id={destino.id if destino else ''}.",
            )
            messages.success(request, "Responsável atualizado.")
            return redirect("admin_contato_mensagem", mensagem_id=mensagem.id)

        if acao == "status":
            novo_status = (request.POST.get("novo_status") or "").strip()
            valores_validos = {item[0] for item in MensagemContato.STATUS_CHOICES}
            if novo_status not in valores_validos:
                messages.error(request, "Status inválido.")
                return redirect("admin_contato_mensagem", mensagem_id=mensagem.id)
            mensagem.status = novo_status
            mensagem.save(update_fields=["status", "atualizado_em"])
            InteracaoMensagemContato.objects.create(
                mensagem=mensagem,
                tipo=InteracaoMensagemContato.TIPO_STATUS,
                criado_por=request.user,
                corpo=f"Status alterado para: {mensagem.get_status_display()}",
                sucesso_envio=True,
            )
            registrar_auditoria(
                request=request,
                acao="contato_mensagem_status_alterado",
                alvo=mensagem,
                detalhes=f"Novo status: {novo_status}",
            )
            messages.success(request, "Status atualizado.")
            return redirect("admin_contato_mensagem", mensagem_id=mensagem.id)

        if acao == "responder":
            resposta_form = ContatoRespostaForm(request.POST)
            if resposta_form.is_valid():
                assunto = resposta_form.cleaned_data["assunto_resposta"].strip()
                corpo = _anexar_assinatura_email_html(
                    request,
                    request.user,
                    resposta_form.cleaned_data["corpo_resposta"],
                )
                try:
                    validate_email((mensagem.email or "").strip())
                except ValidationError:
                    messages.error(request, "E-mail de destino inválido para resposta.")
                    return redirect("admin_contato_mensagem", mensagem_id=mensagem.id)

                email_msg = EmailMessage(
                    subject=assunto,
                    body=corpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[mensagem.email],
                )
                email_msg.content_subtype = "html"
                sucesso = True
                erro = ""
                try:
                    email_msg.send(fail_silently=False)
                    _enviar_monitoramento_resposta_contato(request, mensagem, corpo)
                    mensagem.status = MensagemContato.STATUS_RESPONDIDO
                    mensagem.save(update_fields=["status", "atualizado_em"])
                    messages.success(request, "Resposta enviada com sucesso.")
                except Exception as exc:
                    sucesso = False
                    erro = str(exc)
                    messages.error(request, "Falha ao enviar e-mail de resposta.")

                InteracaoMensagemContato.objects.create(
                    mensagem=mensagem,
                    tipo=InteracaoMensagemContato.TIPO_RESPOSTA,
                    criado_por=request.user,
                    destinatario_email=mensagem.email,
                    assunto=assunto,
                    corpo=corpo,
                    sucesso_envio=sucesso,
                    erro_envio=erro,
                )
                registrar_auditoria(
                    request=request,
                    acao="contato_mensagem_respondida",
                    alvo=mensagem,
                    detalhes=f"Resposta enviada para {mensagem.email}. Sucesso={sucesso}.",
                )
                return redirect("admin_contato_mensagem", mensagem_id=mensagem.id)
            messages.error(request, "Corrija os campos da resposta.")

        if acao == "encaminhar":
            if not is_admin(request.user):
                messages.error(request, "Apenas administradores podem encaminhar mensagens.")
                return redirect("admin_contato_mensagem", mensagem_id=mensagem.id)
            encaminhamento_form = ContatoEncaminhamentoForm(
                request.POST,
                panel_email_suggestions=panel_email_suggestions,
            )
            if encaminhamento_form.is_valid():
                destinatario = encaminhamento_form.cleaned_data["email_encaminhar"].strip().lower()
                assunto = encaminhamento_form.cleaned_data["assunto_encaminhamento"].strip()
                corpo_complementar = _anexar_assinatura_email_html(
                    request,
                    request.user,
                    encaminhamento_form.cleaned_data["corpo_encaminhamento"],
                )
                incluir_ultima_resposta = encaminhamento_form.cleaned_data["incluir_ultima_resposta"]

                partes = []
                if strip_tags(corpo_complementar or "").strip():
                    partes.append(
                        "<p><strong>Observação complementar:</strong></p>"
                        f"<div>{corpo_complementar}</div>"
                    )
                partes.append(
                    f"<p><strong>Encaminhado por:</strong> {escape(request.user.username)}</p>"
                    f"<p><strong>Mensagem original de:</strong> {escape(mensagem.nome)} ({escape(mensagem.email)})</p>"
                    f"<p><strong>Texto original:</strong><br>{escape(mensagem.mensagem).replace(chr(10), '<br>')}</p>"
                )
                if incluir_ultima_resposta and ultima_resposta and (ultima_resposta.corpo or "").strip():
                    partes.append(
                        "<hr><p><strong>Última resposta enviada pelo painel:</strong></p>"
                        f"<div>{ultima_resposta.corpo}</div>"
                    )
                corpo = "".join(partes)

                email_msg = EmailMessage(
                    subject=assunto,
                    body=corpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[destinatario],
                )
                email_msg.content_subtype = "html"
                sucesso = True
                erro = ""
                try:
                    email_msg.send(fail_silently=False)
                    messages.success(request, "Encaminhamento enviado com sucesso.")
                except Exception as exc:
                    sucesso = False
                    erro = str(exc)
                    messages.error(request, "Falha ao enviar encaminhamento.")

                InteracaoMensagemContato.objects.create(
                    mensagem=mensagem,
                    tipo=InteracaoMensagemContato.TIPO_ENCAMINHAMENTO,
                    criado_por=request.user,
                    destinatario_email=destinatario,
                    assunto=assunto,
                    corpo=corpo,
                    sucesso_envio=sucesso,
                    erro_envio=erro,
                )
                registrar_auditoria(
                    request=request,
                    acao="contato_mensagem_encaminhada",
                    alvo=mensagem,
                    detalhes=f"Encaminhada para {destinatario}. Sucesso={sucesso}.",
                )
                return redirect("admin_contato_mensagem", mensagem_id=mensagem.id)
            messages.error(request, "Corrija os campos do encaminhamento.")

    return render(
        request,
        "conteudo/admin_contato_mensagem.html",
        {
            "mensagem": mensagem,
            "interacoes": interacoes,
            "responsaveis": responsaveis,
            "panel_email_suggestions": panel_email_suggestions,
            "status_choices": MensagemContato.STATUS_CHOICES,
            "is_admin": is_admin(request.user),
            "resposta_form": resposta_form,
            "encaminhamento_form": encaminhamento_form,
            "ultima_resposta": ultima_resposta,
        },
    )


def _templates_email_prontos(site):
    nome_site = getattr(site, "site_name", "") or site.hostname
    return [
        {
            "id": "novidade",
            "nome": "Novidade do site",
            "assunto": f"Novidade no {nome_site}",
            "corpo_html": (
                f"<p>Olá!</p><p>Temos uma novidade no <strong>{nome_site}</strong>.</p>"
                "<p>Acesse o site para conferir.</p>"
            ),
        },
        {
            "id": "boletim",
            "nome": "Boletim semanal",
            "assunto": f"Boletim semanal - {nome_site}",
            "corpo_html": (
                "<p>Olá!</p><p>Segue o resumo da semana:</p>"
                "<ul><li>Atualização 1</li><li>Atualização 2</li></ul>"
                "<p>Até a próxima.</p>"
            ),
        },
        {
            "id": "comunicado",
            "nome": "Comunicado geral",
            "assunto": f"Comunicado oficial - {nome_site}",
            "corpo_html": (
                "<p>Olá!</p><p>Este é um comunicado importante.</p>"
                "<p>Obrigado pela atenção.</p>"
            ),
        },
    ]


def _resolver_template_email(site, tpl_value):
    tpl_value = (tpl_value or "").strip()
    templates_prontos = _templates_email_prontos(site)
    prontos_map = {f"builtin:{tpl['id']}": tpl for tpl in templates_prontos}
    if tpl_value in prontos_map:
        tpl = prontos_map[tpl_value]
        return tpl_value, tpl["assunto"], _sanitizar_corpo_email_admin(tpl["corpo_html"])

    if tpl_value.startswith("saved:"):
        try:
            template_id = int(tpl_value.split(":", 1)[1])
        except (TypeError, ValueError):
            return "", "", ""
        template_salvo = TemplateEmailCampanha.objects.filter(
            id=template_id,
            ativo=True,
        ).first()
        if template_salvo:
            return (
                tpl_value,
                template_salvo.assunto_padrao,
                _sanitizar_corpo_email_admin(template_salvo.corpo_html_padrao),
            )
    return "", "", ""


def email_admin_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "A gestão de e-mails é restrita a administradores.",
        )

    ultimos_30_dias = timezone.now() - timedelta(days=30)
    disparos_30d = DisparoEmail.objects.filter(criado_em__gte=ultimos_30_dias)
    totais_30d = disparos_30d.aggregate(
        enviados=Sum("total_enviados"),
        falhas=Sum("total_falhas"),
    )
    context = {
        "disparos_total": DisparoEmail.objects.count(),
        "disparos_30d": disparos_30d.count(),
        "enviados_30d": int(totais_30d.get("enviados") or 0),
        "falhas_30d": int(totais_30d.get("falhas") or 0),
        "templates_total": TemplateEmailCampanha.objects.count(),
        "templates_ativos": TemplateEmailCampanha.objects.filter(ativo=True).count(),
        "disparos_url": reverse("admin_email_disparos"),
        "templates_url": reverse("admin_email_templates"),
        "publicacoes_url": reverse("admin_email_publicacoes"),
    }
    return render(request, "conteudo/admin_email.html", context)


def email_templates_admin_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "Os templates de e-mail são restritos a administradores.",
        )

    template_edit = None
    template_edit_id = (request.GET.get("editar") or "").strip()
    if template_edit_id.isdigit():
        template_edit = TemplateEmailCampanha.objects.filter(id=int(template_edit_id)).first()

    if request.method == "POST":
        acao = (request.POST.get("acao") or "").strip()
        if acao == "salvar":
            template_id = (request.POST.get("template_id") or "").strip()
            nome = (request.POST.get("nome") or "").strip()
            assunto = (request.POST.get("assunto") or "").strip()
            corpo = _sanitizar_corpo_email_admin(request.POST.get("corpo_html") or "")
            ativo = (request.POST.get("ativo") or "").strip() == "on"

            if not nome or not assunto or not corpo:
                messages.error(request, "Nome, assunto e corpo são obrigatórios.")
                return redirect("admin_email_templates")

            if template_id.isdigit():
                template = TemplateEmailCampanha.objects.filter(id=int(template_id)).first()
                if not template:
                    messages.error(request, "Template não encontrado.")
                    return redirect("admin_email_templates")
                template.nome = nome
                template.assunto_padrao = assunto
                template.corpo_html_padrao = corpo
                template.ativo = ativo
                template.save(
                    update_fields=[
                        "nome",
                        "assunto_padrao",
                        "corpo_html_padrao",
                        "ativo",
                        "atualizado_em",
                    ]
                )
                registrar_auditoria(
                    request=request,
                    acao="email_template_atualizado",
                    alvo=template,
                    detalhes=f"Template atualizado: {template.nome}.",
                )
                messages.success(request, "Template atualizado.")
                return redirect("admin_email_templates")

            template = TemplateEmailCampanha.objects.create(
                nome=nome,
                assunto_padrao=assunto,
                corpo_html_padrao=corpo,
                ativo=ativo,
                criado_por=request.user,
            )
            registrar_auditoria(
                request=request,
                acao="email_template_criado",
                alvo=template,
                detalhes=f"Template criado: {template.nome}.",
            )
            messages.success(request, "Template criado.")
            return redirect("admin_email_templates")

        if acao == "excluir":
            template_id = (request.POST.get("template_id") or "").strip()
            if not template_id.isdigit():
                messages.error(request, "Template inválido.")
                return redirect("admin_email_templates")
            template = TemplateEmailCampanha.objects.filter(id=int(template_id)).first()
            if not template:
                messages.error(request, "Template não encontrado.")
                return redirect("admin_email_templates")
            nome = template.nome
            template.delete()
            registrar_auditoria(
                request=request,
                acao="email_template_excluido",
                detalhes=f"Template removido: {nome}.",
            )
            messages.success(request, "Template excluído.")
            return redirect("admin_email_templates")

    templates_salvos = TemplateEmailCampanha.objects.select_related("criado_por").order_by("nome")
    return render(
        request,
        "conteudo/admin_email_templates.html",
        {
            "templates_salvos": templates_salvos,
            "template_edit": template_edit,
        },
    )


def email_disparos_admin_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "O disparo em massa é restrito a administradores.",
        )

    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    if not site:
        messages.error(request, "Site não encontrado.")
        return redirect("/admin/")

    templates_prontos = _templates_email_prontos(site)
    templates_salvos = list(TemplateEmailCampanha.objects.filter(ativo=True).order_by("nome"))
    tpl_id = (request.GET.get("tpl") or "").strip()
    tpl_id, assunto_inicial, corpo_inicial = _resolver_template_email(site, tpl_id)
    filtro_historico_tipo = (request.GET.get("tipo") or "").strip()
    filtro_historico_status = (request.GET.get("status_historico") or "").strip()

    historico_qs = DisparoEmail.objects.select_related("criado_por").annotate(
        total_aberturas=Sum("destinos__total_aberturas"),
        total_cliques=Sum("destinos__total_cliques"),
        aberturas_unicas=Count(
            "destinos",
            filter=Q(destinos__aberto_em__isnull=False),
        ),
    )
    if filtro_historico_tipo:
        historico_qs = historico_qs.filter(tipo=filtro_historico_tipo)
    if filtro_historico_status:
        historico_qs = historico_qs.filter(status=filtro_historico_status)
    historico = list(historico_qs[:50])
    for item in historico:
        total = int(item.total_destinatarios or 0)
        enviados = int(item.total_enviados or 0)
        falhas = int(item.total_falhas or 0)
        item.total_aberturas = int(item.total_aberturas or 0)
        item.total_cliques = int(item.total_cliques or 0)
        item.aberturas_unicas = int(item.aberturas_unicas or 0)
        item.taxa_entrega = round((enviados * 100.0 / total), 1) if total else 0.0
        item.taxa_falha = round((falhas * 100.0 / total), 1) if total else 0.0
        item.taxa_abertura_unica = (
            round((item.aberturas_unicas * 100.0 / total), 1) if total else 0.0
        )
        item.ctr_unico = (
            round((item.total_cliques * 100.0 / total), 1) if total else 0.0
        )

    historico_30d = DisparoEmail.objects.filter(
        criado_em__gte=timezone.now() - timedelta(days=30)
    )
    total_30d = int(historico_30d.count() or 0)
    totais_30d = historico_30d.aggregate(
        total_destinatarios=Sum("total_destinatarios"),
        total_enviados=Sum("total_enviados"),
        total_falhas=Sum("total_falhas"),
        total_aberturas=Sum("destinos__total_aberturas"),
        total_cliques=Sum("destinos__total_cliques"),
        total_aberturas_unicas=Count(
            "destinos",
            filter=Q(destinos__aberto_em__isnull=False),
            distinct=True,
        ),
    )
    total_dest_30d = int(totais_30d.get("total_destinatarios") or 0)
    total_env_30d = int(totais_30d.get("total_enviados") or 0)
    total_fal_30d = int(totais_30d.get("total_falhas") or 0)
    total_abr_30d = int(totais_30d.get("total_aberturas") or 0)
    total_clk_30d = int(totais_30d.get("total_cliques") or 0)
    total_abr_unicas_30d = int(totais_30d.get("total_aberturas_unicas") or 0)
    taxa_entrega_30d = round((total_env_30d * 100.0 / total_dest_30d), 1) if total_dest_30d else 0.0
    taxa_falha_30d = round((total_fal_30d * 100.0 / total_dest_30d), 1) if total_dest_30d else 0.0
    taxa_abertura_30d = (
        round((total_abr_unicas_30d * 100.0 / total_dest_30d), 1)
        if total_dest_30d
        else 0.0
    )
    ctr_30d = (
        round((total_clk_30d * 100.0 / total_dest_30d), 1)
        if total_dest_30d
        else 0.0
    )

    if request.method == "POST":
        tpl_post = (request.POST.get("tpl") or "").strip()
        if tpl_post:
            tpl_id, assunto_tpl, corpo_tpl = _resolver_template_email(site, tpl_post)
            if assunto_tpl:
                assunto_inicial = assunto_tpl
            if corpo_tpl:
                corpo_inicial = corpo_tpl

        acao = (request.POST.get("acao") or "enviar_agora").strip()
        assunto = (request.POST.get("assunto") or assunto_inicial).strip()
        corpo_html = _sanitizar_corpo_email_admin(request.POST.get("corpo_html") or corpo_inicial)
        segmento = (request.POST.get("segmento") or "").strip()
        email_teste = (request.POST.get("email_teste") or "").strip().lower()
        segmentos_validos = {item[0] for item in DisparoEmail.SEGMENTO_CHOICES}

        if not assunto or not corpo_html:
            messages.error(request, "Informe assunto e corpo para o disparo.")
            return redirect("admin_email_disparos")
        if segmento not in segmentos_validos:
            messages.error(request, "Segmento inválido.")
            return redirect("admin_email_disparos")

        if acao == "preview":
            segmento_info = []
            for valor, rotulo in DisparoEmail.SEGMENTO_CHOICES:
                segmento_info.append(
                    {
                        "valor": valor,
                        "rotulo": rotulo,
                        "estimativa": len(destinatarios_por_segmento(valor)),
                    }
                )
            return render(
                request,
                "conteudo/admin_email_disparos.html",
                {
                    "segmento_info": segmento_info,
                    "historico": historico,
                    "templates_prontos": templates_prontos,
                    "templates_salvos": templates_salvos,
                    "tpl_id": tpl_id,
                    "assunto_inicial": assunto,
                    "corpo_inicial": corpo_html,
                    "segmento_inicial": segmento,
                    "filtro_historico_tipo": filtro_historico_tipo,
                    "filtro_historico_status": filtro_historico_status,
                    "metricas_30d": {
                        "disparos": total_30d,
                        "destinatarios": total_dest_30d,
                        "enviados": total_env_30d,
                        "falhas": total_fal_30d,
                        "taxa_entrega": taxa_entrega_30d,
                        "taxa_falha": taxa_falha_30d,
                        "aberturas_unicas": total_abr_unicas_30d,
                        "aberturas_total": total_abr_30d,
                        "cliques_total": total_clk_30d,
                        "taxa_abertura": taxa_abertura_30d,
                        "ctr": ctr_30d,
                    },
                    "preview_assunto": assunto,
                    "preview_html_sanitizado": corpo_html,
                },
            )

        if acao == "enviar_teste":
            if not email_teste:
                messages.error(request, "Informe um e-mail para envio de teste.")
                return redirect("admin_email_disparos")
            try:
                validate_email(email_teste)
            except ValidationError:
                messages.error(request, "E-mail de teste inválido.")
                return redirect("admin_email_disparos")
            msg = EmailMessage(
                subject=f"[TESTE] {assunto}",
                body=corpo_html,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email_teste],
            )
            msg.content_subtype = "html"
            try:
                msg.send(fail_silently=False)
                registrar_auditoria(
                    request=request,
                    acao="email_disparo_teste_enviado",
                    detalhes=f"E-mail de teste enviado para {email_teste}.",
                )
                messages.success(request, "E-mail de teste enviado com sucesso.")
            except Exception:
                logger.exception("Falha ao enviar e-mail de teste.")
                messages.error(request, "Falha ao enviar teste. Verifique o SMTP.")
            return redirect("admin_email_disparos")

        disparo = DisparoEmail.objects.create(
            tipo=DisparoEmail.TIPO_MANUAL,
            segmento=segmento,
            assunto=assunto,
            corpo_html=corpo_html,
            criado_por=request.user,
            metadata={
                "template": tpl_id or "",
            },
        )
        executar_disparo(disparo)
        registrar_auditoria(
            request=request,
            acao="email_disparo_manual_executado",
            alvo=disparo,
            detalhes=(
                f"Segmento: {segmento}. Destinatários: {disparo.total_destinatarios}. "
                f"Enviados: {disparo.total_enviados}. Falhas: {disparo.total_falhas}."
            ),
        )
        if disparo.status == DisparoEmail.STATUS_FALHOU:
            messages.error(request, "Disparo falhou. Verifique o histórico.")
        else:
            messages.success(request, "Disparo executado.")
        return redirect("admin_email_disparos")

    segmento_info = []
    for valor, rotulo in DisparoEmail.SEGMENTO_CHOICES:
        segmento_info.append(
            {
                "valor": valor,
                "rotulo": rotulo,
                "estimativa": len(destinatarios_por_segmento(valor)),
            }
        )
    return render(
        request,
        "conteudo/admin_email_disparos.html",
        {
            "segmento_info": segmento_info,
            "historico": historico,
            "templates_prontos": templates_prontos,
            "templates_salvos": templates_salvos,
            "tpl_id": tpl_id,
            "assunto_inicial": assunto_inicial,
            "corpo_inicial": corpo_inicial,
            "segmento_inicial": DisparoEmail.SEG_NEWSLETTER,
            "filtro_historico_tipo": filtro_historico_tipo,
            "filtro_historico_status": filtro_historico_status,
            "metricas_30d": {
                "disparos": total_30d,
                "destinatarios": total_dest_30d,
                "enviados": total_env_30d,
                "falhas": total_fal_30d,
                "taxa_entrega": taxa_entrega_30d,
                "taxa_falha": taxa_falha_30d,
                "aberturas_unicas": total_abr_unicas_30d,
                "aberturas_total": total_abr_30d,
                "cliques_total": total_clk_30d,
                "taxa_abertura": taxa_abertura_30d,
                "ctr": ctr_30d,
            },
        },
    )


def email_disparo_detalhe_admin_view(request, disparo_id):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "Os detalhes de disparo são restritos a administradores.",
        )

    disparo = get_object_or_404(DisparoEmail, pk=disparo_id)
    filtro_status = (request.GET.get("status") or "").strip()
    filtro_q = (request.GET.get("q") or "").strip().lower()
    filtro_dominio = (request.GET.get("dominio") or "").strip().lower()
    periodo_links = (request.GET.get("periodo_links") or "").strip()
    periodos_links_validos = {"7", "30", "90", "all"}
    if periodo_links not in periodos_links_validos:
        periodo_links = "30"

    destinos = DisparoEmailDestino.objects.filter(disparo=disparo)
    if filtro_status:
        destinos = destinos.filter(status=filtro_status)
    if filtro_q:
        destinos = destinos.filter(email__icontains=filtro_q)
    if filtro_dominio:
        destinos = destinos.filter(email__iendswith=f"@{filtro_dominio}")

    total_filtrado = destinos.count()
    enviados_filtrado = destinos.filter(status=DisparoEmailDestino.STATUS_ENVIADO).count()
    falhas_filtrado = destinos.filter(status=DisparoEmailDestino.STATUS_FALHOU).count()
    aberturas_unicas_filtrado = destinos.filter(aberto_em__isnull=False).count()
    aberturas_total_filtrado = int(destinos.aggregate(v=Sum("total_aberturas")).get("v") or 0)
    cliques_total_filtrado = int(destinos.aggregate(v=Sum("total_cliques")).get("v") or 0)
    taxa_entrega = round((enviados_filtrado * 100.0 / total_filtrado), 1) if total_filtrado else 0.0
    taxa_falha = round((falhas_filtrado * 100.0 / total_filtrado), 1) if total_filtrado else 0.0
    taxa_abertura = (
        round((aberturas_unicas_filtrado * 100.0 / total_filtrado), 1)
        if total_filtrado
        else 0.0
    )
    ctr = (
        round((cliques_total_filtrado * 100.0 / total_filtrado), 1)
        if total_filtrado
        else 0.0
    )

    dominio_stats_map = {}
    for row in (
        DisparoEmailDestino.objects.filter(disparo=disparo)
        .values("email", "status")
        .order_by("id")
    ):
        email = (row.get("email") or "").strip().lower()
        if "@" not in email:
            dominio = "(inválido)"
        else:
            dominio = email.split("@", 1)[1]
        existente = dominio_stats_map.setdefault(
            dominio,
            {"dominio": dominio, "total": 0, "enviados": 0, "falhas": 0},
        )
        existente["total"] += 1
        if row.get("status") == DisparoEmailDestino.STATUS_ENVIADO:
            existente["enviados"] += 1
        if row.get("status") == DisparoEmailDestino.STATUS_FALHOU:
            existente["falhas"] += 1
    dominio_stats = list(dominio_stats_map.values())
    dominio_stats.sort(key=lambda item: (-item["total"], item["dominio"]))
    for item in dominio_stats[:20]:
        total_dom = int(item["total"] or 0)
        item["taxa_entrega"] = round((item["enviados"] * 100.0 / total_dom), 1) if total_dom else 0.0
        item["taxa_falha"] = round((item["falhas"] * 100.0 / total_dom), 1) if total_dom else 0.0

    destino_ids_filtrados = list(destinos.values_list("id", flat=True))
    top_links = []
    if destino_ids_filtrados:
        qs_cliques = DisparoEmailClique.objects.filter(
            disparo=disparo,
            destino_id__in=destino_ids_filtrados,
        )
        if periodo_links != "all":
            dias = int(periodo_links)
            qs_cliques = qs_cliques.filter(
                criado_em__gte=timezone.now() - timedelta(days=dias)
            )
        top_links = list(
            qs_cliques.values("url")
            .annotate(total=Count("id"))
            .order_by("-total", "url")[:20]
        )
    total_cliques_links = sum(int(item.get("total") or 0) for item in top_links)
    for item in top_links:
        total_item = int(item.get("total") or 0)
        item["percentual"] = (
            round((total_item * 100.0 / total_cliques_links), 1)
            if total_cliques_links
            else 0.0
        )

    comparativo_links = None
    if destino_ids_filtrados and periodo_links != "all":
        dias = int(periodo_links)
        agora = timezone.now()
        inicio_atual = agora - timedelta(days=dias)
        inicio_anterior = inicio_atual - timedelta(days=dias)
        qs_base = DisparoEmailClique.objects.filter(
            disparo=disparo,
            destino_id__in=destino_ids_filtrados,
        )
        cliques_periodo_atual = qs_base.filter(criado_em__gte=inicio_atual).count()
        cliques_periodo_anterior = qs_base.filter(
            criado_em__gte=inicio_anterior,
            criado_em__lt=inicio_atual,
        ).count()
        variacao_absoluta = cliques_periodo_atual - cliques_periodo_anterior
        if cliques_periodo_anterior > 0:
            variacao_percentual = round(
                (variacao_absoluta * 100.0 / cliques_periodo_anterior),
                1,
            )
        elif cliques_periodo_atual > 0:
            variacao_percentual = 100.0
        else:
            variacao_percentual = 0.0
        if variacao_absoluta > 0:
            tendencia = "alta"
        elif variacao_absoluta < 0:
            tendencia = "queda"
        else:
            tendencia = "estavel"
        comparativo_links = {
            "dias": dias,
            "atual": cliques_periodo_atual,
            "anterior": cliques_periodo_anterior,
            "variacao_absoluta": variacao_absoluta,
            "variacao_percentual": variacao_percentual,
            "tendencia": tendencia,
        }

    if (request.GET.get("export") or "").strip().lower() == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="disparo_{disparo.id}_destinatarios.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "email",
                "status",
                "enviado_em",
                "aberto_em",
                "total_aberturas",
                "total_cliques",
                "erro",
            ]
        )
        for item in destinos.order_by("id"):
            writer.writerow(
                [
                    item.id,
                    item.email,
                    item.get_status_display(),
                    item.enviado_em.isoformat() if item.enviado_em else "",
                    item.aberto_em.isoformat() if item.aberto_em else "",
                    item.total_aberturas,
                    item.total_cliques,
                    item.erro or "",
                ]
            )
        return response

    paginator = Paginator(destinos.order_by("id"), 100)
    page_obj = paginator.get_page(request.GET.get("pagina"))
    qs = request.GET.copy()
    qs.pop("pagina", None)

    return render(
        request,
        "conteudo/admin_email_disparo_detalhe.html",
        {
            "disparo": disparo,
            "destinos": page_obj,
            "filtro_status": filtro_status,
            "filtro_q": filtro_q,
            "filtro_dominio": filtro_dominio,
            "periodo_links": periodo_links,
            "total_filtrado": total_filtrado,
            "enviados_filtrado": enviados_filtrado,
            "falhas_filtrado": falhas_filtrado,
            "aberturas_unicas_filtrado": aberturas_unicas_filtrado,
            "aberturas_total_filtrado": aberturas_total_filtrado,
            "cliques_total_filtrado": cliques_total_filtrado,
            "taxa_entrega": taxa_entrega,
            "taxa_falha": taxa_falha,
            "taxa_abertura": taxa_abertura,
            "ctr": ctr,
            "dominio_stats": dominio_stats[:20],
            "top_links": top_links,
            "total_cliques_links": total_cliques_links,
            "comparativo_links": comparativo_links,
            "status_choices": DisparoEmailDestino.STATUS_CHOICES,
            "query_string_sem_pagina": qs.urlencode(),
        },
    )


def email_publicacoes_admin_view(request):
    if not _pode_acessar_admin_superuser(request.user):
        return _negar_acesso_admin(
            request,
            "A configuração de e-mails de publicações é restrita a administradores.",
        )

    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    if not site:
        messages.error(request, "Site não encontrado.")
        return redirect("/admin/")

    config = ConfiguracaoSite.for_site(site)
    periodo_dias_choices = [
        (7, "7 dias"),
        (15, "15 dias"),
        (30, "30 dias"),
        (90, "90 dias"),
    ]
    if request.method == "POST":
        acao = (request.POST.get("acao") or "").strip()
        if acao == "salvar_config":
            modo = (request.POST.get("modo") or "").strip()
            periodo_dias_raw = (request.POST.get("periodo_dias") or "").strip()
            modos_validos = {item[0] for item in ConfiguracaoSite.NOTIFICACAO_PUBLICACOES_CHOICES}
            if modo not in modos_validos:
                messages.error(request, "Modo inválido.")
                return redirect("admin_email_publicacoes")
            try:
                periodo_dias = int(periodo_dias_raw)
            except ValueError:
                periodo_dias = 7
            periodo_dias_validos = {valor for valor, _rotulo in periodo_dias_choices}
            if periodo_dias not in periodo_dias_validos:
                periodo_dias = 7
            periodo_h = periodo_dias * 24
            config.notificacao_publicacoes_modo = modo
            config.notificacao_publicacoes_periodo_horas = periodo_h
            config.save(
                update_fields=[
                    "notificacao_publicacoes_modo",
                    "notificacao_publicacoes_periodo_horas",
                ]
            )
            registrar_auditoria(
                request=request,
                acao="email_publicacoes_configurada",
                alvo=config,
                detalhes=f"Modo={modo}; período_dias={periodo_dias}; período_horas={periodo_h}.",
            )
            messages.success(request, "Configuração salva.")
            return redirect("admin_email_publicacoes")

        if acao == "enviar_periodico_agora":
            disparo = enviar_publicacoes_periodicas(site, forcar=True)
            if disparo:
                registrar_auditoria(
                    request=request,
                    acao="email_publicacoes_periodico_manual",
                    alvo=disparo,
                    detalhes=(
                        f"Destinatários: {disparo.total_destinatarios}. "
                        f"Enviados: {disparo.total_enviados}. Falhas: {disparo.total_falhas}."
                    ),
                )
                messages.success(request, "Disparo periódico executado.")
            else:
                messages.warning(request, "Nenhuma publicação nova para enviar no período.")
            return redirect("admin_email_publicacoes")

    historico = DisparoEmail.objects.filter(
        tipo__in=[
            DisparoEmail.TIPO_PUBLICACOES_IMEDIATA,
            DisparoEmail.TIPO_PUBLICACOES_PERIODICA,
        ]
    )[:30]
    return render(
        request,
        "conteudo/admin_email_publicacoes.html",
        {
            "config_site": config,
            "modo_choices": ConfiguracaoSite.NOTIFICACAO_PUBLICACOES_CHOICES,
            "periodo_dias_choices": periodo_dias_choices,
            "periodo_dias_atual": max(1, int(config.notificacao_publicacoes_periodo_horas or 168) // 24),
            "historico": historico,
            "total_newsletter_ativa": len(destinatarios_por_segmento(DisparoEmail.SEG_NEWSLETTER)),
        },
    )


def minha_conta_admin_view(request):
    return redirect("wagtailadmin_account")


@hooks.register("before_create_page")
def restringir_criacao_publicacao_para_autor_vinculado(request, parent_page, page_class):
    if page_class is not PublicacaoPage:
        return None

    if is_admin(request.user):
        return None

    if not is_author(request.user):
        return _bloquear_com_mensagem(
            request,
            "A criação de publicações é restrita a autores e administradores.",
        )

    autor = _autor_vinculado_do_usuario(request.user)
    if not autor:
        return _bloquear_com_mensagem(
            request,
            "Seu usuário não possui autor vinculado. Fale com um administrador.",
        )

    autores_ids = _autores_enviados_no_formulario(request)
    if autores_ids and any(aid != autor.id for aid in autores_ids):
        return _bloquear_com_mensagem(
            request,
            "Usuários não administradores só podem publicar com seu autor vinculado.",
        )

    return None


@hooks.register("after_create_page")
def garantir_autor_vinculado_na_criacao(request, page):
    if not isinstance(page.specific, PublicacaoPage):
        return None

    publicacao = page.specific
    _quarentenar_midias_publicacao_diretas(request, publicacao)
    _registrar_atualizador_publicacao(request, publicacao)

    autor = _autor_vinculado_do_usuario(request.user)
    if not autor and not is_admin(request.user):
        return None

    if autor and not publicacao.autores_publicacao.filter(autor=autor).exists():
        publicacao.autores_publicacao.all().delete()
        PublicacaoPageAutor.objects.create(
            publicacao=publicacao,
            autor=autor,
            sort_order=0,
            confirmacao_status=PublicacaoPageAutor.STATUS_CONFIRMACAO_CONFIRMADO,
            atribuido_por=request.user,
            atribuido_em=timezone.now(),
            confirmado_por=request.user,
            confirmado_em=timezone.now(),
        )
        publicacao.save_revision(user=request.user)
        messages.warning(
            request,
            "Autor ajustado automaticamente para o autor vinculado ao seu usuário.",
        )
    _sincronizar_confirmacoes_autoria(request, publicacao, set())
    registrar_auditoria(
        request=request,
        acao="publicacao_criada",
        alvo=page.specific,
        detalhes=f"Publicação criada pelo painel Wagtail. Status: {page.specific.status_editorial}.",
    )
    return None


@hooks.register("after_edit_page")
def registrar_edicao_publicacao_wagtail(request, page):
    if not isinstance(page.specific, PublicacaoPage):
        return None
    _quarentenar_midias_publicacao_diretas(request, page.specific)
    _registrar_atualizador_publicacao(request, page.specific)
    _sincronizar_confirmacoes_autoria(
        request,
        page.specific,
        getattr(request, "_ownpaper_autores_publicacao_antes", None),
    )
    registrar_auditoria(
        request=request,
        acao="publicacao_editada",
        alvo=page.specific,
        detalhes=f"Publicação editada pelo painel Wagtail. Status: {page.specific.status_editorial}.",
    )
    return None


@hooks.register("before_edit_page")
def restringir_edicao_publicacao_para_autor_vinculado(request, page):
    if not isinstance(page.specific, PublicacaoPage):
        return None

    publicacao = page.specific
    request._ownpaper_autores_publicacao_antes = set(
        publicacao.autores_publicacao.values_list("autor_id", flat=True)
    )
    autores_ids = _autores_enviados_no_formulario(request)

    if _trava_publicacao_orcid_ativa(request):
        if (
            publicacao.autores_publicacao.filter(autor__orcid__gt="").exists()
            and _autoria_alterada_no_formulario(publicacao, autores_ids)
        ):
            return _bloquear_com_mensagem(
                request,
                "Autoria travada por ORCID. Desative esta trava em Configurações do site para alterar autores.",
            )

    if is_admin(request.user):
        if publicacao.status_editorial == PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO and not _revisao_atribuida_para_usuario(publicacao, request.user):
            messages.warning(request, "Você está revisando uma publicação não atribuída ao seu usuário.")
        return None

    if is_reviewer(request.user) and not is_author(request.user):
        if publicacao.status_editorial == PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO and not _revisao_atribuida_para_usuario(publicacao, request.user):
            messages.warning(request, "Esta publicação não está atribuída a você, mas a revisão foi liberada com alerta.")
        return _bloquear_com_mensagem(
            request,
            "Revisores devem usar o Fluxo editorial para ler e decidir publicações. A edição direta é restrita a autores autorizados e administradores.",
        )

    autor = _autor_vinculado_do_usuario(request.user)
    if not autor:
        return _bloquear_com_mensagem(
            request,
            "Seu usuário não possui autor vinculado. Fale com um administrador.",
        )

    if not _publicacao_pertence_ao_autor(publicacao, autor):
        return _bloquear_com_mensagem(
            request,
            "Você só pode editar publicações do seu autor vinculado.",
        )

    if autores_ids and any(aid != autor.id for aid in autores_ids):
        return _bloquear_com_mensagem(
            request,
            "Usuários não administradores só podem usar seu autor vinculado.",
        )

    if publicacao.status_editorial in {
        PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO,
        PublicacaoPage.STATUS_EDITORIAL_AGENDADO,
        PublicacaoPage.STATUS_EDITORIAL_PUBLICADO,
    }:
        return _bloquear_com_mensagem(
            request,
            "Esta publicação está em revisão ou publicada. Solicite reabertura no fluxo editorial para editar.",
        )

    return None


@hooks.register("before_publish_page")
def restringir_publicacao_para_autor_vinculado(request, page):
    if not isinstance(page.specific, PublicacaoPage):
        return None

    publicacao = page.specific
    if _trava_publicacao_orcid_ativa(request) and _tem_autor_sem_orcid(publicacao):
        return _bloquear_com_mensagem(
            request,
            "Para publicar com trava ORCID ativa, todos os autores precisam ter ORCID preenchido.",
        )
    if is_admin(request.user):
        motivo_pendencia = _publicacao_tem_dependencias_editoriais_pendentes_sem_autoria_pendente(publicacao)
    else:
        motivo_pendencia = _publicacao_tem_dependencias_editoriais_pendentes(publicacao)
    if motivo_pendencia:
        return _bloquear_com_mensagem(request, motivo_pendencia)

    if is_admin(request.user):
        autor_vinculado = _autor_vinculado_do_usuario_incluindo_admin(request.user)
        pertence_ao_autor = _publicacao_pertence_ao_autor(publicacao, autor_vinculado)
        if (
            publicacao.status_editorial == PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO
            and not _revisao_atribuida_para_usuario(publicacao, request.user)
            and not pertence_ao_autor
        ):
            messages.warning(request, "Você está publicando uma publicação não atribuída ao seu usuário.")
        if _publicacao_tem_autoria_pendente(publicacao):
            messages.warning(
                request,
                (
                    "Há autoria pendente de confirmação. Até o autor confirmar, "
                    f"a publicação será exibida no nome do usuário {request.user.get_username()}."
                ),
            )
            registrar_auditoria(
                request=request,
                acao="publicacao_publicada_com_autoria_pendente",
                alvo=publicacao,
                detalhes=(
                    "Admin publicou com autoria pendente; exibição pública temporária "
                    f"no usuário {request.user.get_username()}."
                ),
            )
        PublicacaoPage.objects.filter(id=publicacao.id).update(
            status_editorial=PublicacaoPage.STATUS_EDITORIAL_PUBLICADO,
            publicado_em=timezone.now(),
            publicado_por=request.user,
            reabertura_solicitada=False,
        )
        return None

    if is_reviewer(request.user) and not is_author(request.user):
        return _bloquear_com_mensagem(
            request,
            "Revisores devem aprovar ou rejeitar publicações pelo Fluxo editorial, não pela publicação direta no editor.",
        )

    autor = _autor_vinculado_do_usuario(request.user)
    if not autor:
        return _bloquear_com_mensagem(
            request,
            "Seu usuário não possui autor vinculado. Fale com um administrador.",
        )

    if not _publicacao_pertence_ao_autor(publicacao, autor):
        return _bloquear_com_mensagem(
            request,
            "Você só pode publicar publicações do seu autor vinculado.",
        )

    autores_ids = _autores_enviados_no_formulario(request)
    if autores_ids and any(aid != autor.id for aid in autores_ids):
        return _bloquear_com_mensagem(
            request,
            "Usuários não administradores só podem publicar com seu autor vinculado.",
        )

    if can_publish_direct(request.user):
        PublicacaoPage.objects.filter(id=publicacao.id).update(
            status_editorial=PublicacaoPage.STATUS_EDITORIAL_PUBLICADO,
            publicado_em=timezone.now(),
            publicado_por=request.user,
            reabertura_solicitada=False,
        )
        _enviar_alerta_publicacao_para_admins(
            publicacao,
            f"[OwnPaper] Publicação publicada diretamente: {publicacao.title}",
            (
                f"<p>A publicação <strong>{escape(publicacao.title)}</strong> foi publicada diretamente por "
                f"<strong>{escape(request.user.username)}</strong>.</p>"
            ),
        )
        return None

    PublicacaoPage.objects.filter(id=publicacao.id).update(
        status_editorial=PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO,
        revisao_solicitada_em=timezone.now(),
        revisao_solicitada_por=request.user,
    )
    _enviar_alerta_publicacao_para_admins(
        publicacao,
        f"[OwnPaper] Publicação aguardando aprovação: {publicacao.title}",
        (
            f"<p>A publicação <strong>{escape(publicacao.title)}</strong> foi enviada para revisão por "
            f"<strong>{escape(request.user.username)}</strong>.</p>"
        ),
    )
    return _bloquear_com_mensagem(
        request,
        "Publicação enviada para revisão. Um revisor ou administrador precisa liberar a publicação.",
    )


@hooks.register("before_delete_page")
def restringir_exclusao_publicacao_para_autor_vinculado(request, page):
    if not isinstance(page.specific, PublicacaoPage):
        return None

    publicacao = page.specific
    if is_admin(request.user):
        registrar_auditoria(
            request=request,
            acao="publicacao_exclusao_solicitada",
            alvo=publicacao,
            detalhes="Exclusão de publicação solicitada por administrador pelo painel Wagtail.",
        )
        return None

    if is_reviewer(request.user) and not is_author(request.user):
        return _bloquear_com_mensagem(
            request,
            "Revisores não podem excluir publicações. Use o Fluxo editorial para rejeitar ou solicitar ajustes.",
        )

    autor = _autor_vinculado_do_usuario(request.user)
    if not autor:
        return _bloquear_com_mensagem(
            request,
            "Seu usuário não possui autor vinculado. Fale com um administrador.",
        )

    if not _publicacao_pertence_ao_autor(publicacao, autor):
        return _bloquear_com_mensagem(
            request,
            "Você só pode excluir publicações do seu autor vinculado.",
        )

    registrar_auditoria(
        request=request,
        acao="publicacao_exclusao_solicitada",
        alvo=publicacao,
        detalhes="Exclusão de publicação solicitada pelo painel Wagtail.",
    )
    return None


@hooks.register("after_publish_page")
def disparar_email_publicacao_imediata(request, page):
    if not isinstance(page.specific, PublicacaoPage):
        return None

    publicacao = page.specific
    status = (
        PublicacaoPage.STATUS_EDITORIAL_AGENDADO
        if publicacao.go_live_at and publicacao.go_live_at > timezone.now()
        else PublicacaoPage.STATUS_EDITORIAL_PUBLICADO
    )
    PublicacaoPage.objects.filter(id=publicacao.id).update(
        status_editorial=status,
        publicado_em=None if status == PublicacaoPage.STATUS_EDITORIAL_AGENDADO else timezone.now(),
        publicado_por=request.user if request.user.is_authenticated else None,
        reabertura_solicitada=False,
    )
    if status == PublicacaoPage.STATUS_EDITORIAL_AGENDADO:
        registrar_auditoria(
            request=request,
            acao="publicacao_agendada",
            alvo=publicacao,
            detalhes="Publicação agendada pelo painel Wagtail.",
        )
        return None
    registrar_auditoria(
        request=request,
        acao="publicacao_publicada",
        alvo=publicacao,
        detalhes="Publicação publicada pelo painel Wagtail.",
    )

    # Disparo imediato apenas na primeira publicação.
    if not publicacao.first_published_at or not publicacao.last_published_at:
        return None
    if publicacao.first_published_at != publicacao.last_published_at:
        return None

    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    if not site:
        return None

    disparo = enviar_publicacoes_imediata(site, publicacao)
    if disparo:
        registrar_auditoria(
            request=request,
            acao="email_publicacao_imediata_disparada",
            alvo=disparo,
            detalhes=(
                f"Publicação: {publicacao.id}. Destinatários: {disparo.total_destinatarios}. "
                f"Enviados: {disparo.total_enviados}. Falhas: {disparo.total_falhas}."
            ),
        )
    return None



def _pode_acessar_submissoes(user):
    return is_admin(user) or is_reviewer(user)


def _gerar_username_autor_publico(usuario_publico):
    base = normalizar_username_publico(getattr(usuario_publico, "username", "") or "")
    if not base:
        base = slugify(getattr(usuario_publico, "nome", "") or "autor") or "autor"
    candidato = base[:80]
    contador = 2
    while Autor.objects.filter(username=candidato).exists():
        sufixo = f"-{contador}"
        candidato = f"{base[:80 - len(sufixo)]}{sufixo}"
        contador += 1
    return candidato


def _obter_ou_criar_autor_submissao(submissao):
    if submissao.autor_vinculado_id:
        return submissao.autor_vinculado
    usuario = submissao.usuario
    autor = None
    if usuario.orcid:
        autor = Autor.objects.filter(orcid__iexact=usuario.orcid).first()
    if not autor and usuario.email:
        autor = Autor.objects.filter(email__iexact=usuario.email).first()
    if not autor:
        nome_completo = submissao.ficha_nome_completo or usuario.nome or usuario.username
        autor = Autor.objects.create(
            nome_completo=nome_completo,
            nome_exibicao=submissao.ficha_nome_exibicao or nome_completo,
            username=_gerar_username_autor_publico(usuario),
            orcid=usuario.orcid or "",
            email=usuario.email,
            mini_bio=submissao.ficha_mini_bio,
            instagram=submissao.ficha_instagram,
            mastodon=submissao.ficha_mastodon,
            lattes_url=submissao.ficha_lattes_url,
        )
    else:
        updates = []
        for campo_sub, campo_autor in [
            ("ficha_nome_completo", "nome_completo"),
            ("ficha_nome_exibicao", "nome_exibicao"),
            ("ficha_mini_bio", "mini_bio"),
            ("ficha_instagram", "instagram"),
            ("ficha_mastodon", "mastodon"),
            ("ficha_lattes_url", "lattes_url"),
        ]:
            valor = getattr(submissao, campo_sub, "")
            if valor and not getattr(autor, campo_autor, ""):
                setattr(autor, campo_autor, valor)
                updates.append(campo_autor)
        if updates:
            autor.save(update_fields=updates)
    submissao.autor_vinculado = autor
    submissao.save(update_fields=["autor_vinculado", "atualizado_em"])
    return autor


def _richtext_de_texto_simples(texto):
    paragrafos = []
    for bloco in re.split(r"\n{2,}", strip_tags(texto or "").strip()):
        bloco = bloco.strip()
        if bloco:
            paragrafos.append(f"<p>{escape(bloco).replace(chr(10), '<br>')}</p>")
    return "".join(paragrafos)


def submissoes_publicas_admin_view(request):
    if not _pode_acessar_submissoes(request.user):
        return _negar_acesso_admin(request)
    q = strip_tags((request.GET.get("q") or "").strip())
    status = strip_tags((request.GET.get("status") or "").strip())
    submissoes = SubmissaoPublica.objects.select_related("usuario", "autor_vinculado", "publicacao_criada").all()
    if q:
        submissoes = submissoes.filter(
            Q(titulo__icontains=q)
            | Q(resumo__icontains=q)
            | Q(usuario__email__icontains=q)
            | Q(usuario__username__icontains=q)
            | Q(usuario__orcid__icontains=q)
            | Q(arquivo_sha256__icontains=q)
        )
    if status:
        submissoes = submissoes.filter(status=status)
    paginator = Paginator(submissoes, 25)
    page_obj = paginator.get_page(request.GET.get("p"))
    return render(
        request,
        "conteudo/admin_submissoes_publicas.html",
        {
            "page_obj": page_obj,
            "submissoes": page_obj.object_list,
            "status_choices": SubmissaoPublica.STATUS_CHOICES,
            "filtro_q": q,
            "filtro_status": status,
        },
    )


def submissao_publica_admin_detalhe_view(request, submissao_id):
    if not _pode_acessar_submissoes(request.user):
        return _negar_acesso_admin(request)
    submissao = get_object_or_404(
        SubmissaoPublica.objects.select_related("usuario", "autor_vinculado", "publicacao_criada"),
        id=submissao_id,
    )
    if request.method == "POST":
        acao = (request.POST.get("acao") or "").strip()
        observacao = strip_tags((request.POST.get("observacao_admin") or "").strip())[:5000]
        if acao in {"aceitar", "rejeitar"}:
            submissao.status = (
                SubmissaoPublica.STATUS_ACEITA
                if acao == "aceitar"
                else SubmissaoPublica.STATUS_REJEITADA
            )
            submissao.observacao_admin = observacao
            submissao.decidido_por = request.user
            submissao.decidido_em = timezone.now()
            submissao.save(
                update_fields=[
                    "status",
                    "observacao_admin",
                    "decidido_por",
                    "decidido_em",
                    "atualizado_em",
                ]
            )
            registrar_auditoria(
                request=request,
                acao=f"submissao_publica_{acao}",
                alvo=submissao,
                detalhes=f"Submissão {submissao.id}: {submissao.titulo}.",
            )
            if acao == "aceitar":
                link = request.build_absolute_uri(
                    reverse("submissao_publica_completar", args=[submissao.token_acesso])
                )
                try:
                    EmailMessage(
                        subject=f"Sua submissão foi aceita: {submissao.titulo}",
                        body=(
                            "Sua submissão foi aceita para continuidade editorial.\n\n"
                            "Complete sua ficha de autoria e envie o texto final pelo link abaixo:\n"
                            f"{link}\n\n"
                            "Este link é pessoal. Não compartilhe."
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[submissao.usuario.email],
                    ).send(fail_silently=True)
                except Exception:
                    logger.exception("Falha ao enviar aceite de submissão pública.")
            messages.success(request, "Decisão salva.")
            return redirect("admin_submissao_publica_detalhe", submissao_id=submissao.id)

        if acao == "converter":
            if submissao.publicacao_criada_id:
                messages.warning(request, "Esta submissão já foi convertida.")
                return redirect("admin_submissao_publica_detalhe", submissao_id=submissao.id)
            if not submissao.texto_final:
                messages.error(request, "A ficha e o texto final ainda não foram enviados pelo autor.")
                return redirect("admin_submissao_publica_detalhe", submissao_id=submissao.id)
            index = PublicacoesIndexPage.objects.live().first() or PublicacoesIndexPage.objects.first()
            if not index:
                messages.error(request, "Nenhuma pasta de publicações foi encontrada.")
                return redirect("admin_submissao_publica_detalhe", submissao_id=submissao.id)
            autor = _obter_ou_criar_autor_submissao(submissao)
            publicacao = PublicacaoPage(
                title=submissao.titulo,
                slug=slugify(submissao.titulo)[:80] or f"submissao-{submissao.id}",
                resumo=_richtext_de_texto_simples(submissao.resumo),
                corpo=_richtext_de_texto_simples(submissao.texto_final),
                status_editorial=PublicacaoPage.STATUS_EDITORIAL_RASCUNHO,
                revisao_solicitada_por=request.user,
            )
            base_slug = publicacao.slug
            contador = 2
            while Page.objects.child_of(index).filter(slug=publicacao.slug).exists():
                sufixo = f"-{contador}"
                publicacao.slug = f"{base_slug[:80 - len(sufixo)]}{sufixo}"
                contador += 1
            index.add_child(instance=publicacao)
            PublicacaoPageAutor.objects.create(
                publicacao=publicacao,
                autor=autor,
                confirmacao_status=PublicacaoPageAutor.STATUS_CONFIRMACAO_CONFIRMADO,
                atribuido_por=request.user,
                atribuido_em=timezone.now(),
                confirmado_por=request.user,
                confirmado_em=timezone.now(),
            )
            publicacao.save_revision(user=request.user)
            submissao.publicacao_criada = publicacao
            submissao.status = SubmissaoPublica.STATUS_CONVERTIDA
            submissao.save(update_fields=["publicacao_criada", "status", "atualizado_em"])
            registrar_auditoria(
                request=request,
                acao="submissao_publica_convertida_publicacao",
                alvo=publicacao,
                detalhes=f"Submissão {submissao.id} convertida em publicação {publicacao.id}.",
            )
            messages.success(request, "Publicação criada em rascunho.")
            return redirect("wagtailadmin_pages:edit", publicacao.id)

    return render(
        request,
        "conteudo/admin_submissao_publica_detalhe.html",
        {"submissao": submissao},
    )


def submissao_publica_pdf_admin_view(request, submissao_id):
    if not _pode_acessar_submissoes(request.user):
        return _negar_acesso_admin(request)
    submissao = get_object_or_404(SubmissaoPublica, id=submissao_id)
    if not submissao.arquivo_pdf:
        messages.error(request, "Arquivo não encontrado.")
        return redirect("admin_submissao_publica_detalhe", submissao_id=submissao.id)
    registrar_auditoria(
        request=request,
        acao="submissao_publica_pdf_aberto",
        alvo=submissao,
        detalhes=f"PDF aberto para avaliação: submissão {submissao.id}.",
    )
    return FileResponse(
        submissao.arquivo_pdf.open("rb"),
        content_type="application/pdf",
        filename=f"submissao-{submissao.id}.pdf",
    )


@hooks.register("register_admin_urls")
def register_admin_urls():
    return [
        path(
            "busca/",
            admin_busca_global_view,
            name="admin_busca_global",
        ),
        path(
            "publicacoes/",
            publicacoes_admin_view,
            name="admin_publicacoes_lista",
        ),
        path(
            "midias-pendentes/",
            midias_pendentes_admin_view,
            name="admin_midias_pendentes",
        ),
        path(
            "midias-pendentes/<int:midia_id>/preview/",
            midia_pendente_preview_admin_view,
            name="admin_midia_pendente_preview",
        ),
        path(
            "midias-pendentes/<int:midia_id>/<slug:acao>/",
            midia_pendente_acao_admin_view,
            name="admin_midia_pendente_acao",
        ),
        path(
            "submissoes/",
            submissoes_publicas_admin_view,
            name="admin_submissoes_publicas",
        ),
        path(
            "submissoes/<int:submissao_id>/",
            submissao_publica_admin_detalhe_view,
            name="admin_submissao_publica_detalhe",
        ),
        path(
            "submissoes/<int:submissao_id>/pdf/",
            submissao_publica_pdf_admin_view,
            name="admin_submissao_publica_pdf",
        ),
        path(
            "perguntas-quiz/",
            quiz_catalogo_admin_view,
            name="admin_quiz_catalogo_lista",
        ),
        path(
            "categorias-tags/",
            categorias_tags_admin_view,
            name="admin_categorias_tags",
        ),
        path(
            "configuracoes-site/",
            configuracoes_site_admin_view,
            name="admin_configuracoes_site",
        ),
        path(
            "configuracoes-site/<slug:secao_slug>/",
            configuracoes_site_secao_admin_view,
            name="admin_configuracoes_site_secao",
        ),
        path(
            "configuracoes-site/imagem-preview/<int:image_id>/",
            configuracoes_site_imagem_preview_admin_view,
            name="admin_configuracoes_site_imagem_preview",
        ),
        path(
            "backups/",
            backups_admin_view,
            name="admin_backups",
        ),
        path(
            "backups/download/<int:backup_id>/<str:token>/",
            backup_download_temporario_admin_view,
            name="admin_backup_download",
        ),
        path(
            "saude/",
            saude_operacional_admin_view,
            name="admin_saude_operacional",
        ),
        path(
            "navegacao/",
            navegacao_admin_view,
            name="admin_navegacao",
        ),
        path(
            "configuracoes-home/",
            configuracoes_home_admin_view,
            name="admin_configuracoes_home",
        ),
        path(
            "usuarios/reset-senha/",
            usuarios_reset_senha_admin_view,
            name="admin_usuarios_reset_senha",
        ),
        path(
            "usuarios/",
            usuarios_admin_lista_view,
            name="admin_usuarios_lista",
        ),
        path(
            "usuarios/<int:usuario_id>/",
            usuario_admin_editar_view,
            name="admin_usuario_editar",
        ),
        path(
            "usuarios/mudancas-admin/<int:solicitacao_id>/confirmar/",
            usuario_admin_confirmar_mudanca_view,
            name="admin_usuario_confirmar_mudanca_admin",
        ),
        path(
            "usuarios/reset-2fa/",
            usuarios_reset_2fa_admin_view,
            name="admin_usuarios_reset_2fa",
        ),
        path(
            "usuarios/logs-atividade/",
            logs_atividade_admin_view,
            name="admin_logs_atividade",
        ),
        path(
            "estatisticas/",
            estatisticas_admin_view,
            name="admin_estatisticas",
        ),
        path(
            "contato/inbox/",
            contato_inbox_admin_view,
            name="admin_contato_inbox",
        ),
        path(
            "contato/inbox/<int:mensagem_id>/",
            contato_mensagem_admin_view,
            name="admin_contato_mensagem",
        ),
        path(
            "publicacoes/<int:publicacao_id>/fluxo-editorial/",
            publicacao_fluxo_editorial_admin_view,
            name="admin_publicacao_fluxo_editorial",
        ),
        path(
            "email/",
            email_admin_view,
            name="admin_email",
        ),
        path(
            "email/disparos/",
            email_disparos_admin_view,
            name="admin_email_disparos",
        ),
        path(
            "email/templates/",
            email_templates_admin_view,
            name="admin_email_templates",
        ),
        path(
            "email/disparos/<int:disparo_id>/",
            email_disparo_detalhe_admin_view,
            name="admin_email_disparo_detalhe",
        ),
        path(
            "email/publicacoes/",
            email_publicacoes_admin_view,
            name="admin_email_publicacoes",
        ),
        path(
            "minha-conta/",
            minha_conta_admin_view,
            name="admin_minha_conta",
        ),
        path(
            "indexador/",
            indexador_admin_view,
            name="admin_indexador",
        ),
        path(
            "indexador/importar-csv/",
            importar_csv_indexador_view,
            name="admin_indexador_importar_csv",
        ),
        path(
            "indexador/modelo-csv/",
            modelo_csv_indexador_view,
            name="admin_indexador_modelo_csv",
        ),
        path(
            "newsletter/",
            newsletter_admin_view,
            name="admin_newsletter",
        ),
        path(
            "newsletter/importar-csv/",
            importar_csv_newsletter_view,
            name="admin_newsletter_importar_csv",
        ),
        path(
            "newsletter/modelo-csv/",
            modelo_csv_newsletter_view,
            name="admin_newsletter_modelo_csv",
        ),
    ]


class AdminGlobalSearchArea(SearchArea):
    def __init__(self):
        super().__init__(
            "Busca do painel",
            reverse("admin_busca_global"),
            name="admin-global-search",
            icon_name="search",
            order=1,
        )

    def is_shown(self, request):
        return _pode_acessar_admin_basico(request.user)


@hooks.register("register_admin_search_area")
def register_admin_global_search_area():
    return AdminGlobalSearchArea()


@hooks.register("register_admin_menu_item")
def register_publicacoes_menu_item():
    return MenuItem(
        "Publicações",
        reverse("admin_publicacoes_lista"),
        name="admin-publicacoes",
        icon_name="doc-full",
        order=832,
    )


@hooks.register("register_admin_menu_item")
def register_midias_pendentes_menu_item():
    return MenuItem(
        "Mídias pendentes",
        reverse("admin_midias_pendentes"),
        name="admin-midias-pendentes",
        icon_name="image",
        order=831,
    )


@hooks.register("register_admin_menu_item")
def register_submissoes_publicas_menu_item():
    return MenuItem(
        "Submissões",
        reverse("admin_submissoes_publicas"),
        name="admin-submissoes-publicas",
        icon_name="form",
        order=830,
    )


@hooks.register("register_admin_menu_item")
def register_indexador_menu_item():
    return SubmenuMenuItem(
        "Indexador",
        Menu(
            items=[
                MenuItem(
                    "Registros do indexador",
                    reverse("wagtailsnippets_conteudo_registroindexador:list"),
                    icon_name="doc-full",
                    order=2,
                ),
                MenuItem(
                    "Importar indexador",
                    reverse("admin_indexador_importar_csv"),
                    icon_name="download",
                    order=1,
                ),
            ]
        ),
        name="admin-indexador",
        icon_name="search",
        order=828,
    )


@hooks.register("register_admin_menu_item")
def register_autores_menu_item():
    return MenuItem(
        "Autores",
        reverse("wagtailsnippets_conteudo_autor:list"),
        name="admin-autores",
        icon_name="user",
        order=820,
    )


@hooks.register("register_admin_menu_item")
def register_quiz_catalogo_menu_item():
    return MenuItem(
        "Perguntas do quiz",
        reverse("admin_quiz_catalogo_lista"),
        name="admin-quiz-catalogo",
        icon_name="help",
        order=819,
    )


@hooks.register("register_admin_menu_item")
def register_categorias_tags_menu_item():
    return SubmenuMenuItem(
        "Categorias e Tags",
        Menu(
            items=[
                MenuItem(
                    "Categorias",
                    reverse("wagtailsnippets_conteudo_categoria:list"),
                    icon_name="folder-open-1",
                    order=1,
                ),
                MenuItem(
                    "Tags",
                    reverse("wagtailsnippets_conteudo_tagpublicacao:list"),
                    icon_name="tag",
                    order=2,
                ),
            ]
        ),
        name="admin-categorias-tags",
        icon_name="folder-open-1",
        order=822,
    )


@hooks.register("register_admin_menu_item")
def register_menu_principal_menu_item():
    return MenuItem(
        "Menu e rodapé",
        reverse("admin_navegacao"),
        name="admin-navegacao",
        icon_name="list-ul",
        order=830,
    )


@hooks.register("register_admin_menu_item")
def register_newsletter_menu_item():
    return SubmenuMenuItem(
        "Newsletter",
        Menu(
            items=[
                MenuItem(
                    "Inscritos",
                    reverse("wagtailsnippets_conteudo_inscritonewsletter:list"),
                    icon_name="mail",
                    order=3,
                ),
                MenuItem(
                    "Eventos (log)",
                    reverse("wagtailsnippets_conteudo_newsletterevento:list"),
                    icon_name="history",
                    order=1,
                ),
                MenuItem(
                    "Solicitações de privacidade",
                    reverse("wagtailsnippets_conteudo_solicitacaoprivacidadenewsletter:list"),
                    icon_name="warning",
                    order=4,
                ),
                MenuItem(
                    "Importar inscritos (CSV)",
                    reverse("admin_newsletter_importar_csv"),
                    icon_name="download",
                    order=2,
                ),
            ]
        ),
        name="admin-newsletter",
        icon_name="mail",
        order=831,
    )


@hooks.register("register_admin_menu_item")
def register_contato_menu_item():
    return MenuItem(
        "Contato (Inbox)",
        reverse("admin_contato_inbox"),
        name="admin-contato-inbox",
        icon_name="mail",
        order=826,
    )


@hooks.register("register_admin_menu_item")
def register_comentarios_menu_item():
    return MenuItem(
        "Comentários",
        reverse("wagtailsnippets_conteudo_comentariopublicacao:list"),
        name="admin-comentarios",
        icon_name="comment",
        order=823,
    )


@hooks.register("register_admin_menu_item")
def register_duvidas_quiz_menu_item():
    return MenuItem(
        "Dúvidas do quiz",
        reverse("wagtailsnippets_conteudo_duvidaquizpublicacao:list"),
        name="admin-duvidas-quiz",
        icon_name="help",
        order=823,
    )


@hooks.register("register_admin_menu_item")
def register_links_curtos_menu_item():
    return MenuItem(
        "Links curtos",
        reverse("wagtailsnippets_conteudo_linkcurtoshlink:list"),
        name="admin-links-curtos",
        icon_name="link",
        order=823,
    )


@hooks.register("register_admin_menu_item")
def register_identidades_externas_menu_item():
    return MenuItem(
        "Identidades externas",
        reverse("wagtailsnippets_conteudo_identidadeexternacomentario:list"),
        name="admin-identidades-externas",
        icon_name="user",
        order=823,
    )


@hooks.register("register_admin_menu_item")
def register_email_menu_item():
    return SubmenuMenuItem(
        "E-mails",
        Menu(
            items=[
                MenuItem(
                    "Disparo em massa",
                    reverse("admin_email_disparos"),
                    icon_name="mail",
                    order=1,
                ),
                MenuItem(
                    "Templates de campanha",
                    reverse("admin_email_templates"),
                    icon_name="snippet",
                    order=3,
                ),
                MenuItem(
                    "Notificações de publicações",
                    reverse("admin_email_publicacoes"),
                    icon_name="doc-full",
                    order=2,
                ),
            ]
        ),
        name="admin-email",
        icon_name="mail",
        order=827,
    )


@hooks.register("register_admin_menu_item")
def register_backups_menu_item():
    return MenuItem(
        "Backups",
        reverse("admin_backups"),
        name="admin-backups",
        icon_name="download",
        order=821,
    )


@hooks.register("register_admin_menu_item")
def register_saude_operacional_menu_item():
    return MenuItem(
        "Saúde do sistema",
        reverse("admin_saude_operacional"),
        name="admin-saude-operacional",
        icon_name="warning",
        order=822,
    )


@hooks.register("register_admin_menu_item")
def register_estatisticas_menu_item():
    return MenuItem(
        "Estatísticas",
        reverse("admin_estatisticas"),
        name="admin-estatisticas",
        icon_name="site",
        order=823,
    )


@hooks.register("insert_global_admin_css")
def custom_admin_theme_css():
    return format_html_join(
        "",
        '<link rel="stylesheet" href="{}">',
        (
            (static("css/admin-global-theme.css"),),
        ),
    )


@hooks.register("insert_global_admin_js")
def custom_admin_zoom_js():
    return format_html(
        """
        <script>
        (function () {{
            var fixedSidebar = document.createElement("script");
            fixedSidebar.src = "{}";
            fixedSidebar.defer = true;
            document.head.appendChild(fixedSidebar);

            var path = window.location.pathname || "";
            if (path === "/admin/" || /^\\/admin\\/pages\\/\\d+\\/edit\\/?$/.test(path)) {{
                return;
            }}
            [
                "{}",
                "{}"
            ].forEach(function (src) {{
                var script = document.createElement("script");
                script.src = src;
                script.defer = true;
                document.head.appendChild(script);
            }});
        }}());
        </script>
        """,
        static("js/admin/fixed-sidebar.js"),
        static("js/admin/account-label.js"),
        static("js/admin/admin-search.js"),
    )


class BackupCodesAccountSettingsPanel:
    name = "backup_codes"
    title = "Backup codes do 2FA"
    order = 510

    def __init__(self, request, user, profile):
        from wagtail.admin.views.account import profile_tab

        self.request = request
        self.user = user
        self.profile = profile
        self.tab = profile_tab

    def is_active(self):
        return self.user.has_usable_password()

    def _should_bind(self):
        if self.request.method != "POST":
            return False
        return any(
            key.startswith(f"{self.name}-") and (self.request.POST.get(key) or "").strip()
            for key in self.request.POST.keys()
        )

    def get_form(self):
        data = self.request.POST if self._should_bind() else None
        return BackupCodesAccountForm(
            self.user,
            request=self.request,
            data=data,
            prefix=self.name,
        )

    def get_context_data(self):
        backup_codes_gerados = []
        if self.request.method != "POST":
            backup_codes_gerados = self.request.session.pop("backup_codes_gerados", [])
        return {
            "form": self.get_form(),
            "backup_codes_gerados": backup_codes_gerados,
            "total_backup_codes": total_backup_codes_usuario(self.user),
            "tem_totp": usuario_tem_totp(self.user),
        }

    def render(self):
        return render_to_string(
            "conteudo/account_backup_codes_panel.html",
            self.get_context_data(),
            request=self.request,
        )


@hooks.register("register_account_settings_panel")
def register_backup_codes_account_panel(request, user, profile):
    return BackupCodesAccountSettingsPanel(request, user, profile)


@hooks.register("register_admin_menu_item")
def register_usuarios_menu_item():
    return SubmenuMenuItem(
        "Usuários",
        Menu(
            items=[
                MenuItem(
                    "Gerenciar usuários",
                    reverse("admin_usuarios_lista"),
                    icon_name="group",
                    order=3,
                ),
                MenuItem(
                    "Convites de usuários",
                    reverse("wagtailsnippets_conteudo_conviteusuario:list"),
                    icon_name="mail",
                    order=1,
                ),
                MenuItem(
                    "Disparar reset de senha",
                    reverse("admin_usuarios_reset_senha"),
                    icon_name="mail",
                    order=2,
                ),
                MenuItem(
                    "Reset de 2FA",
                    reverse("admin_usuarios_reset_2fa"),
                    icon_name="warning",
                    order=5,
                ),
                MenuItem(
                    "Logs de atividade",
                    reverse("admin_logs_atividade"),
                    icon_name="history",
                    order=4,
                ),
            ]
        ),
        name="admin-usuarios",
        icon_name="group",
        order=833,
    )


@hooks.register("register_admin_menu_item")
def register_configuracoes_site_menu_item():
    return MenuItem(
        "Configurações do site",
        reverse("admin_configuracoes_site"),
        name="admin-configuracoes-site",
        icon_name="cogs",
        order=825,
    )


@hooks.register("register_admin_menu_item")
def register_configuracoes_home_menu_item():
    return MenuItem(
        "Configurações do Início",
        reverse("admin_configuracoes_home"),
        name="admin-config-home",
        icon_name="home",
        order=824,
    )


@hooks.register("construct_main_menu")
def remover_menu_fragmentos(request, menu_items):
    itens_ativos = [
        item for item in menu_items if getattr(item, "name", "") != "snippets"
    ]
    mapa_itens = {
        getattr(item, "name", ""): item
        for item in itens_ativos
        if getattr(item, "name", "")
    }
    site_admin = _resolver_site_admin(request)
    explorer_item = mapa_itens.get("explorer")
    if explorer_item is not None and site_admin is not None and site_admin.root_page_id:
        mapa_itens["explorer"] = MenuItem(
            getattr(explorer_item, "label", "Páginas"),
            reverse("wagtailadmin_explore", args=[site_admin.root_page_id]),
            name="explorer",
            classname=getattr(explorer_item, "classname", ""),
            icon_name=getattr(explorer_item, "icon_name", "folder-open-inverse"),
            attrs=getattr(explorer_item, "attrs", {}),
            order=getattr(explorer_item, "order", 1000),
        )

    reports_item = mapa_itens.get("reports")
    reports_submenu = getattr(reports_item, "menu", None)
    reports_items = _extract_menu_items(reports_submenu)
    if reports_items:
        reports_items = [
            item
            for item in reports_items
            if getattr(item, "name", "")
            not in {"workflows", "workflow-tasks"}
            and "fluxo de trabalho" not in _normalize_menu_label(getattr(item, "label", ""))
            and "fluxos de trabalho" not in _normalize_menu_label(getattr(item, "label", ""))
        ]
        _assign_menu_items(reports_submenu, reports_items)

    settings_diretos = []
    settings_item = mapa_itens.get("settings")
    settings_permitidos = {"redirects"}
    for item in _extract_menu_items(getattr(settings_item, "menu", None)):
        item_name = getattr(item, "name", "")
        if item_name not in settings_permitidos:
            continue
        nome_mapeado = f"settings-{item_name}"
        mapa_itens[nome_mapeado] = item
        settings_diretos.append(nome_mapeado)
    if not settings_diretos:
        settings_fallback = [
            (
                "settings-redirects",
                MenuItem(
                    "Redirecionamentos",
                    reverse("wagtailredirects:index"),
                    name="settings-redirects",
                    icon_name="redirect",
                    order=1,
                ),
            ),
        ]
        for nome_mapeado, item in settings_fallback:
            mapa_itens[nome_mapeado] = item
            settings_diretos.append(nome_mapeado)

    midia_items = []
    for nome in ("admin-midias-pendentes", "images", "documents"):
        item = mapa_itens.get(nome)
        if item is not None:
            midia_items.append(item)
    if midia_items:
        mapa_itens["admin-midias"] = SubmenuMenuItem(
            "Mídias",
            Menu(items=midia_items),
            name="admin-midias",
            icon_name="image",
            order=831,
        )

    if request.user.is_superuser:
        editoriais = [
            "admin-publicacoes",
            "explorer",
            "admin-quiz-catalogo",
            "admin-midias",
            "admin-categorias-tags",
        ]
        operacionais = [
            "admin-contato-inbox",
            "admin-newsletter",
            "admin-email",
            "admin-indexador",
            "admin-comentarios",
            "admin-duvidas-quiz",
            "admin-links-curtos",
        ]
        administrativos = [
            "admin-autores",
            "admin-estatisticas",
            "admin-saude-operacional",
            "admin-usuarios",
            "admin-navegacao",
            "admin-backups",
            "admin-configuracoes-site",
            "admin-config-home",
            "admin-identidades-externas",
            *settings_diretos,
            "reports",
        ]
    else:
        editoriais = []
        if is_author(request.user) or is_reviewer(request.user):
            editoriais = [
                "admin-publicacoes",
                "admin-midias",
                "admin-quiz-catalogo",
                "admin-categorias-tags",
            ]
        operacionais = ["admin-contato-inbox"] if _pode_acessar_admin_contato(request.user) else []
        administrativos = []

    extras = ["help"]

    menu_items[:] = [
        item
        for item in [
            _criar_grupo_menu("Editorial", "grupo-editorial", "doc-full", editoriais, mapa_itens, 810),
            _criar_grupo_menu("Operação", "grupo-operacao", "mail", operacionais, mapa_itens, 820),
            _criar_grupo_menu("Administração", "grupo-administracao", "cogs", administrativos, mapa_itens, 830),
            *[mapa_itens[nome] for nome in extras if nome in mapa_itens],
        ]
        if item is not None
    ]


def _normalize_menu_label(value):
    label = (value or "").strip().casefold()
    normalized = unicodedata.normalize("NFKD", label)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _extract_menu_items(menu_obj):
    if menu_obj is None:
        return []
    if hasattr(menu_obj, "menu_items"):
        return list(menu_obj.menu_items or [])
    if hasattr(menu_obj, "items"):
        return list(menu_obj.items or [])
    return []


def _assign_menu_items(menu_obj, items):
    if menu_obj is None:
        return
    if hasattr(menu_obj, "menu_items"):
        menu_obj.menu_items = items
        return
    if hasattr(menu_obj, "items"):
        menu_obj.items = items


def ordenar_itens_menu_alfabeticamente(menu_items):
    for item in menu_items:
        submenu = getattr(item, "menu", None)
        sub_items = _extract_menu_items(submenu)
        if sub_items:
            sub_items.sort(key=lambda sub: _normalize_menu_label(getattr(sub, "label", "")))
            _assign_menu_items(submenu, sub_items)
    menu_items.sort(key=lambda item: _normalize_menu_label(getattr(item, "label", "")))


def _criar_grupo_menu(label, name, icon_name, item_names, item_map, order):
    items = [item_map[item_name] for item_name in item_names if item_name in item_map]
    if not items:
        return None
    for index, item in enumerate(items, start=1):
        item.order = index
    return SubmenuMenuItem(label, Menu(items=items), name=name, icon_name=icon_name, order=order)


@hooks.register("construct_settings_menu")
def remover_usuarios_legado_do_settings(request, menu_items):
    menu_items[:] = [
        item
        for item in menu_items
        if getattr(item, "name", "")
        not in {
            "users",
            "groups",
            "sites",
            "configuracao-do-site",
            "workflows",
            "workflow-tasks",
            "collections",
        }
    ]


@hooks.register("construct_reports_menu")
def remover_relatorios_workflow_legados(request, menu_items):
    menu_items[:] = [
        item
        for item in menu_items
        if getattr(item, "name", "")
        not in {
            "workflows",
            "workflow-tasks",
        }
        and "fluxo de trabalho" not in _normalize_menu_label(getattr(item, "label", ""))
        and "fluxos de trabalho" not in _normalize_menu_label(getattr(item, "label", ""))
    ]
