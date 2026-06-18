from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0082_publicacao_metricas_avaliacoes"),
    ]

    operations = [
        migrations.AddField(
            model_name="comentariopublicacao",
            name="editado_moderacao_em",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Editado pela moderação em",
            ),
        ),
        migrations.AddField(
            model_name="comentariopublicacao",
            name="editado_pela_moderacao",
            field=models.BooleanField(
                default=False,
                verbose_name="Editado pela moderação",
            ),
        ),
    ]

