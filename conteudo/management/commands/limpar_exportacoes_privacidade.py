from datetime import timedelta

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.utils import timezone

from conteudo.models import SolicitacaoPrivacidadeNewsletter


class Command(BaseCommand):
    help = "Remove arquivos de exportacao de privacidade antigos e limpa o campo correspondente."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias",
            type=int,
            default=7,
            help="Remove exportacoes com executada_em anterior a este numero de dias. Padrao: 7.",
        )

    def handle(self, *args, **options):
        dias = options["dias"]
        limite = timezone.now() - timedelta(days=dias)

        solicitacoes = SolicitacaoPrivacidadeNewsletter.objects.filter(
            arquivo_exportacao__isnull=False,
            executada_em__isnull=False,
            executada_em__lt=limite,
        ).exclude(arquivo_exportacao="")

        total = 0

        for solicitacao in solicitacoes:
            nome_arquivo = solicitacao.arquivo_exportacao.name

            if nome_arquivo and default_storage.exists(nome_arquivo):
                default_storage.delete(nome_arquivo)

            solicitacao.arquivo_exportacao = None
            solicitacao.save(update_fields=["arquivo_exportacao", "atualizado_em"])
            total += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{total} arquivo(s) de exportacao removido(s) com sucesso."
            )
        )
