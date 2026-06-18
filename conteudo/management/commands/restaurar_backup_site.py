import os
from datetime import datetime

from django.core.management.base import BaseCommand

from conteudo.backup_ops import preparar_restore_backup, simular_restore_backup


class Command(BaseCommand):
    help = (
        "Restauração assistida de backup. Por padrão executa só validação (dry-run). "
        "Use --executar para extrair os arquivos em um diretório de restore."
    )

    def add_arguments(self, parser):
        parser.add_argument("arquivo", type=str)
        parser.add_argument("--checksum", type=str, default="")
        parser.add_argument("--executar", action="store_true")
        parser.add_argument("--destino", type=str, default="")

    def handle(self, *args, **options):
        arquivo = options["arquivo"]
        checksum = (options.get("checksum") or "").strip()
        executar = bool(options.get("executar"))
        destino = (options.get("destino") or "").strip()

        if not executar:
            resultado = simular_restore_backup(arquivo_path=arquivo, checksum_esperado=checksum)
            if not resultado.get("ok"):
                self.stderr.write(resultado.get("erro") or "Falha na validação do backup.")
                return

            manifesto = resultado.get("manifesto") or {}
            arquivos = manifesto.get("arquivos") or []
            db_arquivo = next((n for n in arquivos if ".db." in n), "")
            media_arquivo = next((n for n in arquivos if ".media.tar.gz" in n), "")

            self.stdout.write(self.style.SUCCESS("Validação (dry-run) concluída com sucesso."))
            self.stdout.write(f"Arquivo: {arquivo}")
            self.stdout.write(f"Banco identificado: {db_arquivo or '-'}")
            self.stdout.write(f"Mídia identificada: {media_arquivo or '-'}")
            self.stdout.write("Use --executar para extrair os arquivos e seguir com a restauração manual guiada.")
            return

        if not destino:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            destino = os.path.join("/tmp", f"ownpaper_restore_{timestamp}")

        resultado = preparar_restore_backup(
            arquivo_path=arquivo,
            destino_dir=destino,
            checksum_esperado=checksum,
        )
        if not resultado.get("ok"):
            self.stderr.write(resultado.get("erro") or "Falha ao preparar restauração do backup.")
            return

        db_arquivo = resultado.get("db_arquivo") or ""
        media_arquivo = resultado.get("media_arquivo") or ""
        self.stdout.write(self.style.SUCCESS("Preparação de restauração concluída."))
        self.stdout.write(f"Diretório de restore: {resultado.get('destino')}")
        if db_arquivo:
            self.stdout.write(f"Arquivo de banco: {db_arquivo}")
            if db_arquivo.endswith(".dump"):
                self.stdout.write(
                    "Próximo passo (Postgres): pg_restore -c -d <database> <arquivo_dump>"
                )
            elif db_arquivo.endswith(".json"):
                self.stdout.write(
                    "Próximo passo (JSON): python manage.py loaddata <arquivo_json>"
                )
        if media_arquivo:
            self.stdout.write(f"Arquivo de mídia: {media_arquivo}")
            self.stdout.write(
                "Próximo passo (mídia): tar -xzf <arquivo_media> -C <destino_media>"
            )
