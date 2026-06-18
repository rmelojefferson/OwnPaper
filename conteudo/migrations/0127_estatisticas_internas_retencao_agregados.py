from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0126_usuariopainelperfil_termos_painel"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosite",
            name="estatisticas_internas_ativas",
            field=models.BooleanField(
                default=True,
                help_text="Quando ativo, o OwnPaper registra estatísticas internas somente após consentimento de cookies opcionais.",
                verbose_name="Ativar estatísticas internas",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="estatisticas_reter_agregados_dias",
            field=models.PositiveIntegerField(
                default=365,
                help_text="Padrão recomendado: 365 dias.",
                verbose_name="Retenção dos agregados diários (dias)",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="estatisticas_reter_eventos_brutos_dias",
            field=models.PositiveIntegerField(
                default=90,
                help_text="Padrão recomendado: 90 dias.",
                verbose_name="Retenção dos eventos brutos (dias)",
            ),
        ),
        migrations.CreateModel(
            name="EstatisticaDiariaSite",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("data", models.DateField(db_index=True, verbose_name="Data")),
                ("path", models.CharField(db_index=True, max_length=500, verbose_name="Caminho")),
                ("sessoes", models.PositiveIntegerField(default=0, verbose_name="Sessões")),
                ("tempo_total_seconds", models.PositiveBigIntegerField(default=0, verbose_name="Tempo total em segundos")),
                ("tempo_medio_seconds", models.PositiveIntegerField(default=0, verbose_name="Tempo médio em segundos")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
            ],
            options={
                "verbose_name": "Estatística diária do site",
                "verbose_name_plural": "Estatísticas diárias do site",
                "ordering": ["-data", "path"],
            },
        ),
        migrations.AddIndex(
            model_name="estatisticadiariasite",
            index=models.Index(fields=["data", "path"], name="conteudo_ed_data_path_idx"),
        ),
        migrations.AddConstraint(
            model_name="estatisticadiariasite",
            constraint=models.UniqueConstraint(fields=("data", "path"), name="unique_estatistica_diaria_site_data_path"),
        ),
    ]
