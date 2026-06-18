from django.core.management.base import BaseCommand

from conteudo.backup_ops import executar_backup_site, normalizar_escopo_backup
from conteudo.models import BackupExecucao


class Command(BaseCommand):
    help = "Processa backups solicitados pelo painel sem bloquear a requisição administrativa."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=1)

    def handle(self, *args, **options):
        limite = max(1, int(options.get("limite") or 1))
        pendentes = (
            BackupExecucao.objects.filter(
                tipo=BackupExecucao.TIPO_PAINEL,
                status=BackupExecucao.STATUS_PENDENTE,
            )
            .select_related("site", "solicitado_por")
            .order_by("criado_em")[:limite]
        )
        total = 0
        for execucao in pendentes:
            escopo = normalizar_escopo_backup((execucao.detalhes or {}).get("escopo"))
            resultado = executar_backup_site(
                site=execucao.site,
                solicitado_por=execucao.solicitado_por,
                tipo=BackupExecucao.TIPO_PAINEL,
                incluir_midia=execucao.inclui_midia,
                escopo=escopo,
                execucao=execucao,
            )
            total += 1
            self.stdout.write(
                f"{execucao.site.hostname}: id={execucao.id} escopo={escopo} "
                f"status={resultado.status} arquivo={resultado.arquivo_caminho or '-'}"
            )
        self.stdout.write(self.style.SUCCESS(f"Backups pendentes processados: {total}"))
