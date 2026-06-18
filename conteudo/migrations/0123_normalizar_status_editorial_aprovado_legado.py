from django.db import migrations


def normalizar_status_editorial_aprovado(apps, schema_editor):
    PublicacaoPage = apps.get_model("conteudo", "PublicacaoPage")
    Revision = apps.get_model("wagtailcore", "Revision")

    PublicacaoPage.objects.filter(status_editorial="aprovado").update(
        status_editorial="publicado"
    )

    revisoes = Revision.objects.filter(content__status_editorial="aprovado")
    for revisao in revisoes.iterator():
        content = dict(revisao.content or {})
        content["status_editorial"] = "publicado"
        revisao.content = content
        revisao.save(update_fields=["content"])


def reverter_status_editorial_aprovado(apps, schema_editor):
    # O status "aprovado" foi removido do fluxo editorial. A reversão não deve
    # recriar esse estado legado para evitar quebrar validações do Wagtail.
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0122_midiaincorporadapublicacao_midia_pendente_and_more"),
    ]

    operations = [
        migrations.RunPython(
            normalizar_status_editorial_aprovado,
            reverse_code=reverter_status_editorial_aprovado,
        ),
    ]
