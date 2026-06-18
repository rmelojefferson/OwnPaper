from django.db import migrations, models


def converter_aprovado_para_publicado(apps, schema_editor):
    PublicacaoPage = apps.get_model("conteudo", "PublicacaoPage")
    PublicacaoPage.objects.filter(status_editorial="aprovado").update(
        status_editorial="publicado"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0111_remove_assinaturas_richtext_legadas"),
    ]

    operations = [
        migrations.RunPython(converter_aprovado_para_publicado, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="publicacaopage",
            name="status_editorial",
            field=models.CharField(
                choices=[
                    ("rascunho", "Rascunho"),
                    ("em_revisao", "Em revisão"),
                    ("ajustes_solicitados", "Ajustes solicitados"),
                    ("rejeitado", "Rejeitado"),
                    ("agendado", "Agendado"),
                    ("publicado", "Publicado"),
                ],
                db_index=True,
                default="rascunho",
                max_length=32,
                verbose_name="Status editorial",
            ),
        ),
    ]
