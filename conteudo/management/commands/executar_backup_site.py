from django.core.management.base import BaseCommand
from wagtail.models import Site

from conteudo.backup_ops import BACKUP_SCOPE_CHOICES, executar_backup_site, escopo_inclui_midia, normalizar_escopo_backup


class Command(BaseCommand):
    help = "Executa backup manual de banco e mídia para um site."

    def add_arguments(self, parser):
        parser.add_argument("--site-id", type=int, default=0)
        parser.add_argument("--sem-midia", action="store_true")
        parser.add_argument(
            "--escopo",
            choices=[item[0] for item in BACKUP_SCOPE_CHOICES],
            default="total",
            help="Escopo do backup.",
        )

    def handle(self, *args, **options):
        site_id = int(options.get("site_id") or 0)
        if site_id:
            site = Site.objects.filter(id=site_id).first()
        else:
            site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
        if not site:
            self.stderr.write("Site não encontrado.")
            return

        escopo = normalizar_escopo_backup(options.get("escopo"))
        execucao = executar_backup_site(
            site=site,
            solicitado_por=None,
            tipo="manual",
            incluir_midia=escopo_inclui_midia(escopo) and not bool(options.get("sem_midia")),
            escopo=escopo,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Backup status={execucao.status} arquivo={execucao.arquivo_caminho or '-'}"
            )
        )
