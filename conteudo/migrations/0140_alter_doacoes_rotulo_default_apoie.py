from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0139_normalizar_rotulo_apoie"),
    ]

    operations = [
        migrations.AlterField(
            model_name="configuracaosite",
            name="doacoes_rotulo",
            field=models.CharField(blank=True, default="Apoie", max_length=120, verbose_name="Rótulo do botão/link de apoio"),
        ),
    ]
