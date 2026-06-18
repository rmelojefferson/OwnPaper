from django.db import migrations


def normalizar_titulos_home(apps, schema_editor):
    HomePage = apps.get_model("home", "HomePage")

    for home in HomePage.objects.all():
        atualizado = False

        if (home.titulo_carrossel_home or "").strip() in {
            "Publicacoes em destaque",
            "Publicações em destaque",
        }:
            home.titulo_carrossel_home = "Publicações em destaque"
            atualizado = True

        if (home.titulo_ultimas_publicacoes_home or "").strip() in {
            "Ultimas publicacoes",
            "Ultimas publicações",
            "Últimas publicacoes",
            "Ultimas Publicacoes",
            "Últimas Publicacoes",
        }:
            home.titulo_ultimas_publicacoes_home = "Últimas publicações"
            atualizado = True

        if atualizado:
            home.save(
                update_fields=[
                    "titulo_carrossel_home",
                    "titulo_ultimas_publicacoes_home",
                ]
            )


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0008_homepage_itens_por_pagina_ultimas_home"),
    ]

    operations = [
        migrations.RunPython(normalizar_titulos_home, migrations.RunPython.noop),
    ]
