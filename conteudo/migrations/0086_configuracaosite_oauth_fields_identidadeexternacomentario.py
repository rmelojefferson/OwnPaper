from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0085_configuracaosite_shlink_fields_linkcurtoshlink"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosite",
            name="oauth_github_client_id",
            field=models.CharField(blank=True, max_length=255, verbose_name="GitHub client ID"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="oauth_github_client_secret",
            field=models.CharField(blank=True, max_length=255, verbose_name="GitHub client secret"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="oauth_gitlab_base_url",
            field=models.URLField(blank=True, default="https://gitlab.com", help_text="Use a URL do GitLab público ou da instância própria.", verbose_name="GitLab base URL"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="oauth_gitlab_client_id",
            field=models.CharField(blank=True, max_length=255, verbose_name="GitLab client ID"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="oauth_gitlab_client_secret",
            field=models.CharField(blank=True, max_length=255, verbose_name="GitLab client secret"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="oauth_orcid_client_id",
            field=models.CharField(blank=True, max_length=255, verbose_name="ORCID client ID"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="oauth_orcid_client_secret",
            field=models.CharField(blank=True, max_length=255, verbose_name="ORCID client secret"),
        ),
        migrations.CreateModel(
            name="IdentidadeExternaComentario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("orcid", "ORCID"), ("github", "GitHub"), ("gitlab", "GitLab")], db_index=True, max_length=20, verbose_name="Provedor")),
                ("provider_user_id", models.CharField(db_index=True, max_length=255, verbose_name="ID do usuário no provedor")),
                ("provider_username", models.CharField(blank=True, max_length=255, verbose_name="Nome no provedor")),
                ("nome_exibicao", models.CharField(blank=True, max_length=255, verbose_name="Nome exibido pelo provedor")),
                ("email_externo", models.EmailField(blank=True, max_length=254, verbose_name="E-mail do provedor")),
                ("email_verificado", models.BooleanField(default=False, verbose_name="E-mail verificado no provedor")),
                ("perfil_url", models.URLField(blank=True, verbose_name="URL do perfil")),
                ("avatar_url", models.URLField(blank=True, verbose_name="URL do avatar")),
                ("escopos", models.CharField(blank=True, max_length=500, verbose_name="Escopos")),
                ("payload", models.JSONField(blank=True, default=dict, verbose_name="Payload")),
                ("vinculado_em", models.DateTimeField(auto_now_add=True, verbose_name="Vinculado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="identidades_externas", to="conteudo.usuariocomentario", verbose_name="Usuário")),
            ],
            options={
                "verbose_name": "Identidade externa de comentário",
                "verbose_name_plural": "Identidades externas de comentários",
                "ordering": ["-atualizado_em", "-vinculado_em"],
            },
        ),
        migrations.AddConstraint(
            model_name="identidadeexternacomentario",
            constraint=models.UniqueConstraint(fields=("provider", "provider_user_id"), name="unique_provider_identity_comment"),
        ),
    ]
