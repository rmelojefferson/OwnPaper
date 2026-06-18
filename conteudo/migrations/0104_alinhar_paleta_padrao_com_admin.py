from django.db import migrations, models


OLD_PRIMARY = "#0f172a"
OLD_SECONDARY = "#1d4ed8"
NEW_PRIMARY = "#1f3b5c"
NEW_SECONDARY = "#3b82f6"


def alinhar_paleta_padrao(apps, schema_editor):
    ConfiguracaoSite = apps.get_model("conteudo", "ConfiguracaoSite")
    ConfiguracaoSite.objects.filter(
        paleta_cor_1=OLD_PRIMARY,
        paleta_cor_2=OLD_SECONDARY,
    ).update(
        paleta_cor_1=NEW_PRIMARY,
        paleta_cor_2=NEW_SECONDARY,
    )


def reverter_paleta_padrao(apps, schema_editor):
    ConfiguracaoSite = apps.get_model("conteudo", "ConfiguracaoSite")
    ConfiguracaoSite.objects.filter(
        paleta_cor_1=NEW_PRIMARY,
        paleta_cor_2=NEW_SECONDARY,
    ).update(
        paleta_cor_1=OLD_PRIMARY,
        paleta_cor_2=OLD_SECONDARY,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0103_alter_perguntaquizcatalogo_categoria_editorial_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="configuracaosite",
            name="paleta_cor_1",
            field=models.CharField(
                default=NEW_PRIMARY,
                help_text="Hexadecimal no formato #RRGGBB.",
                max_length=7,
                verbose_name="Paleta cor 1",
            ),
        ),
        migrations.AlterField(
            model_name="configuracaosite",
            name="paleta_cor_2",
            field=models.CharField(
                default=NEW_SECONDARY,
                help_text="Hexadecimal no formato #RRGGBB.",
                max_length=7,
                verbose_name="Paleta cor 2",
            ),
        ),
        migrations.RunPython(alinhar_paleta_padrao, reverter_paleta_padrao),
    ]
