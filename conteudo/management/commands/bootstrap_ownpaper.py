import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify
from wagtail.models import Page, Site

from conteudo.models import (
    ConfiguracaoSite,
    ContatoPage,
    IndexadorPage,
    NewsletterPage,
    PaginaInstitucionalPage,
    PublicacoesIndexPage,
)
from home.models import HomePage


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ["1", "true", "yes", "on"]


def env_value(name, default=""):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def first_public_host():
    for host in settings.ALLOWED_HOSTS:
        hostname = host.split(":")[0]
        if hostname and hostname != "*":
            return hostname
    return "localhost"


class Command(BaseCommand):
    help = "Bootstrap a fresh OwnPaper Wagtail installation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--site-name",
            default=os.getenv("OWNPAPER_SITE_NAME", settings.WAGTAIL_SITE_NAME),
            help="Public site name.",
        )
        parser.add_argument(
            "--hostname",
            default=os.getenv("OWNPAPER_SITE_HOSTNAME", first_public_host()),
            help="Wagtail site hostname.",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=int(os.getenv("OWNPAPER_SITE_PORT", "80")),
            help="Wagtail site port.",
        )
        parser.add_argument(
            "--root-title",
            default=os.getenv("OWNPAPER_HOME_TITLE", "Home"),
            help="Home page title.",
        )
        parser.add_argument(
            "--with-pages",
            action="store_true",
            default=env_bool("OWNPAPER_BOOTSTRAP_PAGES", True),
            help="Create default institutional pages when missing.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=env_bool("OWNPAPER_BOOTSTRAP_FORCE", False),
            help="Overwrite existing bootstrap-managed settings.",
        )

    def handle(self, *args, **options):
        hostname = options["hostname"].strip()
        if not hostname:
            raise CommandError("A hostname is required.")

        home_page = self.get_or_create_home_page(options["root_title"])
        site = self.configure_site(home_page, hostname, options["port"])
        site_settings = self.configure_site_settings(
            site,
            site_name=options["site_name"],
            force=options["force"],
        )

        if options["with_pages"]:
            self.create_default_pages(home_page, site_settings, force=options["force"])

        self.create_superuser()

        self.stdout.write(
            self.style.SUCCESS(
                f"OwnPaper bootstrap complete for {site.hostname}:{site.port}."
            )
        )

    def get_or_create_home_page(self, title):
        home_page = HomePage.objects.first()
        if home_page:
            changed = False
            if title and home_page.title != title:
                home_page.title = title
                home_page.draft_title = title
                changed = True
            if not home_page.live:
                home_page.live = True
                changed = True
            if changed:
                home_page.save()
                home_page.save_revision().publish()
            return home_page

        root_page = Page.get_first_root_node()
        if root_page is None:
            raise CommandError("Wagtail root page does not exist. Run migrations first.")

        home_page = HomePage(
            title=title or "Home",
            slug=slugify(title or "home") or "home",
            live=True,
            show_in_menus=True,
        )
        root_page.add_child(instance=home_page)
        home_page.save_revision().publish()
        return home_page

    def configure_site(self, home_page, hostname, port):
        Site.objects.exclude(hostname=hostname).update(is_default_site=False)
        site = Site.objects.filter(hostname=hostname).first()
        if site is None:
            site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()

        if site is None:
            site = Site(hostname=hostname)

        site.hostname = hostname
        site.port = port
        site.root_page = home_page
        site.is_default_site = True
        site.save()
        return site

    def configure_site_settings(self, site, site_name, force=False):
        site_settings = ConfiguracaoSite.for_site(site)
        updates = {
            "nome_site": site_name,
            "seo_title_padrao": site_name,
            "descricao_padrao": os.getenv(
                "OWNPAPER_SITE_DESCRIPTION",
                "OwnPaper editorial CMS.",
            ),
            "texto_rodape": env_value(
                "OWNPAPER_FOOTER_TEXT",
                f"{site_name}",
            ),
            "copyright_texto": env_value(
                "OWNPAPER_COPYRIGHT_TEXT",
                f"{site_name}",
            ),
            "email_contato": os.getenv("OWNPAPER_CONTACT_EMAIL", ""),
            "rotulo_indexador": env_value("OWNPAPER_INDEXER_LABEL", "Indexador"),
        }

        changed = False
        for field, value in updates.items():
            current = getattr(site_settings, field)
            default = site_settings._meta.get_field(field).default
            if force or not current or current == default:
                setattr(site_settings, field, value)
                changed = True

        if changed:
            site_settings.save()

        return site_settings

    def create_default_pages(self, home_page, site_settings, force=False):
        default_pages = [
            (
                "publicacoes",
                PublicacoesIndexPage,
                {
                    "title": "Publicações",
                    "introducao": "Consulte as publicacoes mais recentes.",
                },
                None,
            ),
            (
                "sobre",
                PaginaInstitucionalPage,
                {
                    "title": "Sobre",
                    "resumo": "Conte a historia, o escopo e a proposta editorial do projeto.",
                    "corpo": "",
                },
                "pagina_sobre",
            ),
            (
                "privacidade",
                PaginaInstitucionalPage,
                {
                    "title": "Privacidade e dados",
                    "resumo": "Explique como dados pessoais sao tratados nesta instalacao.",
                    "corpo": "",
                },
                "pagina_privacidade",
            ),
            (
                "cookies",
                PaginaInstitucionalPage,
                {
                    "title": "Cookies",
                    "resumo": "Descreva os cookies e tecnologias equivalentes usados no site.",
                    "corpo": "",
                },
                "pagina_cookies",
            ),
            (
                "contato",
                ContatoPage,
                {
                    "title": "Contato",
                    "introducao": "Envie sua mensagem.",
                    "email_destino": os.getenv("OWNPAPER_CONTACT_EMAIL", ""),
                },
                "pagina_contato",
            ),
            (
                "newsletter",
                NewsletterPage,
                {
                    "title": "Newsletter",
                    "introducao": "Receba novidades por e-mail.",
                },
                "pagina_newsletter",
            ),
            (
                "indexador",
                IndexadorPage,
                {
                    "title": "Indexador",
                    "introducao": "Pesquise registros catalogados.",
                },
                "pagina_indexador",
            ),
        ]

        for slug, model, values, setting_field in default_pages:
            page = model.objects.child_of(home_page).filter(slug=slug).first()
            if page is None:
                page = model(slug=slug, live=True, show_in_menus=True, **values)
                home_page.add_child(instance=page)
                page.save_revision().publish()
                self.stdout.write(f"Created page: {page.title}")
            elif force:
                for field, value in values.items():
                    setattr(page, field, value)
                page.live = True
                page.show_in_menus = True
                page.save()
                page.save_revision().publish()
                self.stdout.write(f"Updated page: {page.title}")

            if setting_field and (force or getattr(site_settings, f"{setting_field}_id") is None):
                setattr(site_settings, setting_field, page)

        site_settings.save()

    def create_superuser(self):
        username = os.getenv("OWNPAPER_ADMIN_USERNAME") or os.getenv(
            "DJANGO_SUPERUSER_USERNAME"
        )
        email = os.getenv("OWNPAPER_ADMIN_EMAIL") or os.getenv("DJANGO_SUPERUSER_EMAIL")
        password = os.getenv("OWNPAPER_ADMIN_PASSWORD") or os.getenv(
            "DJANGO_SUPERUSER_PASSWORD"
        )

        if not username or not password:
            self.stdout.write(
                "Admin user skipped. Set OWNPAPER_ADMIN_USERNAME and "
                "OWNPAPER_ADMIN_PASSWORD to create one automatically."
            )
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email or "", "is_staff": True, "is_superuser": True},
        )

        changed = created
        if email and user.email != email:
            user.email = email
            changed = True
        if not user.is_staff or not user.is_superuser:
            user.is_staff = True
            user.is_superuser = True
            changed = True
        if created or env_bool("OWNPAPER_ADMIN_RESET_PASSWORD", False):
            user.set_password(password)
            changed = True

        if changed:
            user.save()

        status = "created" if created else "ready"
        self.stdout.write(f"Admin user {status}: {username}")
