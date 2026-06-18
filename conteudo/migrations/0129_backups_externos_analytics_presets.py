from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0128_alter_estatisticadiariasite_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_destino_externo",
            field=models.CharField(
                choices=[
                    ("local", "Apenas local"),
                    ("email", "E-mail com anexo quando couber"),
                    ("webdav", "WebDAV externo"),
                ],
                default="local",
                help_text="Use e-mail apenas para backups pequenos; para externo persistente, prefira WebDAV.",
                max_length=20,
                verbose_name="Destino externo do backup",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_webdav_password_env",
            field=models.CharField(
                blank=True,
                default="OWNPAPER_BACKUP_WEBDAV_PASSWORD",
                help_text="A senha não é salva no painel. Configure esta variável no ambiente do servidor.",
                max_length=120,
                verbose_name="Variável de ambiente da senha WebDAV",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_webdav_url",
            field=models.URLField(
                blank=True,
                help_text="Exemplo: https://backup.example.com/ownpaper/. O ZIP será enviado para esta pasta.",
                verbose_name="URL WebDAV de destino",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_webdav_username",
            field=models.CharField(blank=True, max_length=255, verbose_name="Usuário WebDAV"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="matomo_site_id",
            field=models.CharField(
                blank=True,
                help_text="ID numérico do site no Matomo. Deixe vazio para desativar.",
                max_length=40,
                verbose_name="Matomo - Site ID",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="matomo_url",
            field=models.URLField(
                blank=True,
                help_text="Exemplo: https://matomo.example.com/.",
                verbose_name="Matomo - URL base",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="plausible_domain",
            field=models.CharField(
                blank=True,
                help_text="Exemplo: exemplo.com. Deixe vazio para desativar.",
                max_length=255,
                verbose_name="Plausible - domínio do site",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="plausible_script_url",
            field=models.URLField(
                blank=True,
                default="https://plausible.io/js/script.js",
                help_text="Use a URL oficial ou da sua instância Plausible self-hosted.",
                verbose_name="Plausible - URL do script",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="umami_script_url",
            field=models.URLField(
                blank=True,
                help_text="Exemplo: https://analytics.example.com/script.js.",
                verbose_name="Umami - URL do script",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="umami_website_id",
            field=models.CharField(
                blank=True,
                help_text="ID do site no Umami. Deixe vazio para desativar.",
                max_length=120,
                verbose_name="Umami - Website ID",
            ),
        ),
    ]
