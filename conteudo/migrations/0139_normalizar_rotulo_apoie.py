from django.db import migrations


def normalizar_rotulo_padrao(apps, schema_editor):
    ConfiguracaoSite = apps.get_model("conteudo", "ConfiguracaoSite")
    ConfiguracaoSite.objects.filter(doacoes_rotulo="Apoio").update(doacoes_rotulo="Apoie")


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0138_normalizar_rotulo_apoio_padrao"),
    ]

    operations = [
        migrations.RunPython(normalizar_rotulo_padrao, migrations.RunPython.noop),
    ]
