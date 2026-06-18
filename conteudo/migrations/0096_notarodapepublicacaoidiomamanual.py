# Generated manually for manual footnote translations on publications.

from django.db import migrations, models
import modelcluster.fields
import wagtail.fields


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0095_publicacaoidiomamanual"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotaRodapePublicacaoIdiomaManual",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("sort_order", models.IntegerField(blank=True, editable=False, null=True)),
                (
                    "marcador_referencia",
                    models.CharField(
                        help_text=(
                            "Use o mesmo marcador da nota original. Se a nota original nao tiver marcador, "
                            "use o numero exibido na lista, como 1, 2, 3."
                        ),
                        max_length=20,
                        verbose_name="Marcador da nota original",
                    ),
                ),
                (
                    "idioma_codigo",
                    models.CharField(
                        help_text="Use um codigo simples, como en, es, fr ou en-us.",
                        max_length=16,
                        verbose_name="Codigo do idioma",
                    ),
                ),
                (
                    "conteudo",
                    wagtail.fields.RichTextField(blank=True, verbose_name="Conteudo no idioma"),
                ),
                (
                    "publicacao",
                    modelcluster.fields.ParentalKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="notas_rodape_idiomas",
                        to="conteudo.publicacaopage",
                    ),
                ),
            ],
            options={
                "verbose_name": "Nota de rodape em outro idioma",
                "verbose_name_plural": "Notas de rodape em outros idiomas",
                "ordering": ["sort_order"],
            },
        ),
    ]
