from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0063_rodapelink"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_anexar_limite_mb",
            field=models.PositiveIntegerField(default=10, verbose_name="Limite de anexo do backup (MB)"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_email_destino",
            field=models.EmailField(blank=True, max_length=254, verbose_name="E-mail para relatório de backup"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_enviar_relatorio",
            field=models.BooleanField(default=False, verbose_name="Enviar relatório por e-mail"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_periodo_horas",
            field=models.PositiveIntegerField(default=168, verbose_name="Período do backup automático (horas)"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_reter_dias",
            field=models.PositiveIntegerField(default=30, verbose_name="Retenção dos arquivos de backup (dias)"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_ultimo_envio_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Última execução de backup"),
        ),
        migrations.CreateModel(
            name="BackupExecucao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("manual", "Manual"), ("agendado", "Agendado")], default="manual", max_length=20, verbose_name="Tipo")),
                ("status", models.CharField(choices=[("em_execucao", "Em execução"), ("concluido", "Concluído"), ("falhou", "Falhou")], db_index=True, max_length=20, verbose_name="Status")),
                ("formato_db", models.CharField(choices=[("pg_dump", "pg_dump"), ("json", "JSON (dumpdata)")], default="json", max_length=20, verbose_name="Formato do banco")),
                ("inclui_midia", models.BooleanField(default=True, verbose_name="Inclui mídia")),
                ("arquivo_caminho", models.CharField(blank=True, max_length=500, verbose_name="Caminho do arquivo")),
                ("arquivo_tamanho_bytes", models.BigIntegerField(default=0, verbose_name="Tamanho (bytes)")),
                ("checksum_sha256", models.CharField(blank=True, max_length=64, verbose_name="Checksum SHA256")),
                ("detalhes", models.JSONField(blank=True, default=dict, verbose_name="Detalhes")),
                ("erro", models.TextField(blank=True, verbose_name="Erro")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("concluido_em", models.DateTimeField(blank=True, null=True, verbose_name="Concluído em")),
                ("site", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="backups_execucoes", to="wagtailcore.site", verbose_name="Site")),
                ("solicitado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="Solicitado por")),
            ],
            options={
                "verbose_name": "Execução de backup",
                "verbose_name_plural": "Execuções de backup",
                "ordering": ["-criado_em"],
            },
        ),
    ]
