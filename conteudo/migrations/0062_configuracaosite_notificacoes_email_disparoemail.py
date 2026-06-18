from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0061_mensagemcontato_inbox_fields_and_interacoes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosite",
            name="notificacao_publicacoes_modo",
            field=models.CharField(
                choices=[
                    ("desativada", "Desativada"),
                    ("imediata", "Imediata (nova publicação)"),
                    ("periodica", "Consolidada por período"),
                ],
                default="desativada",
                max_length=20,
                verbose_name="Modo de notificação de publicações",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="notificacao_publicacoes_periodo_horas",
            field=models.PositiveIntegerField(
                default=168,
                help_text="Usado quando o modo estiver em consolidado por período. Ex.: 24 (diário), 168 (semanal).",
                verbose_name="Período (horas) para envio consolidado",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="notificacao_publicacoes_ultimo_envio_em",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Último envio de publicações",
            ),
        ),
        migrations.CreateModel(
            name="DisparoEmail",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("manual", "Manual"), ("publicacoes_imediata", "Publicações (imediata)"), ("publicacoes_periodica", "Publicações (periódica)")], default="manual", max_length=30, verbose_name="Tipo")),
                ("segmento", models.CharField(choices=[("todos_usuarios", "Todos os usuários do painel"), ("apenas_admins", "Apenas administradores"), ("apenas_autores", "Apenas autores/escritores"), ("newsletter", "Inscritos ativos da newsletter")], max_length=30, verbose_name="Segmento")),
                ("assunto", models.CharField(max_length=255, verbose_name="Assunto")),
                ("corpo_html", models.TextField(verbose_name="Corpo HTML")),
                ("status", models.CharField(choices=[("pendente", "Pendente"), ("enviando", "Enviando"), ("concluido", "Concluído"), ("falhou", "Falhou")], db_index=True, default="pendente", max_length=20, verbose_name="Status")),
                ("total_destinatarios", models.PositiveIntegerField(default=0, verbose_name="Total de destinatários")),
                ("total_enviados", models.PositiveIntegerField(default=0, verbose_name="Total enviados")),
                ("total_falhas", models.PositiveIntegerField(default=0, verbose_name="Total de falhas")),
                ("erro", models.TextField(blank=True, verbose_name="Erro")),
                ("metadata", models.JSONField(blank=True, default=dict, verbose_name="Metadados")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("enviado_em", models.DateTimeField(blank=True, null=True, verbose_name="Enviado em")),
                ("criado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="Criado por")),
            ],
            options={
                "verbose_name": "Disparo de e-mail",
                "verbose_name_plural": "Disparos de e-mail",
                "ordering": ["-criado_em"],
            },
        ),
    ]
