from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def confirmar_autorias_existentes(apps, schema_editor):
    PublicacaoPageAutor = apps.get_model("conteudo", "PublicacaoPageAutor")
    PublicacaoPageAutor.objects.all().update(
        confirmacao_status="confirmado",
        confirmado_em=timezone.now(),
    )


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("conteudo", "0123_normalizar_status_editorial_aprovado_legado"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicacaopageautor",
            name="atribuido_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Atribuído em"),
        ),
        migrations.AddField(
            model_name="publicacaopageautor",
            name="atribuido_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Atribuído por",
            ),
        ),
        migrations.AddField(
            model_name="publicacaopageautor",
            name="confirmacao_status",
            field=models.CharField(
                choices=[
                    ("pendente", "Pendente"),
                    ("confirmado", "Confirmada"),
                    ("rejeitado", "Rejeitada"),
                ],
                db_index=True,
                default="pendente",
                max_length=20,
                verbose_name="Confirmação de autoria",
            ),
        ),
        migrations.AddField(
            model_name="publicacaopageautor",
            name="confirmado_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Confirmado em"),
        ),
        migrations.AddField(
            model_name="publicacaopageautor",
            name="confirmado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Confirmado por",
            ),
        ),
        migrations.AddField(
            model_name="publicacaopageautor",
            name="observacao_confirmacao",
            field=models.TextField(blank=True, verbose_name="Observação da confirmação"),
        ),
        migrations.AddField(
            model_name="publicacaopageautor",
            name="rejeitado_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Rejeitado em"),
        ),
        migrations.AddField(
            model_name="publicacaopageautor",
            name="rejeitado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Rejeitado por",
            ),
        ),
        migrations.RunPython(confirmar_autorias_existentes, reverse_code=noop),
    ]
