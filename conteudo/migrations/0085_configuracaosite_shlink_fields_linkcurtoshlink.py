from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0084_autor_mastodon"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosite",
            name="shlink_ativo",
            field=models.BooleanField(default=False, verbose_name="Ativar encurtamento com Shlink"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="shlink_api_key",
            field=models.CharField(blank=True, max_length=255, verbose_name="API key do Shlink"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="shlink_base_url",
            field=models.URLField(blank=True, help_text="Ex.: https://s.seudominio.com", verbose_name="URL base do Shlink"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="shlink_default_domain",
            field=models.CharField(blank=True, help_text="Opcional. Use quando a instância trabalha com múltiplos domínios curtos.", max_length=255, verbose_name="Domínio padrão do Shlink"),
        ),
        migrations.CreateModel(
            name="LinkCurtoShlink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("contexto", models.CharField(choices=[("publicacao", "Publicação"), ("email", "E-mail"), ("manual", "Manual")], default="manual", max_length=20, verbose_name="Contexto")),
                ("canal", models.CharField(choices=[("whatsapp", "WhatsApp"), ("telegram", "Telegram"), ("linkedin", "LinkedIn"), ("mastodon", "Mastodon"), ("bluesky", "Bluesky"), ("x", "X"), ("email", "E-mail"), ("copia", "Cópia"), ("manual", "Manual")], default="manual", max_length=30, verbose_name="Canal")),
                ("titulo", models.CharField(blank=True, max_length=255, verbose_name="Título")),
                ("long_url", models.URLField(max_length=2048, verbose_name="URL original")),
                ("short_url", models.URLField(blank=True, max_length=1024, verbose_name="URL curta")),
                ("short_code", models.CharField(blank=True, max_length=255, verbose_name="Short code")),
                ("dominio", models.CharField(blank=True, max_length=255, verbose_name="Domínio curto")),
                ("slug_customizado", models.CharField(blank=True, max_length=255, verbose_name="Slug customizado")),
                ("tags", models.JSONField(blank=True, default=list, verbose_name="Tags")),
                ("visits_total", models.PositiveIntegerField(default=0, verbose_name="Visitas totais")),
                ("visits_non_bots", models.PositiveIntegerField(default=0, verbose_name="Visitas humanas")),
                ("visits_bots", models.PositiveIntegerField(default=0, verbose_name="Visitas de bots")),
                ("ultimo_sync_em", models.DateTimeField(blank=True, null=True, verbose_name="Última sincronização")),
                ("ultimo_erro", models.TextField(blank=True, verbose_name="Último erro")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                ("publicacao", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="links_curtos_shlink", to="conteudo.publicacaopage", verbose_name="Publicação")),
            ],
            options={
                "verbose_name": "Link curto do Shlink",
                "verbose_name_plural": "Links curtos do Shlink",
                "ordering": ["-atualizado_em", "-criado_em"],
            },
        ),
    ]
