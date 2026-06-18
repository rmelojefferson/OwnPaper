from django.core.management.base import BaseCommand
from django.utils import timezone

from conteudo.models import SolicitacaoPrivacidadeNewsletter


class Command(BaseCommand):
    help = "Processa solicitações de exclusão de dados da newsletter já vencidas para execução."

    def handle(self, *args, **options):
        agora = timezone.now()

        pendentes = SolicitacaoPrivacidadeNewsletter.objects.filter(
            tipo=SolicitacaoPrivacidadeNewsletter.TIPO_EXCLUSAO,
            status=SolicitacaoPrivacidadeNewsletter.STATUS_ATENDIDA,
            confirmacao_usuario_exclusao=True,
            executada_em__isnull=True,
            executar_apos_em__isnull=False,
            executar_apos_em__lte=agora,
        ).order_by("executar_apos_em")

        total = 0
        for solicitacao in pendentes:
            solicitacao.save()
            if solicitacao.executada_em:
                total += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{total} solicitação(ões) de exclusão processada(s) com sucesso."
            )
        )
