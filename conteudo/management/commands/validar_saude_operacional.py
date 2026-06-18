import json

from django.core.management.base import BaseCommand, CommandError

from conteudo.health import avaliar_saude_operacional


class Command(BaseCommand):
    help = "Valida saúde operacional do OwnPaper: backup, restore dry-run, logs, ClamAV, e-mail, disco e retenção."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Emite o resultado em JSON.")
        parser.add_argument(
            "--fail-on-warning",
            action="store_true",
            help="Retorna erro também quando houver avisos.",
        )

    def handle(self, *args, **options):
        resultado = avaliar_saude_operacional()

        if options["json"]:
            self.stdout.write(
                json.dumps(
                    resultado,
                    default=str,
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            self.stdout.write(f"Saúde operacional: {resultado['status'].upper()}")
            for item in resultado["itens"]:
                status = item["status"].upper()
                self.stdout.write(f"[{status}] {item['nome']}: {item['mensagem']}")

        if resultado["status"] == "error" or (
            options["fail_on_warning"] and resultado["status"] == "warn"
        ):
            raise CommandError("Saúde operacional com pendências.")
