from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from wagtail.models import Site

from conteudo.models import ConfiguracaoSite, EstatisticaDiariaSite, EstatisticaTempoSite


class Command(BaseCommand):
    help = "Consolida estatísticas internas e aplica retenção de eventos brutos/agregados."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Mostra o que seria removido sem apagar dados.")

    def handle(self, *args, **options):
        site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
        config = ConfiguracaoSite.for_site(site) if site else None
        reter_brutos = max(1, config.estatisticas_reter_eventos_brutos_dias if config else 90)
        reter_agregados = max(1, config.estatisticas_reter_agregados_dias if config else 365)
        hoje = timezone.localdate()
        limite_brutos = hoje - timedelta(days=reter_brutos)
        limite_agregados = hoje - timedelta(days=reter_agregados)

        eventos_antigos = EstatisticaTempoSite.objects.filter(started_at__date__lt=limite_brutos)
        pares = (
            eventos_antigos.values("path", "started_at__date")
            .annotate(
                sessoes=Count("id"),
                tempo_total=Sum("duration_seconds"),
                tempo_medio=Avg("duration_seconds"),
            )
            .order_by()
        )
        agregados_atualizados = 0
        if not options["dry_run"]:
            for item in pares:
                EstatisticaDiariaSite.objects.update_or_create(
                    data=item["started_at__date"],
                    path=item["path"],
                    defaults={
                        "sessoes": item["sessoes"] or 0,
                        "tempo_total_seconds": item["tempo_total"] or 0,
                        "tempo_medio_seconds": int(item["tempo_medio"] or 0),
                    },
                )
                agregados_atualizados += 1
        else:
            agregados_atualizados = pares.count()

        total_brutos = eventos_antigos.count()
        agregados_antigos = EstatisticaDiariaSite.objects.filter(data__lt=limite_agregados)
        total_agregados = agregados_antigos.count()

        if not options["dry_run"]:
            eventos_antigos.delete()
            agregados_antigos.delete()

        self.stdout.write(
            self.style.SUCCESS(
                "Estatísticas processadas. "
                f"Agregados atualizados: {agregados_atualizados}. "
                f"Eventos brutos removidos: {total_brutos}. "
                f"Agregados removidos: {total_agregados}."
            )
        )
