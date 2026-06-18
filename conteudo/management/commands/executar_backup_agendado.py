from django.core.management.base import BaseCommand
from wagtail.models import Site

from conteudo.backup_ops import backup_agendado_pendente, executar_backup_site
from conteudo.models import BackupExecucao


class Command(BaseCommand):
    help = "Executa backup agendado para todos os sites elegíveis."

    def handle(self, *args, **options):
        total = 0
        for site in Site.objects.all():
            if not backup_agendado_pendente(site):
                continue
            execucao = executar_backup_site(
                site=site,
                solicitado_por=None,
                tipo=BackupExecucao.TIPO_AGENDADO,
                incluir_midia=True,
            )
            total += 1
            self.stdout.write(
                f"{site.hostname}: status={execucao.status} arquivo={execucao.arquivo_caminho or '-'}"
            )
        self.stdout.write(self.style.SUCCESS(f"Backups agendados executados: {total}"))
