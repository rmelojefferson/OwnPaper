from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0087_configuracaosite_menu_home_imagem_mobile"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="configuracaosite",
            name="menu_home_imagem_escala",
        ),
    ]
