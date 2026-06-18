from django.core.management.base import BaseCommand, CommandError

from conteudo.models import AuditLog


class Command(BaseCommand):
    help = "Verifica a cadeia criptográfica append-only dos logs de auditoria."

    def handle(self, *args, **options):
        resultado = AuditLog.verificar_integridade()
        if not resultado.get("ok"):
            partes = [resultado.get("erro") or "Integridade comprometida."]
            if resultado.get("log_id"):
                partes.append(f"log_id={resultado['log_id']}")
            if resultado.get("esperado"):
                partes.append(f"esperado={resultado['esperado']}")
                partes.append(f"encontrado={resultado.get('encontrado')}")
            raise CommandError(" | ".join(partes))

        self.stdout.write(
            self.style.SUCCESS(
                f"Cadeia de logs íntegra: {resultado.get('total', 0)} registro(s). "
                f"Último hash: {resultado.get('ultimo_hash') or '-'}"
            )
        )
