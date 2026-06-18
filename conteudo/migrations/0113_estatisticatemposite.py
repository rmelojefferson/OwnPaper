from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0112_publicacao_status_agendado_sem_aprovado"),
    ]

    operations = [
        migrations.CreateModel(
            name="EstatisticaTempoSite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_hash", models.CharField(db_index=True, max_length=64, verbose_name="Hash da sessão")),
                ("path", models.CharField(db_index=True, max_length=500, verbose_name="Caminho")),
                ("started_at", models.DateTimeField(db_index=True, verbose_name="Iniciado em")),
                ("last_seen_at", models.DateTimeField(db_index=True, verbose_name="Último sinal em")),
                ("duration_seconds", models.PositiveIntegerField(default=0, verbose_name="Duração em segundos")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
            ],
            options={
                "verbose_name": "Estatística de tempo no site",
                "verbose_name_plural": "Estatísticas de tempo no site",
            },
        ),
        migrations.AddIndex(
            model_name="estatisticatemposite",
            index=models.Index(fields=["started_at", "duration_seconds"], name="conteudo_es_started_80d23d_idx"),
        ),
        migrations.AddIndex(
            model_name="estatisticatemposite",
            index=models.Index(fields=["session_hash", "path"], name="conteudo_es_session_2246a1_idx"),
        ),
        migrations.AddConstraint(
            model_name="estatisticatemposite",
            constraint=models.UniqueConstraint(fields=("session_hash", "path", "started_at"), name="unique_estatistica_tempo_site_sessao_pagina_inicio"),
        ),
    ]
