# Generated manually to remove the deprecated automatic search translation path.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0132_backups_webdav_painel"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="configuracaosite",
            name="busca_expansao_modo",
        ),
        migrations.DeleteModel(
            name="CacheExpansaoBusca",
        ),
    ]
