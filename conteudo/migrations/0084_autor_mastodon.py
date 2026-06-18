from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0083_comentariopublicacao_edicao_moderacao"),
    ]

    operations = [
        migrations.AddField(
            model_name="autor",
            name="mastodon",
            field=models.URLField(blank=True, verbose_name="Mastodon"),
        ),
    ]
