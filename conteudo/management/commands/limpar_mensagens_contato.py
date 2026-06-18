from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from conteudo.models import MensagemContato


class Command(BaseCommand):
    help = "Remove mensagens de contato antigas com base na política de retenção."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias",
            type=int,
            default=settings.CONTACT_MESSAGES_RETENTION_DAYS,
            help=(
                "Remove mensagens com criado_em anterior a este número de dias. "
                "Padrão: OWNPAPER_CONTACT_MESSAGES_RETENTION_DAYS (ou 365)."
            ),
        )

    def handle(self, *args, **options):
        dias = options["dias"]
        limite = timezone.now() - timedelta(days=dias)

        queryset = MensagemContato.objects.filter(criado_em__lt=limite)
        total = queryset.count()
        queryset.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"{total} mensagem(ns) de contato removida(s) com sucesso."
            )
        )
