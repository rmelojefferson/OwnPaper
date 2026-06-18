import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0078_comentarios_publicos_models_and_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuariocomentario",
            name="nome",
            field=models.CharField(blank=True, max_length=120, verbose_name="Nome"),
        ),
        migrations.CreateModel(
            name="ComentarioAcessoCodigo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Token")),
                (
                    "fluxo",
                    models.CharField(
                        choices=[("login", "Login"), ("cadastro", "Cadastro")],
                        db_index=True,
                        max_length=20,
                        verbose_name="Fluxo",
                    ),
                ),
                ("codigo", models.CharField(db_index=True, max_length=6, verbose_name="Código")),
                ("email", models.EmailField(max_length=254, verbose_name="E-mail")),
                ("username", models.SlugField(blank=True, max_length=80, verbose_name="Nome de usuário")),
                ("nome", models.CharField(blank=True, max_length=120, verbose_name="Nome")),
                ("orcid", models.CharField(blank=True, max_length=19, verbose_name="ORCID")),
                ("expira_em", models.DateTimeField(verbose_name="Expira em")),
                ("usado_em", models.DateTimeField(blank=True, null=True, verbose_name="Usado em")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                (
                    "publicacao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="conteudo.publicacaopage",
                        verbose_name="Publicação",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="conteudo.usuariocomentario",
                        verbose_name="Usuário",
                    ),
                ),
            ],
            options={
                "verbose_name": "Código de acesso para comentário",
                "verbose_name_plural": "Códigos de acesso para comentários",
                "ordering": ["-criado_em"],
            },
        ),
    ]
