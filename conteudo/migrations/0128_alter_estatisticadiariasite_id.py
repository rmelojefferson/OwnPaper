from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0127_estatisticas_internas_retencao_agregados"),
    ]

    operations = [
        migrations.AlterField(
            model_name="estatisticadiariasite",
            name="id",
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
        ),
    ]
