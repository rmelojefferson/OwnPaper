import json
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.html import strip_tags
from wagtail.rich_text import expand_db_html

from conteudo.models import PublicacaoPage


class Command(BaseCommand):
    help = "Exporta publicações para pacote de livro portátil (Markdown + índice CSV + manifesto JSON)."

    def add_arguments(self, parser):
        parser.add_argument("--ids", type=str, default="", help="IDs separados por vírgula.")
        parser.add_argument("--tag", type=str, default="", help="Filtrar por slug da tag.")
        parser.add_argument("--todos", action="store_true", help="Exportar todas as publicações live.")
        parser.add_argument("--saida", type=str, default="", help="Caminho final do arquivo ZIP.")

    def handle(self, *args, **options):
        ids_raw = (options.get("ids") or "").strip()
        tag = (options.get("tag") or "").strip()
        todos = bool(options.get("todos"))
        saida = (options.get("saida") or "").strip()

        qs = PublicacaoPage.objects.live().public().prefetch_related("tags", "autores_publicacao__autor")
        if ids_raw:
            ids = [int(item.strip()) for item in ids_raw.split(",") if item.strip().isdigit()]
            qs = qs.filter(id__in=ids)
        elif tag:
            qs = qs.filter(tags__slug=tag).distinct()
        elif not todos:
            self.stderr.write("Informe --ids, --tag ou --todos.")
            return

        publicacoes = list(qs.order_by("data_publicacao", "id"))
        if not publicacoes:
            self.stderr.write("Nenhuma publicação encontrada para exportação.")
            return

        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        if not saida:
            saida = f"/tmp/livro_publicacoes_{timestamp}.zip"
        saida_path = Path(saida)
        saida_path.parent.mkdir(parents=True, exist_ok=True)

        manifest = {
            "gerado_em": timezone.now().isoformat(),
            "total_publicacoes": len(publicacoes),
            "filtro": {
                "ids": ids_raw,
                "tag": tag,
                "todos": todos,
            },
            "arquivos": [],
        }

        with zipfile.ZipFile(saida_path, "w", zipfile.ZIP_DEFLATED) as zf:
            linhas_csv = [["id", "titulo", "data_publicacao", "autores", "slug", "url"]]

            for idx, pub in enumerate(publicacoes, start=1):
                autores = "; ".join([str(autor) for autor in pub.autores_ordenados])
                resumo = strip_tags(expand_db_html(pub.resumo or "")).strip()
                corpo = strip_tags(expand_db_html(pub.corpo or "")).strip()
                data_pub = pub.data_publicacao.strftime("%Y-%m-%d") if pub.data_publicacao else ""
                tags = ", ".join([tag.name for tag in pub.tags.all()])

                nome_arquivo = f"capitulos/{idx:03d}_{pub.slug or pub.id}.md"
                markdown = (
                    f"# {pub.title}\n\n"
                    f"- ID: {pub.id}\n"
                    f"- Data: {data_pub}\n"
                    f"- Autores: {autores or '-'}\n"
                    f"- Tags: {tags or '-'}\n\n"
                    f"## Resumo\n\n{resumo or '-'}\n\n"
                    f"## Conteúdo\n\n{corpo or '-'}\n"
                )
                zf.writestr(nome_arquivo, markdown)
                manifest["arquivos"].append(nome_arquivo)

                linhas_csv.append(
                    [
                        str(pub.id),
                        pub.title,
                        data_pub,
                        autores,
                        pub.slug or "",
                        pub.url or "",
                    ]
                )

            csv_buffer = []
            for row in linhas_csv:
                csv_buffer.append(",".join([f'"{(col or "").replace("\"", "\"\"")}"' for col in row]))
            zf.writestr("indice_publicacoes.csv", "\n".join(csv_buffer))
            zf.writestr("manifesto.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        self.stdout.write(self.style.SUCCESS(f"Exportação concluída: {saida_path}"))
