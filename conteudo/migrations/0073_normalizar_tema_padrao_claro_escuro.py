from django.db import migrations


def normalizar_tema_padrao(apps, schema_editor):
    ConfiguracaoSite = apps.get_model("conteudo", "ConfiguracaoSite")
    ConfiguracaoSite.objects.filter(tema_padrao_site="sistema").update(tema_padrao_site="claro")


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0072_alter_configuracaosite_tema_padrao_site"),
    ]

    operations = [
        migrations.RunPython(normalizar_tema_padrao, migrations.RunPython.noop),
    ]

