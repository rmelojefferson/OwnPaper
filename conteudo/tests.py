import os
import json
import re
import urllib.parse
import base64
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import signing
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from wagtail.admin.menu import MenuItem
from wagtail.images import get_image_model
from wagtail.models import Site

from conteudo.email_ops import destinatarios_por_segmento, executar_disparo
from conteudo.html_safety import sanitize_email_html
from conteudo.access import eligible_contact_assignees
from conteudo.backup_ops import executar_backup_site, simular_restore_backup
from conteudo.wagtail_hooks import (
    _anexar_assinatura_email_html,
    _corpo_inicial_email_com_assinatura,
    _normalizar_status_publicacao_admin,
    email_disparos_admin_view,
    email_disparo_detalhe_admin_view,
    email_publicacoes_admin_view,
    email_templates_admin_view,
    remover_menu_fragmentos,
    remover_usuarios_legado_do_settings,
)
from conteudo.models import (
    AuditLog,
    BackupExecucao,
    ConfiguracaoSite,
    ContatoPage,
    ConviteUsuario,
    DisparoEmail,
    DisparoEmailClique,
    DisparoEmailDestino,
    EstatisticaTempoSite,
    InscritoNewsletter,
    MenuPrincipalGrupo,
    MensagemContato,
    PublicacaoPage,
    PublicacoesIndexPage,
    RodapeLink,
    TemplateEmailCampanha,
    UsuarioPainelPerfil,
)
from conteudo.roles import CONTACT_OPERATORS_GROUP_NAME
from home.models import HomePage


BOOTSTRAP_ENV = {
    "OWNPAPER_SITE_NAME": "OwnPaper Test",
    "OWNPAPER_SITE_HOSTNAME": "testserver",
    "OWNPAPER_SITE_PORT": "80",
    "OWNPAPER_HOME_TITLE": "Início",
    "OWNPAPER_SITE_DESCRIPTION": "OwnPaper test installation.",
    "OWNPAPER_INDEXER_LABEL": "Biblioteca",
}

NO_PANEL_2FA_MIDDLEWARE = [
    item
    for item in settings.MIDDLEWARE
    if item != "config.middleware_two_factor.PanelTwoFactorMiddleware"
]

PUBLIC_TEST_SETTINGS = override_settings(
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"],
    CSRF_TRUSTED_ORIGINS=[],
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    SECURE_HSTS_SECONDS=0,
    SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
    SECURE_HSTS_PRELOAD=False,
    WAGTAILADMIN_BASE_URL="http://testserver",
)


def run_bootstrap():
    output = StringIO()
    with patch.dict(os.environ, BOOTSTRAP_ENV, clear=False):
        call_command("bootstrap_ownpaper", stdout=output)
    return output.getvalue()


def aceitar_termos_painel_teste(*usuarios):
    for usuario in usuarios:
        UsuarioPainelPerfil.objects.update_or_create(
            usuario=usuario,
            defaults={
                "termos_painel_versao": settings.OWNPAPER_PANEL_TERMS_VERSION,
                "aceitou_termos_painel_em": timezone.now(),
                "aceitou_termos_painel_ip": "127.0.0.1",
                "aceitou_termos_painel_user_agent": "OwnPaper tests",
            },
        )


@PUBLIC_TEST_SETTINGS
class BootstrapOwnPaperTests(TestCase):
    def test_bootstrap_creates_default_site_settings_and_pages(self):
        output = run_bootstrap()

        site = Site.objects.get(is_default_site=True)
        home_page = HomePage.objects.get()
        site_settings = ConfiguracaoSite.for_site(site)

        self.assertIn("OwnPaper bootstrap complete", output)
        self.assertEqual(site.hostname, "testserver")
        self.assertEqual(site.port, 80)
        self.assertEqual(site.root_page_id, home_page.id)
        self.assertEqual(site_settings.nome_site, "OwnPaper Test")
        self.assertEqual(site_settings.rotulo_indexador, "Biblioteca")
        self.assertEqual(
            site_settings.tema_padrao_site,
            ConfiguracaoSite.TEMA_PADRAO_CLARO,
        )
        self.assertNotIn(
            ("sistema", "Sistema"),
            ConfiguracaoSite.TEMA_PADRAO_CHOICES,
        )

        for slug in [
            "sobre",
            "privacidade",
            "cookies",
            "contato",
            "newsletter",
            "indexador",
            "quiz",
        ]:
            self.assertEqual(home_page.get_children().filter(slug=slug).count(), 1)

    def test_bootstrap_is_idempotent(self):
        run_bootstrap()
        run_bootstrap()

        home_page = HomePage.objects.get()

        self.assertEqual(HomePage.objects.count(), 1)
        self.assertEqual(Site.objects.filter(is_default_site=True).count(), 1)

        for slug in [
            "sobre",
            "privacidade",
            "cookies",
            "contato",
            "newsletter",
            "indexador",
            "quiz",
        ]:
            self.assertEqual(home_page.get_children().filter(slug=slug).count(), 1)


@PUBLIC_TEST_SETTINGS
class SmokeRouteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_bootstrap()
        pasta_publicacoes = PublicacoesIndexPage.objects.first()
        publicacao = PublicacaoPage(
            title="Publicacao RSS Teste",
            slug="publicacao-rss-teste",
            resumo="<p>Resumo para validar feed RSS.</p>",
            corpo="<p>Corpo da publicação para feed RSS.</p>",
        )
        pasta_publicacoes.add_child(instance=publicacao)
        publicacao.save_revision().publish()

    def test_public_routes_respond(self):
        for path in [
            "/",
            "/busca/",
            "/categorias/",
            "/autores/",
            "/tags/",
            "/indexador/",
            "/quiz/",
            "/rss.xml",
            "/feed/",
            "/robots.txt",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertLess(response.status_code, 500)

    def test_rss_returns_xml_content_type_and_item(self):
        response = self.client.get("/rss.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/rss+xml", response["Content-Type"])
        self.assertContains(response, "<rss")
        self.assertContains(response, "<item>")
        self.assertContains(response, "Publicacao RSS Teste")

    def test_menu_social_links_usam_ordem_alfabetica(self):
        config_site = ConfiguracaoSite.for_site(Site.objects.get(is_default_site=True))
        config_site.social_facebook_url = "https://facebook.com/ownpaper"
        config_site.social_instagram_url = "https://instagram.com/ownpaper"
        config_site.social_linkedin_url = "https://linkedin.com/company/ownpaper"
        config_site.social_x_url = "https://x.com/ownpaper"
        config_site.social_youtube_url = "https://youtube.com/@ownpaper"
        config_site.save(
            update_fields=[
                "social_facebook_url",
                "social_instagram_url",
                "social_linkedin_url",
                "social_x_url",
                "social_youtube_url",
            ]
        )

        response = self.client.get("/")
        html = response.content.decode()
        ordem = [
            html.index('aria-label="Facebook"'),
            html.index('aria-label="Instagram"'),
            html.index('aria-label="LinkedIn"'),
            html.index('aria-label="X"'),
            html.index('aria-label="YouTube"'),
        ]
        self.assertEqual(ordem, sorted(ordem))

    def test_admin_routes_are_reachable(self):
        admin_response = self.client.get("/admin/")
        self.assertEqual(admin_response.status_code, 302)
        self.assertIn("/account/login/", admin_response["Location"])

        login_response = self.client.get("/account/login/")
        self.assertEqual(login_response.status_code, 200)
        self.assertContains(login_response, "Nome de usuário")
        self.assertContains(login_response, "Senha")
        self.assertContains(login_response, "Entrar")
        self.assertContains(login_response, "Esqueci minha senha")
        self.assertNotContains(login_response, "Próximo")
        self.assertNotContains(login_response, "Início")
        self.assertNotContains(login_response, "Voltar")

    def test_custom_indexer_import_admin_url_is_registered(self):
        import_url = reverse("admin_indexador_importar_csv")
        model_url = reverse("admin_indexador_modelo_csv")
        navegacao_url = reverse("admin_navegacao")
        backups_url = reverse("admin_backups")
        disparo_detalhe_url = reverse("admin_email_disparo_detalhe", args=[1])
        templates_email_url = reverse("admin_email_templates")

        self.assertEqual(import_url, "/admin/indexador/importar-csv/")
        self.assertEqual(model_url, "/admin/indexador/modelo-csv/")
        self.assertEqual(navegacao_url, "/admin/navegacao/")
        self.assertEqual(backups_url, "/admin/backups/")
        self.assertEqual(disparo_detalhe_url, "/admin/email/disparos/1/")
        self.assertEqual(templates_email_url, "/admin/email/templates/")

        response = self.client.get(import_url)
        self.assertEqual(response.status_code, 302)

    def test_demo_routes_removed(self):
        for path in [
            "/demo/paletas-admin/",
            "/demo/admin-home-doks/",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)


@PUBLIC_TEST_SETTINGS
@override_settings(MIDDLEWARE=NO_PANEL_2FA_MIDDLEWARE)
class PanelTermsConsentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_bootstrap()
        User = get_user_model()
        cls.admin = User.objects.create_user(
            username="admin_terms",
            email="admin_terms@example.com",
            password="Senha@12345",
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )

    def test_painel_exige_aceite_de_termos_para_usuario_staff(self):
        self.client.force_login(self.admin)
        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/admin/aceite-termos-painel/?next=/admin/")

    def test_aceite_de_termos_registra_perfil_e_auditoria(self):
        self.client.force_login(self.admin)
        antes = AuditLog.objects.filter(acao="painel_termos_aceitos", usuario=self.admin).count()
        response = self.client.post(
            reverse("admin_aceite_termos_painel"),
            {
                "aceitou_termos_painel": "1",
                "next": "/admin/",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/admin/")
        perfil = UsuarioPainelPerfil.objects.get(usuario=self.admin)
        self.assertTrue(perfil.aceitou_termos_painel_atuais())
        depois = AuditLog.objects.filter(acao="painel_termos_aceitos", usuario=self.admin).count()
        self.assertEqual(depois, antes + 1)


@PUBLIC_TEST_SETTINGS
@override_settings(MIDDLEWARE=NO_PANEL_2FA_MIDDLEWARE)
class AdminExplorerHomeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_bootstrap()
        User = get_user_model()
        cls.admin = User.objects.create_user(
            username="admin_explorer",
            email="admin_explorer@example.com",
            password="Senha@12345",
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        aceitar_termos_painel_teste(cls.admin)

    def test_admin_home_renderiza_explorador(self):
        self.client.force_login(self.admin)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="wagtail-sidebar-props"')
        self.assertContains(response, "w-dashboard")
        self.assertContains(response, "Páginas e conteúdo")
        self.assertContains(response, "Relacionamento e campanhas")
        self.assertContains(response, "Configuração e Fluxo editorial")
        self.assertContains(response, "Visão rápida do site")
        self.assertContains(response, "Ver estatísticas completas")
        self.assertContains(response, "op-admin-dashboard-stats__desktop-grid")
        self.assertNotContains(response, "op-admin-dashboard-summary--quick-stats")
        self.assertContains(response, "op-admin-metric-card")
        self.assertContains(response, 'href="/admin/snippets/conteudo/comentariopublicacao/"', html=False)
        self.assertContains(response, 'href="/admin/categorias-tags/"', html=False)
        self.assertContains(response, 'href="/admin/newsletter/"', html=False)
        self.assertContains(response, 'href="/admin/email/"', html=False)
        self.assertContains(response, 'href="/admin/indexador/"', html=False)

    def test_admin_categorias_tags_renderiza_hub_de_taxonomias(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_categorias_tags"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Categorias e Tags")
        self.assertContains(response, "Abrir categorias")
        self.assertContains(response, "Abrir tags")
        self.assertContains(response, 'href="/admin/snippets/conteudo/categoria/"', html=False)
        self.assertContains(response, 'href="/admin/snippets/conteudo/tagpublicacao/"', html=False)

    def test_admin_newsletter_renderiza_hub_de_newsletter(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_newsletter"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Newsletter")
        self.assertContains(response, "Abrir inscritos")
        self.assertContains(response, "Importar inscritos")
        self.assertContains(response, "Abrir eventos")
        self.assertContains(response, "Abrir solicitações")
        self.assertContains(response, 'href="/admin/snippets/conteudo/inscritonewsletter/"', html=False)
        self.assertContains(response, 'href="/admin/newsletter/importar-csv/"', html=False)
        self.assertContains(response, 'href="/admin/snippets/conteudo/newsletterevento/"', html=False)
        self.assertContains(response, 'href="/admin/snippets/conteudo/solicitacaoprivacidadenewsletter/"', html=False)

    def test_admin_email_renderiza_hub_de_emails(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_email"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "E-mails")
        self.assertContains(response, "Abrir disparos")
        self.assertContains(response, "Abrir templates")
        self.assertContains(response, "Abrir notificações")
        self.assertContains(response, 'href="/admin/email/disparos/"', html=False)
        self.assertContains(response, 'href="/admin/email/templates/"', html=False)
        self.assertContains(response, 'href="/admin/email/publicacoes/"', html=False)

    def test_admin_indexador_renderiza_hub_do_indexador(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_indexador"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Indexador")
        self.assertContains(response, "Abrir registros")
        self.assertContains(response, "Importar CSV")
        self.assertContains(response, "Baixar modelo CSV")
        self.assertContains(response, 'href="/admin/snippets/conteudo/registroindexador/"', html=False)
        self.assertContains(response, 'href="/admin/indexador/importar-csv/"', html=False)
        self.assertContains(response, 'href="/admin/indexador/modelo-csv/"', html=False)

    def test_admin_estatisticas_renderiza_resumo(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_estatisticas"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estatísticas")
        self.assertContains(response, "indicadores internos simplificados")
        self.assertContains(response, "Leituras acumuladas")
        self.assertContains(response, "Publicações cadastradas")
        self.assertContains(response, "Publicações mais lidas")
        self.assertContains(response, "Mais comentadas")
        self.assertContains(response, "Páginas com mais sessões registradas")
        self.assertContains(response, "Status editorial")
        self.assertContains(response, "Tempo médio no site")
        self.assertNotContains(response, 'name="data_de"', html=False)
        self.assertNotContains(response, 'name="data_ate"', html=False)
        self.assertNotContains(response, 'data-busca-datepicker', html=False)
        self.assertNotContains(response, "busca-datepicker-toggle")

    def test_admin_saude_operacional_renderiza_resumo(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_saude_operacional"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saúde do sistema")
        self.assertContains(response, "Backup")
        self.assertContains(response, "Logs de auditoria")
        self.assertContains(response, "ClamAV")

    def test_estatistica_tempo_site_respeita_consentimento(self):
        payload = {
            "session_id": "sessao-teste",
            "started_at": timezone.now().isoformat(),
            "path": "/publicacoes/teste/?utm=removido",
            "duration_seconds": 42,
        }
        response_sem_consentimento = self.client.post(
            reverse("estatistica_tempo_site"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response_sem_consentimento.status_code, 204)
        self.assertEqual(EstatisticaTempoSite.objects.count(), 0)

        self.client.cookies["ownpaper_cookie_consent"] = "all"
        response = self.client.post(
            reverse("estatistica_tempo_site"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204)
        estatistica = EstatisticaTempoSite.objects.get()
        self.assertEqual(estatistica.path, "/publicacoes/teste/")
        self.assertEqual(estatistica.duration_seconds, 42)

    def _menu_labels(self, html):
        match = re.search(
            r'<script id="wagtail-sidebar-props" type="application/json">(.*?)</script>',
            html,
            re.S,
        )
        self.assertIsNotNone(match)
        payload = json.loads(match.group(1))
        if isinstance(payload, dict) and "props" in payload:
            menu_items = payload["props"]["menuItems"]
        elif isinstance(payload, dict) and "modules" in payload:
            modules = payload.get("modules") or []
            main_menu_module = next(
                (
                    module
                    for module in modules
                    if isinstance(module, dict)
                    and str(module.get("_type", "")).endswith("MainMenuModule")
                ),
                None,
            )
            args = (main_menu_module or {}).get("_args") or []
            menu_items = args[0] if args and isinstance(args[0], list) else []
        elif isinstance(payload, dict) and "_args" in payload:
            args = payload.get("_args") or []
            menu_items = args[0] if args and isinstance(args[0], list) else []
        else:
            menu_items = []

        top_labels = []
        sub_labels = {}
        for item in menu_items:
            args = item.get("_args") or []
            if not args or not isinstance(args[0], dict):
                continue
            label = args[0].get("label")
            if not label:
                continue
            top_labels.append(label)
            if len(args) > 1 and isinstance(args[1], list):
                sub_labels[label] = [
                    sub.get("_args", [{}])[0].get("label")
                    for sub in args[1]
                    if isinstance(sub, dict) and sub.get("_args")
                ]
        return top_labels, sub_labels

    def test_admin_home_ordem_alfabetica_pastas_e_links(self):
        self.client.force_login(self.admin)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        top_labels, sub_labels = self._menu_labels(html)

        self.assertEqual(
            top_labels[:4],
            ["Editorial", "Operação", "Administração", "Ajuda"],
        )
        self.assertEqual(
            sub_labels["Editorial"],
            [
                "Publicações",
                "Páginas",
                "Perguntas do quiz",
                "Mídias",
                "Categorias e Tags",
            ],
        )
        self.assertIn("Contato (Inbox)", sub_labels["Operação"])
        self.assertIn("Links curtos", sub_labels["Operação"])
        self.assertEqual(sub_labels["Administração"][0], "Autores")
        self.assertIn("Estatísticas", sub_labels["Administração"])
        self.assertIn("Configurações do site", sub_labels["Administração"])
        self.assertIn("Redirecionamentos", sub_labels["Administração"])
        self.assertIn("Usuários", sub_labels["Administração"])
        self.assertNotIn("Configurações", sub_labels["Administração"])
        self.assertNotIn("Fluxos de trabalho", sub_labels["Administração"])
        self.assertNotIn("Tarefas de fluxo de trabalho", sub_labels["Administração"])
        self.assertNotIn("Coleções", sub_labels["Administração"])
        self.assertNotIn("Pessoal", top_labels)

    def test_admin_pages_redireciona_para_home_do_site(self):
        self.client.force_login(self.admin)
        response = self.client.get("/admin/pages/")
        self.assertEqual(
            response["Location"],
            reverse(
                "wagtailadmin_explore",
                args=[Site.objects.get(is_default_site=True).root_page_id],
            ),
        )
        self.assertEqual(response.status_code, 302)

    def test_sidebar_pages_aponta_para_home_do_site(self):
        self.client.force_login(self.admin)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        root_id = Site.objects.get(is_default_site=True).root_page_id
        self.assertContains(response, f'"/admin/pages/{root_id}/"')

    def test_explorador_raiz_usa_titulo_paginas_e_publicacoes_abre_painel_customizado(self):
        self.client.force_login(self.admin)
        root_id = Site.objects.get(is_default_site=True).root_page_id
        response = self.client.get(f"/admin/pages/{root_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<title>Explorando: Páginas - Wagtail</title>", html=True)
        self.assertContains(response, "Abrir publicações e nova publicação")
        self.assertContains(response, 'href="/admin/publicacoes/"', html=False)
        self.assertContains(response, "Publicações e Nova Publicação")
        self.assertNotContains(response, ">Nova publicação<", html=False)
        self.assertNotContains(response, "Abrir gerenciamento de publicações")

    def test_explorador_da_pasta_publicacoes_redireciona_para_lista_customizada(self):
        self.client.force_login(self.admin)
        pasta = PublicacoesIndexPage.objects.first()
        response = self.client.get(f"/admin/pages/{pasta.id}/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("admin_publicacoes_lista"))

    def test_settings_remove_sites_da_navegacao(self):
        request = RequestFactory().get("/admin/")
        request.user = self.admin
        items = [
            MenuItem("Configuração do site", "/admin/settings/conteudo/configuracaosite/", name="configuracao-do-site"),
            MenuItem("Sites", "/admin/sites/", name="sites"),
            MenuItem("Coleções", "/admin/collections/", name="collections"),
        ]

        remover_usuarios_legado_do_settings(request, items)

        self.assertEqual([item.name for item in items], [])

    def test_admin_sites_redireciona_para_configuracao_do_site(self):
        self.client.force_login(self.admin)
        response = self.client.get("/admin/sites/", follow=True)
        self.assertTrue(response.redirect_chain)
        self.assertEqual(response.redirect_chain[0][0], reverse("admin_configuracoes_site"))
        self.assertEqual(response.status_code, 200)
        mensagens = [str(message) for message in response.context["messages"]]
        self.assertTrue(any("único site por projeto" in mensagem for mensagem in mensagens))

    def test_admin_home_carrega_tema_global_e_css_do_dashboard(self):
        self.client.force_login(self.admin)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("/static/css/admin-global-theme.", html)
        self.assertIn("/static/css/admin/dashboard.", html)
        self.assertNotIn("/static/css/admin/core.", html)
        self.assertNotIn("/static/css/admin/palette.", html)
        self.assertNotIn("/static/css/admin/sidebar.", html)
        self.assertNotIn("/static/js/admin/core.", html)
        self.assertNotIn("/static/js/admin/theme-fields.", html)
        self.assertNotIn("/static/js/admin/sidebar.", html)
        self.assertNotIn("/static/js/admin/palette.", html)
        self.assertNotIn("/static/js/admin/logo-home.", html)
        self.assertIn("/static/js/admin/fixed-sidebar.", html)
        self.assertIn("/static/js/admin/zoom.", html)
        self.assertNotIn("data-op-admin-zoom-controls", html)

    def test_admin_home_central_renderiza_opcoes_da_home(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_configuracoes_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Páginas do início")
        self.assertContains(response, "Editar início")
        self.assertContains(response, "Publicações")
        self.assertContains(response, "/static/css/admin-custom-pages.", html=False)

    def test_admin_telas_customizadas_restantes_usa_padrao_visual(self):
        self.client.force_login(self.admin)
        navegacao = self.client.get(reverse("admin_navegacao"))
        self.assertEqual(navegacao.status_code, 200)
        self.assertContains(navegacao, "Menu e rodapé")
        self.assertContains(navegacao, "Menu principal")
        self.assertContains(navegacao, "Rodapé")
        self.assertContains(navegacao, "Adicionar link ao rodapé")
        self.assertContains(navegacao, "/admin/configuracoes-site/identidade-seo/", html=False)
        self.assertContains(navegacao, "/admin/configuracoes-site/menu-navegacao/", html=False)
        self.assertContains(navegacao, "/static/css/admin-custom-pages.", html=False)

        indexador = self.client.get(reverse("admin_indexador_importar_csv"))
        self.assertEqual(indexador.status_code, 200)
        self.assertContains(indexador, "Importar CSV do indexador")
        self.assertContains(indexador, "Baixar modelo CSV")

    def test_admin_publicacoes_usa_periodo_no_lugar_de_ano(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_publicacoes_lista"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="data_de"', html=False)
        self.assertContains(response, 'name="data_ate"', html=False)
        self.assertContains(response, 'data-busca-datepicker', html=False)
        self.assertContains(response, "busca-datepicker-toggle")
        self.assertContains(response, "Data de")
        self.assertContains(response, "Data até")
        self.assertNotContains(response, 'name="ano"', html=False)

    def test_admin_publicacoes_normaliza_aliases_de_status(self):
        self.assertEqual(
            _normalizar_status_publicacao_admin("publicada"),
            PublicacaoPage.STATUS_EDITORIAL_PUBLICADO,
        )
        self.assertEqual(
            _normalizar_status_publicacao_admin("aguardando_aprovacao"),
            PublicacaoPage.STATUS_EDITORIAL_EM_REVISAO,
        )
        self.assertEqual(
            _normalizar_status_publicacao_admin("com_alteracoes"),
            "__com_alteracoes__",
        )

    def test_admin_quiz_catalogo_lista_renderiza_filtros_e_acoes(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_quiz_catalogo_lista"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Perguntas do quiz")
        self.assertContains(response, 'name="uso"', html=False)
        self.assertContains(response, 'name="aprovacao"', html=False)
        self.assertContains(response, 'name="ordenar"', html=False)
        self.assertContains(response, "<th class=\"admin-quiz-catalogo-col-status\">Status</th>", html=True)
        self.assertContains(response, 'href="/admin/snippets/conteudo/perguntaquizcatalogo/add/"', html=False)

    def test_chooser_de_perguntas_do_quiz_renderiza_busca_e_filtros(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("wagtailsnippetchoosers_conteudo_perguntaquizcatalogo:choose")
        )
        self.assertEqual(response.status_code, 200)
        chooser_html = response.json()["html"]
        self.assertIn('name="q"', chooser_html)
        self.assertIn("admin-quiz-catalogo-chooser__filters", chooser_html)
        self.assertIn('name="categoria"', chooser_html)
        self.assertIn('name="tag"', chooser_html)
        self.assertIn('name="status"', chooser_html)
        self.assertIn('name="uso"', chooser_html)
        self.assertNotIn('name="pergunta_id"', chooser_html)
        self.assertNotIn('name="origem"', chooser_html)

    def test_blocos_multifield_relevantes_estao_colapsados_por_padrao(self):
        configuracao_headings = {
            panel.heading: getattr(panel, "classname", "")
            for panel in ConfiguracaoSite.panels
            if getattr(panel, "heading", "")
        }
        self.assertEqual(configuracao_headings["Menu customizado"], "collapsed")
        self.assertEqual(configuracao_headings["Tema e paleta"], "collapsed")
        self.assertEqual(configuracao_headings["Apoios e doações"], "collapsed")
        self.assertEqual(configuracao_headings["Backups"], "collapsed")

        convite_headings = {
            panel.heading: getattr(panel, "classname", "")
            for panel in ConviteUsuario.panels
            if getattr(panel, "heading", "")
        }
        self.assertEqual(convite_headings["Papéis do convite"], "collapsed")

    def test_admin_configuracoes_site_agora_e_hub_por_secoes(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_configuracoes_site"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Configurações do site")
        self.assertContains(response, "Identidade e SEO")
        self.assertContains(response, "Páginas institucionais")
        self.assertContains(response, "Menu e navegação")
        self.assertContains(response, "op-admin-settings-card")
        self.assertContains(response, "op-admin-panel__actions")
        self.assertContains(response, "Ajustes estruturais do projeto")
        self.assertNotContains(response, "Nome público do projeto")

    def test_admin_configuracoes_site_secao_renderiza_formulario(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_configuracoes_site_secao", args=["tema-aparencia"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tema e aparência")
        self.assertContains(response, "O que esta seção controla")
        self.assertContains(response, "Define o idioma base")
        self.assertContains(response, "op-admin-form-grid--settings")
        self.assertContains(response, "op-admin-settings-tabs")
        self.assertContains(response, 'name="paleta_cor_1"', html=False)
        self.assertContains(response, 'name="paleta_cor_2"', html=False)
        self.assertContains(response, "/static/css/admin-custom-pages.", html=False)
        self.assertContains(response, "/static/css/admin/palette.", html=False)
        self.assertContains(response, "/static/js/admin/core.", html=False)
        self.assertContains(response, "/static/js/admin/theme-fields.", html=False)
        self.assertContains(response, "/static/js/admin/palette.", html=False)
        self.assertContains(response, "/static/js/admin/logo-home.", html=False)

    def test_admin_configuracoes_integracoes_usa_layout_proprio(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_configuracoes_site_secao", args=["integracoes-rastreamento"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Integrações e rastreamento")
        self.assertContains(response, "Verificações de domínio")
        self.assertContains(response, "Google e Meta")
        self.assertContains(response, "Analytics externos")
        self.assertContains(response, "Estatísticas internas")
        self.assertContains(response, "Links curtos")
        self.assertContains(response, "op-admin-config-integrations")
        self.assertContains(response, 'name="google_search_console_verification"', html=False)
        self.assertContains(response, 'name="plausible_script_url"', html=False)
        self.assertContains(response, 'name="estatisticas_internas_ativas"', html=False)

    def test_admin_configuracoes_comunicacao_usa_layout_proprio(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_configuracoes_site_secao", args=["comunicacao-comentarios"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Comunicação e comentários")
        self.assertContains(response, "Comentários públicos")
        self.assertContains(response, "Notificações de publicações")
        self.assertContains(response, "Submissões públicas")
        self.assertContains(response, "op-admin-config-communication")
        self.assertContains(response, 'name="comentarios_ativos"', html=False)
        self.assertContains(response, 'name="notificacao_publicacoes_modo"', html=False)
        self.assertContains(response, 'name="submissoes_publicas_ativas"', html=False)

    def test_admin_configuracoes_paginas_institucionais_usa_layout_proprio(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_configuracoes_site_secao", args=["paginas-institucionais"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Páginas institucionais")
        self.assertContains(response, "Páginas base")
        self.assertContains(response, "Ferramentas públicas")
        self.assertContains(response, "op-admin-config-institutional")
        self.assertContains(response, 'name="pagina_sobre"', html=False)
        self.assertContains(response, 'name="pagina_indexador"', html=False)
        self.assertContains(response, 'name="rotulo_quiz_estudo"', html=False)

    def test_admin_configuracoes_apoios_usa_layout_proprio(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_configuracoes_site_secao", args=["apoios-doacoes"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Apoios e doações")
        self.assertContains(response, "Exibição")
        self.assertContains(response, "Pix")
        self.assertContains(response, "Plataformas")
        self.assertContains(response, "Criptoativos")
        self.assertContains(response, "op-admin-config-donations")
        self.assertContains(response, 'name="doacoes_exibir_no_cabecalho"', html=False)
        self.assertContains(response, 'name="doacoes_descricao"', html=False)
        self.assertContains(response, 'data-draftail-input', html=False)
        self.assertContains(response, "wagtailadmin/js/draftail.", html=False)
        self.assertContains(response, 'name="doacoes_pix_ativo"', html=False)
        self.assertContains(response, 'name="doacoes_paypal_hosted_button_id"', html=False)
        self.assertContains(response, 'name="doacoes_ethereum_endereco"', html=False)

    def test_admin_configuracoes_operacao_usa_layout_proprio(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_configuracoes_site_secao", args=["operacao-site"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operação do site")
        self.assertContains(response, "Manutenção pública")
        self.assertContains(response, "Proteção editorial")
        self.assertContains(response, "Relatório de backup")
        self.assertContains(response, "op-admin-config-operation")
        self.assertContains(response, 'name="modo_manutencao_ativo"', html=False)
        self.assertContains(response, 'name="travar_publicacao_por_orcid"', html=False)
        self.assertContains(response, 'name="backup_email_destino"', html=False)

    def test_pagina_apoio_renderiza_metodos_habilitados(self):
        site = Site.objects.get(is_default_site=True)
        config = ConfiguracaoSite.for_site(site)
        config.doacoes_ativas = True
        config.doacoes_exibir_no_cabecalho = True
        config.doacoes_titulo = "Apoie o teste"
        config.doacoes_pix_ativo = True
        config.doacoes_pix_chave = "pix@example.com"
        config.doacoes_buymeacoffee_ativo = True
        config.doacoes_buymeacoffee_usuario = "ownpaper"
        config.doacoes_paypal_ativo = True
        config.doacoes_paypal_hosted_button_id = "ABC123"
        config.doacoes_github_sponsors_ativo = True
        config.doacoes_github_sponsors_usuario = "ownpaper"
        config.doacoes_bitcoin_ativo = True
        config.doacoes_bitcoin_endereco = "bc1qteste"
        config.doacoes_ethereum_ativo = True
        config.doacoes_ethereum_endereco = "0x1234567890abcdef"
        config.save()

        response = self.client.get(reverse("pagina_apoio"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Apoie o teste")
        self.assertContains(response, "Todo apoio ajuda")
        self.assertContains(response, "pix@example.com")
        self.assertContains(response, "https://www.buymeacoffee.com/ownpaper", html=False)
        self.assertContains(response, "https://www.paypal.com/donate?hosted_button_id=ABC123", html=False)
        self.assertContains(response, "https://github.com/sponsors/ownpaper", html=False)
        self.assertContains(response, "bc1qteste")
        self.assertContains(response, "0x1234567890abcdef")

    def test_admin_configuracoes_identidade_seo_usa_layout_com_previews(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_configuracoes_site_secao", args=["identidade-seo"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identidade e SEO")
        self.assertContains(response, "Identidade pública")
        self.assertContains(response, "Imagem de compartilhamento")
        self.assertContains(response, "Favicon")
        self.assertContains(response, "Rodapé institucional")
        self.assertContains(response, "E-mail institucional público")
        self.assertContains(response, "O destino das mensagens do formulário de contato é configurado na página Contato.")
        self.assertContains(response, "op-admin-settings-media-card")
        self.assertContains(response, "op-admin-settings-image-preview")
        self.assertContains(response, "data-ownpaper-image-preview-card")
        self.assertContains(response, "data-ownpaper-image-preview-target")
        self.assertContains(response, "data-ownpaper-image-preview-field")
        self.assertContains(response, "data-preview-url-template")
        self.assertContains(response, "/static/js/admin/identity-seo-preview.", html=False)
        self.assertContains(response, "Nenhuma imagem selecionada.")
        self.assertContains(response, "Nenhum favicon selecionado.")
        self.assertContains(response, 'name="nome_site"', html=False)
        self.assertContains(response, 'name="imagem_compartilhamento_padrao"', html=False)
        self.assertContains(response, 'name="favicon"', html=False)

    def test_admin_configuracoes_imagem_preview_retorna_rendition_json(self):
        ImageModel = get_image_model()
        png_1x1 = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        )
        imagem = ImageModel.objects.create(
            title="Preview teste",
            file=SimpleUploadedFile("preview.png", png_1x1, content_type="image/png"),
        )

        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("admin_configuracoes_site_imagem_preview", args=[imagem.id]),
            {"spec": "fill-96x96"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], imagem.id)
        self.assertEqual(payload["title"], "Preview teste")
        self.assertIn("/images/", payload["url"])

    def test_admin_configuracoes_menu_navegacao_usa_layout_com_previews(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_configuracoes_site_secao", args=["menu-navegacao"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Menu e navegação")
        self.assertContains(response, "Comportamento do menu")
        self.assertContains(response, "Item Início")
        self.assertContains(response, "Logo padrão do Início")
        self.assertContains(response, "Logos por tema")
        self.assertContains(response, "Logos mobile")
        self.assertContains(response, "Dimensões e ajuste")
        self.assertContains(response, "op-admin-config-menu")
        self.assertContains(response, "op-admin-menu-top-grid")
        self.assertContains(response, "op-admin-menu-checkbox-line")
        self.assertContains(response, "op-admin-menu-checkbox")
        self.assertContains(response, "op-admin-menu-toggle-input")
        self.assertContains(response, "op-admin-form-grid--menu-logos")
        self.assertContains(response, "data-ownpaper-image-preview-card")
        self.assertContains(response, "data-preview-spec=\"max-320x140\"")
        self.assertContains(response, "/static/js/admin/identity-seo-preview.", html=False)
        self.assertContains(response, 'name="usar_menu_customizado"', html=False)
        self.assertContains(response, 'name="menu_home_imagem_claro"', html=False)
        self.assertContains(response, 'name="menu_home_logo_proporcao"', html=False)

    def test_editor_nativo_do_wagtail_nao_recebe_bundle_customizado(self):
        self.client.force_login(self.admin)
        page_id = Site.objects.get(is_default_site=True).root_page_id
        response = self.client.get(reverse("wagtailadmin_pages:edit", args=[page_id]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("/static/css/admin-global-theme.", html)
        self.assertNotIn("/static/css/admin-custom-pages.", html)
        self.assertNotIn("/static/css/admin/core.", html)
        self.assertNotIn("/static/css/admin/palette.", html)
        self.assertNotIn("/static/css/admin/sidebar.", html)
        self.assertNotIn("/static/js/admin/core.", html)
        self.assertNotIn("/static/js/admin/theme-fields.", html)
        self.assertNotIn("/static/js/admin/sidebar.", html)
        self.assertNotIn("/static/js/admin/palette.", html)
        self.assertNotIn("/static/js/admin/logo-home.", html)
        self.assertNotIn("/static/js/admin/zoom.", html)

    def test_rota_antiga_do_wagtailsettings_redireciona_para_hub(self):
        self.client.force_login(self.admin)
        site = Site.objects.get(is_default_site=True)
        response = self.client.get(f"/admin/settings/conteudo/configuracaosite/{site.id}/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("admin_configuracoes_site"))


@PUBLIC_TEST_SETTINGS
@override_settings(MIDDLEWARE=NO_PANEL_2FA_MIDDLEWARE)
class AdminOperationalAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_bootstrap()
        User = get_user_model()
        cls.operador = User.objects.create_user(
            username="operador_contato",
            email="operador_contato@example.com",
            password="Senha@12345",
            is_active=True,
            is_staff=True,
            is_superuser=False,
        )
        cls.admin = User.objects.create_user(
            username="admin_operacional",
            email="admin_operacional@example.com",
            password="Senha@12345",
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        cls.staff_comum = User.objects.create_user(
            username="staff_comum",
            email="staff_comum@example.com",
            password="Senha@12345",
            is_active=True,
            is_staff=True,
            is_superuser=False,
        )
        Group.objects.get(name=CONTACT_OPERATORS_GROUP_NAME).user_set.add(cls.operador)
        aceitar_termos_painel_teste(cls.operador, cls.admin, cls.staff_comum)

    def _menu_labels(self, html):
        match = re.search(
            r'<script id="wagtail-sidebar-props" type="application/json">(.*?)</script>',
            html,
            re.S,
        )
        self.assertIsNotNone(match)
        payload = json.loads(match.group(1))
        if isinstance(payload, dict) and "props" in payload:
            menu_items = payload["props"]["menuItems"]
        elif isinstance(payload, dict) and "modules" in payload:
            modules = payload.get("modules") or []
            main_menu_module = next(
                (
                    module
                    for module in modules
                    if isinstance(module, dict)
                    and str(module.get("_type", "")).endswith("MainMenuModule")
                ),
                None,
            )
            args = (main_menu_module or {}).get("_args") or []
            menu_items = args[0] if args and isinstance(args[0], list) else []
        elif isinstance(payload, dict) and "_args" in payload:
            args = payload.get("_args") or []
            menu_items = args[0] if args and isinstance(args[0], list) else []
        else:
            menu_items = []

        labels = []
        for item in menu_items:
            args = item.get("_args") or []
            if not args or not isinstance(args[0], dict):
                continue
            label = args[0].get("label")
            if label:
                labels.append(label)
        return labels

    def test_operador_contato_acessa_inbox_e_ve_menu_restrito(self):
        self.client.force_login(self.operador)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        labels = self._menu_labels(response.content.decode("utf-8"))
        self.assertIn("Operação", labels)
        self.assertNotIn("Pessoal", labels)
        self.assertNotIn("Editorial", labels)
        self.assertContains(response, "Relacionamento e campanhas")
        self.assertContains(response, "Contato")
        self.assertNotContains(response, "Configuração e Fluxo editorial")

        inbox = self.client.get(reverse("admin_contato_inbox"))
        self.assertEqual(inbox.status_code, 200)
        self.assertContains(inbox, "Data de")
        self.assertContains(inbox, "Data até")
        self.assertContains(inbox, 'data-busca-datepicker', html=False)
        self.assertContains(inbox, "busca-datepicker-toggle")

    def test_staff_comum_nao_acessa_inbox(self):
        self.client.force_login(self.staff_comum)
        response = self.client.get(reverse("admin_contato_inbox"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/", response["Location"])

    def test_minha_conta_redireciona_para_conta_nativa(self):
        self.client.force_login(self.operador)
        response = self.client.get(reverse("admin_minha_conta"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("wagtailadmin_account"))

    def test_conta_nativa_exibe_backup_codes_e_zoom(self):
        self.client.force_login(self.operador)
        response = self.client.get(reverse("wagtailadmin_account"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Backup codes do 2FA")
        self.assertContains(response, "Zoom do painel")
        self.assertContains(response, 'data-op-admin-zoom-controls', html=False)
        html = response.content.decode("utf-8")
        self.assertNotIn("/static/css/admin/core.", html)
        self.assertNotIn("/static/js/admin/core.", html)

    def test_responsaveis_de_contato_incluem_admin_e_operador(self):
        usernames = set(eligible_contact_assignees().values_list("username", flat=True))
        self.assertIn("operador_contato", usernames)
        self.assertIn("admin_operacional", usernames)
        self.assertNotIn("staff_comum", usernames)

    def test_assinatura_operacional_e_anexada_no_envio_com_nome_e_site(self):
        self.admin.first_name = "Admin Operacional"
        self.admin.save(update_fields=["first_name"])
        config = ConfiguracaoSite.for_site(Site.objects.get(is_default_site=True))
        config.nome_site = "OwnPaper Operacional"
        config.save(update_fields=["nome_site"])
        request = RequestFactory().get("/admin/contato/1/")
        request.user = self.admin

        html_inicial = _corpo_inicial_email_com_assinatura(request, self.admin)
        html = _anexar_assinatura_email_html(request, self.admin, "<p>Resposta</p>")

        self.assertEqual(html_inicial, "")
        self.assertIn("Resposta", html)
        self.assertIn("Admin Operacional", html)
        self.assertIn("OwnPaper Operacional", html)

    def test_edicao_de_usuario_nao_exibe_campo_legacy_de_assinatura(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_usuario_editar", args=[self.operador.id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="assinatura_email"', html=False)
        self.assertContains(response, "A assinatura operacional é gerada automaticamente")


@PUBLIC_TEST_SETTINGS
class PublicacaoLeituraZoomTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_bootstrap()
        pasta_publicacoes = PublicacoesIndexPage.objects.first()
        cls.publicacao = PublicacaoPage(
            title="Publicacao para teste de zoom",
            slug="publicacao-teste-zoom",
            resumo="<p>Resumo de teste para validar zoom.</p>",
            corpo="<p>Corpo de teste para validar zoom.</p>",
        )
        pasta_publicacoes.add_child(instance=cls.publicacao)
        cls.publicacao.save_revision().publish()

    def test_publicacao_renderiza_controles_de_leitura(self):
        response = self.client.get(self.publicacao.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="publicacao-barra-acoes"')
        self.assertContains(response, 'data-fonte-acao="diminuir"')
        self.assertContains(response, 'data-fonte-acao="padrao"')
        self.assertContains(response, 'data-fonte-acao="aumentar"')


@PUBLIC_TEST_SETTINGS
class PublicFormsSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_bootstrap()
        cls.contato_page = ContatoPage.objects.first()

    def test_contato_rejeita_mensagem_maior_que_limite(self):
        payload = {
            "nome": "Nome de teste",
            "email": "contato@example.com",
            "mensagem": "x" * (settings.CONTACT_MAX_MENSAGEM_LENGTH + 1),
            "aceitou_privacidade": "on",
            "website": "",
        }

        response = self.client.post(
            f"/contato/{self.contato_page.slug}/enviar/",
            data=payload,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(MensagemContato.objects.count(), 0)

    def test_newsletter_rejeita_email_invalido(self):
        response = self.client.post(
            "/newsletter/newsletter/inscrever/",
            data={
                "email": "email-invalido",
                "consentimento": "on",
                "website": "",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(InscritoNewsletter.objects.count(), 0)


@PUBLIC_TEST_SETTINGS
class RodapeConfiguravelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_bootstrap()
        cls.site = Site.objects.get(is_default_site=True)
        cls.config = ConfiguracaoSite.for_site(cls.site)

    def test_rodape_usa_links_configuraveis_com_ordem(self):
        RodapeLink.objects.create(
            configuracao_site=self.config,
            sort_order=2,
            titulo="Link Externo",
            tipo=RodapeLink.TIPO_URL,
            url_externa="https://example.org",
        )
        RodapeLink.objects.create(
            configuracao_site=self.config,
            sort_order=1,
            titulo="Contato Atalho",
            tipo=RodapeLink.TIPO_ATALHO,
            atalho="contato",
        )

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Contato Atalho", html)
        self.assertIn("Link Externo", html)
        self.assertLess(html.find("Contato Atalho"), html.find("Link Externo"))

    def test_rodape_mantem_fallback_legado_sem_links_configurados(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contato")
        self.assertContains(response, "Newsletter")


@PUBLIC_TEST_SETTINGS
class MenuTraducaoDinamicaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_bootstrap()
        cls.site = Site.objects.get(is_default_site=True)
        cls.config = ConfiguracaoSite.for_site(cls.site)
        cls.config.usar_menu_customizado = True
        cls.config.save(update_fields=["usar_menu_customizado"])

        MenuPrincipalGrupo.objects.create(
            configuracao_site=cls.config,
            sort_order=1,
            titulo="Busca avançada",
            tipo=MenuPrincipalGrupo.TIPO_URL,
            url_externa="https://example.com/busca-avancada",
        )
        MenuPrincipalGrupo.objects.create(
            configuracao_site=cls.config,
            sort_order=2,
            titulo="Busca de artigos científicos",
            tipo=MenuPrincipalGrupo.TIPO_URL,
            url_externa="https://example.com/indexador",
        )
        MenuPrincipalGrupo.objects.create(
            configuracao_site=cls.config,
            sort_order=3,
            titulo="Sobre",
            tipo=MenuPrincipalGrupo.TIPO_URL,
            url_externa="https://example.com/sobre",
        )
        MenuPrincipalGrupo.objects.create(
            configuracao_site=cls.config,
            sort_order=4,
            titulo="Contato",
            tipo=MenuPrincipalGrupo.TIPO_URL,
            url_externa="https://example.com/contato",
        )
        RodapeLink.objects.create(
            configuracao_site=cls.config,
            sort_order=1,
            titulo="Indexador",
            tipo=RodapeLink.TIPO_URL,
            url_externa="https://example.com/indexador",
        )

    def test_home_ignora_cookie_legado_de_idioma_ingles(self):
        self.client.cookies["ownpaper_site_lang"] = "en"
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Busca avançada", html)
        self.assertIn("Busca de artigos científicos", html)
        self.assertIn(">Sobre<", html)
        self.assertIn(">Contato<", html)
        self.assertIn(">Indexador<", html)
        self.assertNotIn("Advanced search", html)
        self.assertNotIn(">Contact<", html)

    def test_home_ignora_cookie_legado_de_idioma_espanhol(self):
        self.client.cookies["ownpaper_site_lang"] = "es"
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Busca avançada", html)
        self.assertIn("Busca de artigos científicos", html)
        self.assertIn(">Sobre<", html)
        self.assertIn(">Contato<", html)
        self.assertIn(">Indexador<", html)
        self.assertNotIn("Búsqueda avanzada", html)
        self.assertNotIn(">Contacto<", html)


@PUBLIC_TEST_SETTINGS
class EmailDisparosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_bootstrap()
        User = get_user_model()
        cls.admin = User.objects.create_user(
            username="admin_test",
            email="admin@example.com",
            password="Senha@12345",
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        cls.autor = User.objects.create_user(
            username="autor_test",
            email="autor@example.com",
            password="Senha@12345",
            is_active=True,
            is_staff=True,
            is_superuser=False,
        )
        cls.autor.groups.add(Group.objects.get(name="Autores / Escritores"))
        cls.comum = User.objects.create_user(
            username="comum_test",
            email="comum@example.com",
            password="Senha@12345",
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        InscritoNewsletter.objects.create(
            email="newsletter@example.com",
            ativo=True,
            consentimento=True,
            origem="teste",
        )

    def test_segmentacao_destinatarios(self):
        todos = destinatarios_por_segmento(DisparoEmail.SEG_TODOS_USUARIOS)
        self.assertIn("admin@example.com", todos)
        self.assertIn("autor@example.com", todos)
        self.assertIn("comum@example.com", todos)

        admins = destinatarios_por_segmento(DisparoEmail.SEG_APENAS_ADMINS)
        self.assertIn("admin@example.com", admins)
        self.assertNotIn("autor@example.com", admins)

        autores = destinatarios_por_segmento(DisparoEmail.SEG_APENAS_AUTORES)
        self.assertIn("autor@example.com", autores)
        self.assertNotIn("admin@example.com", autores)

        newsletter = destinatarios_por_segmento(DisparoEmail.SEG_NEWSLETTER)
        self.assertIn("newsletter@example.com", newsletter)

    def test_criacao_template_email_campanha(self):
        TemplateEmailCampanha.objects.create(
            nome="Modelo semanal",
            assunto_padrao="Resumo da semana",
            corpo_html_padrao="<p>Resumo</p>",
            ativo=True,
            criado_por=self.admin,
        )
        self.assertTrue(
            TemplateEmailCampanha.objects.filter(
                nome="Modelo semanal",
                assunto_padrao="Resumo da semana",
                ativo=True,
            ).exists()
        )

    def test_telas_de_email_usam_editor_visual_no_corpo(self):
        request_disparo = RequestFactory().get(reverse("admin_email_disparos"))
        request_disparo.user = self.admin
        response_disparo = email_disparos_admin_view(request_disparo)
        html_disparo = response_disparo.content.decode("utf-8")

        self.assertEqual(response_disparo.status_code, 200)
        self.assertIn("Corpo da mensagem", html_disparo)
        self.assertIn("data-email-richtext", html_disparo)
        self.assertIn("email-richtext", html_disparo)
        self.assertNotIn("Corpo (HTML simples)", html_disparo)

        request_template = RequestFactory().get(reverse("admin_email_templates"))
        request_template.user = self.admin
        response_template = email_templates_admin_view(request_template)
        html_template = response_template.content.decode("utf-8")

        self.assertEqual(response_template.status_code, 200)
        self.assertIn("Corpo padrão", html_template)
        self.assertIn("data-email-richtext", html_template)
        self.assertIn("email-richtext", html_template)
        self.assertNotIn("Corpo HTML padrão", html_template)

    def test_notificacoes_publicacoes_explicam_modos_de_envio(self):
        request = RequestFactory().get(reverse("admin_email_publicacoes"))
        request.user = self.admin
        response = email_publicacoes_admin_view(request)
        html = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Como funciona", html)
        self.assertIn("Desativada:", html)
        self.assertIn("Imediata:", html)
        self.assertIn("Consolidada por período:", html)
        self.assertIn("Enviar consolidado agora:", html)
        self.assertIn("Frequência do consolidado", html)
        self.assertIn('name="periodo_dias"', html)
        self.assertIn(">7 dias<", html)
        self.assertIn(">15 dias<", html)
        self.assertIn(">30 dias<", html)
        self.assertIn(">90 dias<", html)
        self.assertNotIn("Período em horas", html)

    def test_notificacoes_publicacoes_salvam_frequencia_em_dias_como_horas(self):
        request = RequestFactory().post(
            reverse("admin_email_publicacoes"),
            data={
                "acao": "salvar_config",
                "modo": ConfiguracaoSite.NOTIFICACAO_PUBLICACOES_PERIODICA,
                "periodo_dias": "15",
            },
        )
        request.user = self.admin
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        response = email_publicacoes_admin_view(request)

        self.assertEqual(response.status_code, 302)
        config = ConfiguracaoSite.for_site(Site.objects.get(is_default_site=True))
        self.assertEqual(config.notificacao_publicacoes_modo, ConfiguracaoSite.NOTIFICACAO_PUBLICACOES_PERIODICA)
        self.assertEqual(config.notificacao_publicacoes_periodo_horas, 15 * 24)

    def test_sanitize_email_html_remove_scripts_eventos_e_links_perigosos(self):
        html = (
            '<p onclick="alert(1)">Oi</p>'
            '<script>alert(2)</script>'
            '<a href="javascript:alert(3)" title="x">link ruim</a>'
            '<a href="https://example.org" onclick="alert(4)">link bom</a>'
        )
        sanitizado = sanitize_email_html(html)
        self.assertIn("<p>Oi</p>", sanitizado)
        self.assertNotIn("onclick", sanitizado)
        self.assertNotIn("<script", sanitizado)
        self.assertNotIn("javascript:", sanitizado)
        self.assertIn('href="https://example.org"', sanitizado)
        self.assertIn("rel=", sanitizado)

    def test_preview_admin_de_email_renderiza_html_sanitizado(self):
        request = RequestFactory().post(
            reverse("admin_email_disparos"),
            data={
                "acao": "preview",
                "segmento": DisparoEmail.SEG_NEWSLETTER,
                "assunto": "Preview seguro",
                "corpo_html": (
                    '<p onclick="alert(1)">Olá</p>'
                    '<script>alert(2)</script>'
                    '<a href="javascript:alert(3)">ruim</a>'
                    '<a href="https://example.org">bom</a>'
                ),
            },
        )
        request.user = self.admin
        response = email_disparos_admin_view(request)
        html = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            '<div class="op-admin-preview-box">\n                <p>Olá</p><a>ruim</a><a href="https://example.org" rel="noopener noreferrer nofollow">bom</a>',
            html,
        )
        self.assertNotIn("javascript:", html)

    def test_export_csv_destinos_disparo(self):
        disparo = DisparoEmail.objects.create(
            tipo=DisparoEmail.TIPO_MANUAL,
            segmento=DisparoEmail.SEG_NEWSLETTER,
            assunto="Teste CSV",
            corpo_html="<p>Teste</p>",
            criado_por=self.admin,
            status=DisparoEmail.STATUS_CONCLUIDO,
        )
        DisparoEmailDestino.objects.create(
            disparo=disparo,
            email="ok@example.com",
            status=DisparoEmailDestino.STATUS_ENVIADO,
        )
        DisparoEmailDestino.objects.create(
            disparo=disparo,
            email="erro@example.com",
            status=DisparoEmailDestino.STATUS_FALHOU,
            erro="Falhou",
        )
        request = RequestFactory().get(
            reverse("admin_email_disparo_detalhe", args=[disparo.id]),
            data={"status": "enviado", "export": "csv"},
        )
        request.user = self.admin
        response = email_disparo_detalhe_admin_view(request, disparo.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        csv_text = response.content.decode("utf-8")
        self.assertIn("ok@example.com", csv_text)
        self.assertNotIn("erro@example.com", csv_text)

    @patch("django.core.mail.EmailMessage.send", return_value=1)
    def test_executar_disparo_atualiza_metricas(self, mocked_send):
        disparo = DisparoEmail.objects.create(
            tipo=DisparoEmail.TIPO_MANUAL,
            segmento=DisparoEmail.SEG_APENAS_ADMINS,
            assunto="Teste de envio",
            corpo_html="<p>Olá</p>",
            criado_por=self.admin,
        )
        executar_disparo(disparo)
        disparo.refresh_from_db()

        self.assertEqual(disparo.status, DisparoEmail.STATUS_CONCLUIDO)
        self.assertGreaterEqual(disparo.total_destinatarios, 1)
        self.assertEqual(disparo.total_falhas, 0)
        self.assertGreaterEqual(disparo.total_enviados, 1)
        self.assertTrue(mocked_send.called)
        self.assertGreaterEqual(DisparoEmailDestino.objects.filter(disparo=disparo).count(), 1)

    @patch("conteudo.email_ops.EmailMessage")
    def test_executar_disparo_sanitiza_corpo_antes_do_envio(self, mocked_email_message):
        mocked_email_message.return_value.send.return_value = 1
        disparo = DisparoEmail.objects.create(
            tipo=DisparoEmail.TIPO_MANUAL,
            segmento=DisparoEmail.SEG_APENAS_ADMINS,
            assunto="Teste de envio",
            corpo_html=(
                '<p>Olá</p><script>alert(1)</script>'
                '<a href="javascript:alert(2)">ruim</a>'
                '<a href="https://example.org">bom</a>'
            ),
            criado_por=self.admin,
        )
        executar_disparo(disparo)
        kwargs = mocked_email_message.call_args.kwargs
        body = kwargs["body"]
        self.assertIn("<p>Olá</p>", body)
        self.assertNotIn("<script", body)
        self.assertNotIn("javascript:", body)
        self.assertIn("/email/track/click/", body)


@PUBLIC_TEST_SETTINGS
class BackupOpsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_bootstrap()
        cls.site = Site.objects.get(is_default_site=True)
        cls.config = ConfiguracaoSite.for_site(cls.site)
        cls.config.backup_enviar_relatorio = False
        cls.config.save(update_fields=["backup_enviar_relatorio"])

    @patch("conteudo.backup_ops._dump_banco_pg_dump")
    @patch("conteudo.backup_ops.call_command")
    def test_backup_site_gera_arquivo_zip(self, mocked_dumpdata, mocked_pg_dump):
        mocked_pg_dump.return_value = (None, "pg_dump indisponivel")
        mocked_dumpdata.side_effect = lambda *a, **k: k["stdout"].write("[]")
        media_root = Path(settings.MEDIA_ROOT)
        media_root.mkdir(parents=True, exist_ok=True)
        (media_root / "arquivo_teste.txt").write_text("teste", encoding="utf-8")

        execucao = executar_backup_site(
            site=self.site,
            solicitado_por=None,
            tipo=BackupExecucao.TIPO_MANUAL,
            incluir_midia=True,
        )
        execucao.refresh_from_db()

        self.assertEqual(execucao.status, BackupExecucao.STATUS_CONCLUIDO)
        self.assertTrue(execucao.arquivo_caminho.endswith(".zip"))
        self.assertTrue(Path(execucao.arquivo_caminho).exists())
        self.assertGreater(execucao.arquivo_tamanho_bytes, 0)
        self.assertTrue(execucao.detalhes["restore_dry_run"]["ok"])
        validacao = simular_restore_backup(execucao.arquivo_caminho)
        self.assertTrue(validacao.get("ok"))

    @patch("conteudo.backup_ops.call_command")
    def test_backup_logs_gera_json_parcial(self, mocked_dumpdata):
        mocked_dumpdata.side_effect = lambda *a, **k: k["stdout"].write("[]")

        execucao = executar_backup_site(
            site=self.site,
            solicitado_por=None,
            tipo=BackupExecucao.TIPO_MANUAL,
            incluir_midia=False,
            escopo="logs",
        )
        execucao.refresh_from_db()

        self.assertEqual(execucao.status, BackupExecucao.STATUS_CONCLUIDO)
        self.assertEqual(execucao.detalhes["escopo"], "logs")
        self.assertFalse(execucao.inclui_midia)
        self.assertTrue(simular_restore_backup(execucao.arquivo_caminho).get("ok"))

    def test_backup_midias_valida_sem_dump_de_banco(self):
        media_root = Path(settings.MEDIA_ROOT)
        media_root.mkdir(parents=True, exist_ok=True)
        (media_root / "arquivo_midia_teste.txt").write_text("teste", encoding="utf-8")

        execucao = executar_backup_site(
            site=self.site,
            solicitado_por=None,
            tipo=BackupExecucao.TIPO_MANUAL,
            incluir_midia=True,
            escopo="midias",
        )
        execucao.refresh_from_db()

        self.assertEqual(execucao.status, BackupExecucao.STATUS_CONCLUIDO)
        self.assertEqual(execucao.detalhes["escopo"], "midias")
        self.assertTrue(execucao.inclui_midia)
        self.assertTrue(simular_restore_backup(execucao.arquivo_caminho).get("ok"))


@PUBLIC_TEST_SETTINGS
class EmailTrackingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_bootstrap()
        cls.disparo = DisparoEmail.objects.create(
            tipo=DisparoEmail.TIPO_MANUAL,
            segmento=DisparoEmail.SEG_NEWSLETTER,
            assunto="Rastreio",
            corpo_html='<p><a href="https://example.org">Link</a></p>',
            status=DisparoEmail.STATUS_CONCLUIDO,
        )
        cls.destino = DisparoEmailDestino.objects.create(
            disparo=cls.disparo,
            email="destino@example.com",
            status=DisparoEmailDestino.STATUS_ENVIADO,
        )

    def test_email_open_track_incrementa_aberturas(self):
        url = reverse("email_open_track", args=[self.destino.tracking_token])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("image/gif", response["Content-Type"])
        self.client.get(url)
        self.destino.refresh_from_db()
        self.assertEqual(self.destino.total_aberturas, 2)
        self.assertIsNotNone(self.destino.aberto_em)

    def test_email_click_track_redireciona_e_incrementa_cliques(self):
        url_destino = "https://example.org/materia"
        payload = signing.dumps(
            {"t": str(self.destino.tracking_token), "u": url_destino},
            salt="ownpaper_email_click",
        )
        url = (
            reverse("email_click_track", args=[self.destino.tracking_token])
            + f"?d={urllib.parse.quote(payload, safe='')}"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], url_destino)
        self.destino.refresh_from_db()
        self.assertEqual(self.destino.total_cliques, 1)
        self.assertIsNotNone(self.destino.ultimo_clique_em)
        self.assertEqual(
            DisparoEmailClique.objects.filter(
                disparo=self.disparo,
                destino=self.destino,
                url=url_destino,
            ).count(),
            1,
        )

    def test_top_links_respeita_periodo_selecionado(self):
        clique_recente = DisparoEmailClique.objects.create(
            disparo=self.disparo,
            destino=self.destino,
            url="https://example.org/recente",
        )
        clique_antigo = DisparoEmailClique.objects.create(
            disparo=self.disparo,
            destino=self.destino,
            url="https://example.org/antigo",
        )
        DisparoEmailClique.objects.filter(id=clique_antigo.id).update(
            criado_em=timezone.now() - timedelta(days=120)
        )

        User = get_user_model()
        admin = User.objects.create_user(
            username="admin_periodo_links",
            email="admin_periodo_links@example.com",
            password="Senha@12345",
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        request = RequestFactory().get(
            reverse("admin_email_disparo_detalhe", args=[self.disparo.id]),
            data={"periodo_links": "30"},
        )
        request.user = admin
        response = email_disparo_detalhe_admin_view(request, self.disparo.id)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("https://example.org/recente", html)
        self.assertNotIn("https://example.org/antigo", html)

    def test_comparativo_links_periodo_atual_vs_anterior(self):
        agora = timezone.now()
        DisparoEmailClique.objects.create(
            disparo=self.disparo,
            destino=self.destino,
            url="https://example.org/a1",
        )
        DisparoEmailClique.objects.create(
            disparo=self.disparo,
            destino=self.destino,
            url="https://example.org/a2",
        )
        clique_anterior = DisparoEmailClique.objects.create(
            disparo=self.disparo,
            destino=self.destino,
            url="https://example.org/b1",
        )
        DisparoEmailClique.objects.filter(id=clique_anterior.id).update(
            criado_em=agora - timedelta(days=31)
        )

        User = get_user_model()
        admin = User.objects.create_user(
            username="admin_comparativo_links",
            email="admin_comparativo_links@example.com",
            password="Senha@12345",
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        request = RequestFactory().get(
            reverse("admin_email_disparo_detalhe", args=[self.disparo.id]),
            data={"periodo_links": "30"},
        )
        request.user = admin
        response = email_disparo_detalhe_admin_view(request, self.disparo.id)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Janela atual (30 dias): <strong>2</strong>", html)
        self.assertIn("Janela anterior: <strong>1</strong>", html)
        self.assertIn("Tendência: <strong>alta</strong>", html)
