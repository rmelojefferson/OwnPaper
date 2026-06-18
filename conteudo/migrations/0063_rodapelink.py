from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0062_configuracaosite_notificacoes_email_disparoemail"),
    ]

    operations = [
        migrations.CreateModel(
            name="RodapeLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="Ordem")),
                ("ativo", models.BooleanField(default=True, verbose_name="Ativo")),
                ("titulo", models.CharField(max_length=120, verbose_name="Título")),
                ("tipo", models.CharField(choices=[("pagina", "Página interna"), ("url", "URL externa"), ("atalho", "Atalho do site")], default="pagina", max_length=20, verbose_name="Tipo")),
                ("url_externa", models.URLField(blank=True, verbose_name="URL externa")),
                ("atalho", models.CharField(blank=True, choices=[("home", "Home"), ("categorias", "Categorias"), ("tags", "Tags"), ("autores", "Autores"), ("busca", "Busca"), ("destaques", "Âncora: Destaques"), ("ultimas", "Âncora: Últimas publicações"), ("contato", "Contato"), ("newsletter", "Newsletter"), ("indexador", "Indexador")], max_length=30, verbose_name="Atalho do site")),
                ("abrir_nova_aba", models.BooleanField(default=False, verbose_name="Abrir em nova aba")),
                ("configuracao_site", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rodape_links", to="conteudo.configuracaosite")),
                ("pagina", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="wagtailcore.page", verbose_name="Página interna")),
            ],
            options={
                "verbose_name": "Link do rodapé",
                "verbose_name_plural": "Links do rodapé",
                "ordering": ["sort_order", "id"],
            },
        ),
    ]
