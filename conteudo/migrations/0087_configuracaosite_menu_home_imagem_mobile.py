from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wagtailimages", "0001_initial"),
        ("conteudo", "0086_configuracaosite_oauth_fields_identidadeexternacomentario"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosite",
            name="menu_home_imagem_mobile_claro",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="+",
                to="wagtailimages.image",
                verbose_name="Imagem/logo da Home no mobile (tema claro)",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="menu_home_imagem_mobile_escuro",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="+",
                to="wagtailimages.image",
                verbose_name="Imagem/logo da Home no mobile (tema escuro)",
            ),
        ),
    ]
