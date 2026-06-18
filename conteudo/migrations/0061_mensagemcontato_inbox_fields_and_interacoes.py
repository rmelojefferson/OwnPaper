from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0060_auditlog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="mensagemcontato",
            name="atribuido_para",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="mensagens_contato_atribuidas",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Atribuído para",
            ),
        ),
        migrations.AddField(
            model_name="mensagemcontato",
            name="atualizado_em",
            field=models.DateTimeField(auto_now=True, verbose_name="Atualizado em"),
        ),
        migrations.AddField(
            model_name="mensagemcontato",
            name="status",
            field=models.CharField(
                choices=[
                    ("novo", "Novo"),
                    ("em_andamento", "Em andamento"),
                    ("respondido", "Respondido"),
                    ("arquivado", "Arquivado"),
                ],
                db_index=True,
                default="novo",
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.CreateModel(
            name="InteracaoMensagemContato",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("resposta", "Resposta"), ("encaminhamento", "Encaminhamento"), ("status", "Alteração de status"), ("atribuicao", "Atribuição")], db_index=True, max_length=20, verbose_name="Tipo")),
                ("destinatario_email", models.EmailField(blank=True, max_length=254, verbose_name="Destinatário")),
                ("assunto", models.CharField(blank=True, max_length=255, verbose_name="Assunto")),
                ("corpo", models.TextField(blank=True, verbose_name="Corpo")),
                ("sucesso_envio", models.BooleanField(default=False, verbose_name="Envio com sucesso")),
                ("erro_envio", models.TextField(blank=True, verbose_name="Erro de envio")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("criado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="Criado por")),
                ("mensagem", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="interacoes", to="conteudo.mensagemcontato", verbose_name="Mensagem de contato")),
            ],
            options={
                "verbose_name": "Interação da mensagem de contato",
                "verbose_name_plural": "Interações das mensagens de contato",
                "ordering": ["-criado_em"],
            },
        ),
    ]
