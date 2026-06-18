from django.core.management.base import BaseCommand

from conteudo.email_ops import enviar_publicacoes_periodicas_todos_sites


class Command(BaseCommand):
    help = "Envia notificações periódicas de publicações para inscritos ativos da newsletter."

    def handle(self, *args, **options):
        disparos = enviar_publicacoes_periodicas_todos_sites()
        self.stdout.write(self.style.SUCCESS(f"Disparos executados: {len(disparos)}"))
