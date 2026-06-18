from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0089_configuracaosite_menu_home_logo_ajuste_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosite",
            name="busca_expansao_modo",
            field=models.CharField(
                choices=[
                    ("desativada", "Desativada (somente termo original)"),
                    ("sob_demanda", "Sob demanda"),
                    ("cache_persistente", "Cache persistente"),
                ],
                default="cache_persistente",
                help_text=(
                    "Define se a busca usa apenas o termo original, tradução sob demanda "
                    "ou cache persistente de expansões."
                ),
                max_length=32,
                verbose_name="Modo da expansão multilíngue da busca",
            ),
        ),
        migrations.CreateModel(
            name="CacheExpansaoBusca",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("termo", models.CharField(max_length=255, verbose_name="Termo")),
                ("idioma_atual", models.CharField(default="pt-br", max_length=10, verbose_name="Idioma atual")),
                (
                    "idiomas_chave",
                    models.CharField(default="pt-br,en,es", max_length=64, verbose_name="Idiomas selecionados"),
                ),
                ("versao", models.CharField(default="v1", max_length=16, verbose_name="Versão do algoritmo")),
                ("variantes", models.JSONField(blank=True, default=list, verbose_name="Variantes expandidas")),
                ("hits", models.PositiveIntegerField(default=0, verbose_name="Hits")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
            ],
            options={
                "verbose_name": "Cache de expansão da busca",
                "verbose_name_plural": "Cache de expansões da busca",
                "unique_together": {("termo", "idioma_atual", "idiomas_chave", "versao")},
            },
        ),
        migrations.AddIndex(
            model_name="cacheexpansaobusca",
            index=models.Index(
                fields=["idioma_atual", "idiomas_chave", "versao"],
                name="conteudo_ca_idioma__93e418_idx",
            ),
        ),
    ]
