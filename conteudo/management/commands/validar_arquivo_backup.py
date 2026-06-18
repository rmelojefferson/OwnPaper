from django.core.management.base import BaseCommand

from conteudo.backup_ops import simular_restore_backup

class Command(BaseCommand):
    help = "Valida integridade de um arquivo de backup (checksum, manifesto e conteúdo)."

    def add_arguments(self, parser):
        parser.add_argument("arquivo", type=str)
        parser.add_argument("--checksum", type=str, default="")

    def handle(self, *args, **options):
        resultado = simular_restore_backup(
            arquivo_path=options["arquivo"],
            checksum_esperado=options.get("checksum") or "",
        )
        if not resultado.get("ok"):
            self.stderr.write(resultado.get("erro") or "Falha na validação do backup.")
            return
        self.stdout.write(self.style.SUCCESS("Backup válido. Estrutura e integridade OK."))
