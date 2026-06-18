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
    QuizEstudoPage,
)
from conteudo.roles import ensure_role_groups
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
            default=os.getenv("OWNPAPER_SITE_NAME", settings.WAGTAIL_SITE_NAME or "OwnPaper"),
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
            default=os.getenv("OWNPAPER_HOME_TITLE", "Início"),
            help="Título da página inicial.",
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
        options["site_name"] = (options.get("site_name") or "").strip() or "OwnPaper"

        home_page = self.get_or_create_home_page(options["root_title"])
        site = self.configure_site(home_page, hostname, options["port"])
        site_settings = self.configure_site_settings(
            site,
            site_name=options["site_name"],
            force=options["force"],
        )

        if options["with_pages"]:
            self.create_default_pages(home_page, site_settings, force=options["force"])

        self.ensure_default_groups()
        self.create_superuser()

        self.stdout.write(
            self.style.SUCCESS(
                f"OwnPaper bootstrap complete for {site.hostname}:{site.port}."
            )
        )

    def ensure_default_groups(self):
        ensure_role_groups()

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
            title=title or "Início",
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
                f"Todos os direitos reservados © 2026 {site_name}",
            ),
            "email_contato": os.getenv("OWNPAPER_CONTACT_EMAIL", ""),
            "rotulo_indexador": env_value("OWNPAPER_INDEXER_LABEL", "Indexador"),
            "paleta_cor_1": env_value("OWNPAPER_SITE_COLOR_PRIMARY", "#1f3b5c"),
            "paleta_cor_2": env_value("OWNPAPER_SITE_COLOR_SECONDARY", "#3b82f6"),
            "doacoes_rotulo": env_value("OWNPAPER_DONATIONS_LABEL", "Apoie"),
            "doacoes_titulo": env_value("OWNPAPER_DONATIONS_TITLE", "Apoie o projeto"),
            "doacoes_descricao": env_value(
                "OWNPAPER_DONATIONS_DESCRIPTION",
                (
                    "<p>Se este projeto é útil para você, considere contribuir para manter "
                    "a publicação independente, a infraestrutura técnica e o desenvolvimento "
                    "de novos recursos. Todo apoio ajuda a sustentar o trabalho editorial e "
                    "a continuidade do site.</p>"
                ),
            ),
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
        cookies_resumo = (
            "Esta página descreve os cookies, tecnologias similares e dados básicos "
            "tratados pela instalação padrão do OwnPaper, incluindo a medição agregada "
            "de tempo médio no site quando cookies opcionais são aceitos, com retenção "
            "padrão de eventos brutos por até 3 meses e agregados diários por até 12 meses."
        )
        cookies_corpo = (
            "<h2>1. O que é coletado na estrutura padrão</h2>"
            "<ul>"
            "<li><strong>Essenciais:</strong> cookies de sessão e segurança (login/admin, CSRF e autenticação).</li>"
            "<li><strong>Preferências:</strong> tema (claro/escuro), tamanho de fonte e preferências locais da interface.</li>"
            "<li><strong>Consentimento:</strong> escolha de cookies (aceitar tudo ou recusar opcionais).</li>"
            "<li><strong>Formulários:</strong> dados enviados em contato e newsletter conforme os campos preenchidos.</li>"
            "<li><strong>Estatísticas internas:</strong> quando cookies opcionais são aceitos, página acessada, duração aproximada da visita e sinais periódicos de permanência.</li>"
            "</ul>"
            "<h2>2. Cookies opcionais (rastreamento)</h2>"
            "<p>Google Tag Manager, Google Analytics, Meta Pixel e a estatística interna de tempo médio só são carregados ou registrados após consentimento para opcionais.</p>"
            "<p>A estatística interna de tempo médio usa um identificador aleatório de sessão armazenado no navegador e convertido em hash no servidor. Ela não grava nome, e-mail, usuário do painel ou endereço IP para essa medição.</p>"
            "<p>Na configuração padrão, eventos brutos são mantidos por até 3 meses e agregados diários por até 12 meses. O administrador pode desativar as estatísticas internas nas configurações do site.</p>"
            "<p>Para análises mais profundas, o projeto pode usar ferramentas externas de analytics condicionadas ao consentimento de cookies opcionais. O OwnPaper recomenda integrações por campos estruturados, evitando script livre inserido manualmente.</p>"
            "<p>Ao recusar opcionais, o site continua funcionando sem carregar scripts opcionais de rastreamento e sem registrar tempo médio de permanência.</p>"
            "<h2>3. Escolha obrigatória, aceite opcional</h2>"
            "<p>Quando não houver escolha registrada, o site exibe o aviso de cookies para que você aceite tudo ou recuse os opcionais. A navegação deve continuar possível, mas a decisão fica disponível para ser feita de forma clara.</p>"
            "<h2>4. Base legal e finalidade</h2>"
            "<ul>"
            "<li><strong>Essenciais:</strong> legítimo interesse e execução do serviço.</li>"
            "<li><strong>Opcionais:</strong> consentimento.</li>"
            "</ul>"
            "<h2>5. Como gerenciar sua escolha</h2>"
            "<p>Você pode alterar sua escolha a qualquer momento clicando no botão <strong>Gerenciar cookies</strong> e escolhendo novamente suas preferências.</p>"
            "<h2>6. O que pode ser adicionado em projetos derivados</h2>"
            "<p>Se o projeto instalar novas ferramentas (chat, anúncios, mapas, vídeos externos com rastreamento, A/B test, etc.), esta página deve ser atualizada com as novas coletas e finalidades.</p>"
        )

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
                    "resumo": "Informe como dados pessoais são tratados nesta instalação, quais solicitações o usuário pode fazer e como a política respeita a LGPD.",
                    "corpo": "",
                },
                "pagina_privacidade",
            ),
            (
                "cookies",
                PaginaInstitucionalPage,
                {
                    "title": "Cookies",
                    "resumo": cookies_resumo,
                    "corpo": cookies_corpo,
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
            (
                "quiz",
                QuizEstudoPage,
                {
                    "title": "Quiz",
                    "introducao": "Estude por perguntas e respostas.",
                    "itens_por_sessao": 20,
                },
                "pagina_quiz_estudo",
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

        if username.strip().lower() == "admin":
            self.stdout.write(
                "Admin user skipped. Username 'admin' is blocked for security. "
                "Set OWNPAPER_ADMIN_USERNAME with another value."
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
