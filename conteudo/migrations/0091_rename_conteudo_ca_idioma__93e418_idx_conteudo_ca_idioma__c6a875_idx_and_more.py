from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0090_configuracaosite_busca_expansao_modo_cacheexpansaobusca"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="cacheexpansaobusca",
            new_name="conteudo_ca_idioma__c6a875_idx",
            old_name="conteudo_ca_idioma__93e418_idx",
        ),
        migrations.AlterField(
            model_name="configuracaosite",
            name="menu_home_logo_proporcao",
            field=models.CharField(
                choices=[
                    ("auto", "Manter proporção original da imagem"),
                    ("1:1", "1:1"),
                    ("3:2", "3:2"),
                    ("4:3", "4:3"),
                    ("5:1", "5:1"),
                    ("16:9", "16:9"),
                    ("21:9", "21:9"),
                    ("12:5", "12:5"),
                ],
                default="auto",
                help_text="Defina uma proporção fixa ou mantenha a original do arquivo enviado.",
                max_length=20,
                verbose_name="Proporção do botão/logo da Home",
            ),
        ),
    ]
