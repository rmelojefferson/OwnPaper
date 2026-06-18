from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from conteudo.models import (
    Categoria,
    PublicacaoPage,
    normalizar_rotulo_taxonomia,
)


class Command(BaseCommand):
    help = (
        "Consolida categorias duplicadas considerando nome normalizado "
        "(ignorando maiúsculas, minúsculas, acentuação e espaços extras)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas mostra o que seria consolidado, sem alterar o banco.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        grupos = defaultdict(list)
        for categoria in Categoria.objects.all().order_by("id"):
            chave = normalizar_rotulo_taxonomia(categoria.nome)
            if chave:
                grupos[chave].append(categoria)

        grupos_duplicados = {
            chave: categorias
            for chave, categorias in grupos.items()
            if len(categorias) > 1
        }

        if not grupos_duplicados:
            self.stdout.write(self.style.SUCCESS("Nenhuma categoria duplicada encontrada."))
            return

        total_removidas = 0
        total_publicacoes_reatribuidas = 0
        with transaction.atomic():
            for chave, categorias in grupos_duplicados.items():
                canonical = self._choose_canonical(categorias)
                duplicadas = [categoria for categoria in categorias if categoria.pk != canonical.pk]

                self.stdout.write(
                    f"[{chave}] manter #{canonical.pk} \"{canonical.nome}\" ({canonical.slug})"
                )

                for duplicada in duplicadas:
                    pubs_qs = PublicacaoPage.objects.filter(categoria_principal=duplicada)
                    pubs_count = pubs_qs.count()

                    self.stdout.write(
                        f"  - consolidar #{duplicada.pk} \"{duplicada.nome}\" ({duplicada.slug}) "
                        f"[publicações={pubs_count}]"
                    )

                    total_publicacoes_reatribuidas += pubs_count
                    total_removidas += 1

                    if dry_run:
                        continue

                    pubs_qs.update(categoria_principal=canonical)
                    duplicada.delete()

            if dry_run:
                transaction.set_rollback(True)

        resumo = (
            f"Categorias removidas: {total_removidas}; "
            f"publicações reatribuídas: {total_publicacoes_reatribuidas}."
        )
        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry-run concluído. {resumo}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Consolidação concluída. {resumo}"))

    def _choose_canonical(self, categorias):
        def score(categoria):
            publicacoes = PublicacaoPage.objects.filter(categoria_principal=categoria).count()
            slug_ascii = 1 if (categoria.slug or "") == slugify(categoria.nome or "") else 0
            return (publicacoes, slug_ascii, -categoria.pk)

        return max(categorias, key=score)
