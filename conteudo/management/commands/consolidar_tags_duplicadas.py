from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from conteudo.models import (
    PublicacaoPageTag,
    TagPublicacao,
    normalizar_rotulo_taxonomia,
)


class Command(BaseCommand):
    help = (
        "Consolida tags duplicadas considerando nome normalizado "
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

        with transaction.atomic():
            resumo_publicacao = self._consolidar_tags_publicacao(dry_run=dry_run)
            if dry_run:
                transaction.set_rollback(True)

        if not any(resumo_publicacao.values()):
            self.stdout.write(self.style.SUCCESS("Nenhuma tag duplicada encontrada."))
            return

        resumo = (
            "Tags editoriais removidas: {pub_removed}; "
            "vínculos editoriais reatribuídos: {pub_links}."
        ).format(
            pub_removed=resumo_publicacao["removed"],
            pub_links=resumo_publicacao["links"],
        )
        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry-run concluído. {resumo}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Consolidação concluída. {resumo}"))

    def _consolidar_tags_publicacao(self, dry_run=False):
        grupos = self._grupos_duplicados(TagPublicacao, "name")
        removed = 0
        links = 0
        for chave, tags in grupos.items():
            canonical = self._choose_canonical_tag_publicacao(tags)
            duplicadas = [tag for tag in tags if tag.pk != canonical.pk]
            self.stdout.write(
                f"[tag-editorial:{chave}] manter #{canonical.pk} \"{canonical.name}\" ({canonical.slug})"
            )

            for duplicada in duplicadas:
                pub_links_qs = PublicacaoPageTag.objects.filter(tag=duplicada)
                pub_count = pub_links_qs.count()

                self.stdout.write(
                    f"  - consolidar #{duplicada.pk} \"{duplicada.name}\" ({duplicada.slug}) "
                    f"[publicações={pub_count}]"
                )

                removed += 1
                links += pub_count

                if dry_run:
                    continue

                pub_links_qs.update(tag=canonical)
                duplicada.delete()

        return {"removed": removed, "links": links}

    def _grupos_duplicados(self, model, field_name):
        grupos = defaultdict(list)
        for item in model.objects.all().order_by("id"):
            chave = normalizar_rotulo_taxonomia(getattr(item, field_name))
            if chave:
                grupos[chave].append(item)
        return {
            chave: itens
            for chave, itens in grupos.items()
            if len(itens) > 1
        }

    def _choose_canonical_tag_publicacao(self, tags):
        def score(tag):
            pub_links = PublicacaoPageTag.objects.filter(tag=tag).count()
            slug_ascii = 1 if (tag.slug or "") == slugify(tag.name or "") else 0
            return (pub_links, slug_ascii, -tag.pk)

        return max(tags, key=score)
