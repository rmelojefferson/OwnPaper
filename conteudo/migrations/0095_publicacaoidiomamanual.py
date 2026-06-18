from django.db import migrations, models
import modelcluster.fields
import django.db.models.deletion
import wagtail.fields


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0094_quiz_traducoes"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicacaoIdiomaManual",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sort_order", models.IntegerField(blank=True, editable=False, null=True)),
                ("idioma_codigo", models.CharField(help_text="Use um código simples, como en, es, fr ou en-us.", max_length=16, verbose_name="Código do idioma")),
                ("idioma_rotulo", models.CharField(blank=True, help_text="Opcional. Ex.: English, Español, Français.", max_length=80, verbose_name="Rótulo do idioma")),
                ("idioma_rotulo_abreviado", models.CharField(blank=True, help_text="Opcional. Ex.: EN, ES, FR.", max_length=12, verbose_name="Rótulo abreviado")),
                ("title", models.CharField(blank=True, max_length=255, verbose_name="Título")),
                ("seo_title", models.CharField(blank=True, max_length=255, verbose_name="Título SEO")),
                ("search_description", models.TextField(blank=True, verbose_name="Descrição para busca")),
                ("resumo", wagtail.fields.RichTextField(blank=True, verbose_name="Resumo")),
                ("corpo", wagtail.fields.RichTextField(blank=True, verbose_name="Corpo")),
                ("palavras_chave", models.CharField(blank=True, max_length=500, verbose_name="Palavras-chave")),
                ("page", modelcluster.fields.ParentalKey(on_delete=django.db.models.deletion.CASCADE, related_name="idiomas_manuscritos", to="conteudo.publicacaopage")),
            ],
            options={
                "verbose_name": "Versão manual da publicação",
                "verbose_name_plural": "Versões manuais da publicação",
                "ordering": ["sort_order"],
            },
        ),
    ]
