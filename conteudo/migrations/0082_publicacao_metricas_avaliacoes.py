from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0081_autor_traducoes_categoria_traducoes_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicacaopage",
            name="soma_avaliacoes_meio",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Armazena a soma das notas em escala de meio ponto. Ex.: 3,5 = 7.",
                verbose_name="Soma das avaliações (meio ponto)",
            ),
        ),
        migrations.AddField(
            model_name="publicacaopage",
            name="total_avaliacoes",
            field=models.PositiveIntegerField(default=0, verbose_name="Total de avaliações"),
        ),
        migrations.AddField(
            model_name="publicacaopage",
            name="total_visualizacoes",
            field=models.PositiveIntegerField(default=0, verbose_name="Total de visualizações"),
        ),
        migrations.CreateModel(
            name="AvaliacaoPublicacao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cookie_id", models.CharField(db_index=True, max_length=64, verbose_name="ID do cookie")),
                (
                    "valor_meio",
                    models.PositiveSmallIntegerField(
                        help_text="Escala de 1 a 10, onde 10 corresponde a 5 estrelas.",
                        verbose_name="Nota em meio ponto",
                    ),
                ),
                ("ip_origem", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP de origem")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                (
                    "publicacao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="avaliacoes_publicacao",
                        to="conteudo.publicacaopage",
                        verbose_name="Publicação",
                    ),
                ),
            ],
            options={
                "verbose_name": "Avaliação da publicação",
                "verbose_name_plural": "Avaliações das publicações",
                "ordering": ["-atualizado_em"],
            },
        ),
        migrations.AddConstraint(
            model_name="avaliacaopublicacao",
            constraint=models.UniqueConstraint(
                fields=("publicacao", "cookie_id"),
                name="unique_publicacao_avaliacao_cookie",
            ),
        ),
    ]
