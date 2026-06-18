from django.db import migrations


def normalizar_rotulo_padrao(apps, schema_editor):
    ConfiguracaoSite = apps.get_model("conteudo", "ConfiguracaoSite")
    ConfiguracaoSite.objects.filter(doacoes_rotulo="Apoie").update(doacoes_rotulo="Apoio")


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0137_doacoes_cabecalho_texto_padrao"),
    ]

    operations = [
        migrations.RunPython(normalizar_rotulo_padrao, migrations.RunPython.noop),
    ]
