from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0059_configuracaosite_travar_publicacao_por_orcid"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("usuario_id_ref", models.PositiveIntegerField(blank=True, db_index=True, null=True, verbose_name="ID técnico do usuário")),
                ("usuario_email", models.EmailField(blank=True, max_length=254, verbose_name="E-mail do usuário")),
                ("usuario_username", models.CharField(blank=True, max_length=150, verbose_name="Username do usuário")),
                ("acao", models.CharField(db_index=True, max_length=80, verbose_name="Ação")),
                ("alvo_tipo", models.CharField(blank=True, db_index=True, max_length=120, verbose_name="Tipo de alvo")),
                ("alvo_id", models.CharField(blank=True, max_length=64, verbose_name="ID do alvo")),
                ("alvo_repr", models.CharField(blank=True, max_length=255, verbose_name="Alvo")),
                ("ip", models.CharField(blank=True, max_length=64, verbose_name="IP")),
                ("detalhes", models.TextField(blank=True, verbose_name="Detalhes")),
                ("criado_em", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Criado em")),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Usuário",
                    ),
                ),
            ],
            options={
                "verbose_name": "Log de atividade",
                "verbose_name_plural": "Logs de atividade",
                "ordering": ["-criado_em"],
            },
        ),
    ]
