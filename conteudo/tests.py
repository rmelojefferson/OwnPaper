import os
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from wagtail.models import Site

from conteudo.models import ConfiguracaoSite, PublicacaoPage, PublicacoesIndexPage
from home.models import HomePage


BOOTSTRAP_ENV = {
    "OWNPAPER_SITE_NAME": "OwnPaper Test",
    "OWNPAPER_SITE_HOSTNAME": "localhost",
    "OWNPAPER_SITE_PORT": "80",
    "OWNPAPER_HOME_TITLE": "Home",
    "OWNPAPER_SITE_DESCRIPTION": "OwnPaper test installation.",
    "OWNPAPER_INDEXER_LABEL": "Biblioteca",
}


def run_bootstrap():
    output = StringIO()
    with patch.dict(os.environ, BOOTSTRAP_ENV, clear=False):
        call_command("bootstrap_ownpaper", stdout=output)
    return output.getvalue()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class BootstrapOwnPaperTests(TestCase):
    def test_bootstrap_creates_default_site_settings_and_pages(self):
        output = run_bootstrap()

        site = Site.objects.get(is_default_site=True)
        home_page = HomePage.objects.get()
        site_settings = ConfiguracaoSite.for_site(site)

        self.assertIn("OwnPaper bootstrap complete", output)
        self.assertEqual(site.hostname, "localhost")
        self.assertEqual(site.port, 80)
        self.assertEqual(site.root_page_id, home_page.id)
        self.assertEqual(site_settings.nome_site, "OwnPaper Test")
        self.assertEqual(site_settings.rotulo_indexador, "Biblioteca")

        for slug in [
            "sobre",
            "privacidade",
            "cookies",
            "contato",
            "newsletter",
            "indexador",
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
        ]:
            self.assertEqual(home_page.get_children().filter(slug=slug).count(), 1)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class SmokeRouteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        run_bootstrap()

    def test_public_routes_respond(self):
        for path in [
            "/",
            "/busca/",
            "/categorias/",
            "/autores/",
            "/tags/",
            "/indexador/",
            "/robots.txt",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertLess(response.status_code, 500)

    def test_admin_routes_are_reachable(self):
        admin_response = self.client.get("/admin/")
        self.assertEqual(admin_response.status_code, 302)
        self.assertIn("/account/login/", admin_response["Location"])

        login_response = self.client.get("/account/login/")
        self.assertEqual(login_response.status_code, 200)

    def test_custom_indexer_import_admin_url_is_registered(self):
        import_url = reverse("admin_indexador_importar_csv")
        model_url = reverse("admin_indexador_modelo_csv")

        self.assertEqual(import_url, "/admin/indexador/importar-csv/")
        self.assertEqual(model_url, "/admin/indexador/modelo-csv/")

        response = self.client.get(import_url)
        self.assertEqual(response.status_code, 302)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
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
