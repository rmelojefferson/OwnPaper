from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0129_backups_externos_analytics_presets"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="configuracaosite",
            name="backup_anexar_limite_mb",
        ),
        migrations.RemoveField(
            model_name="configuracaosite",
            name="backup_periodo_horas",
        ),
        migrations.RemoveField(
            model_name="configuracaosite",
            name="backup_reter_dias",
        ),
        migrations.RemoveField(
            model_name="configuracaosite",
            name="backup_destino_externo",
        ),
        migrations.RemoveField(
            model_name="configuracaosite",
            name="backup_webdav_url",
        ),
        migrations.RemoveField(
            model_name="configuracaosite",
            name="backup_webdav_username",
        ),
        migrations.RemoveField(
            model_name="configuracaosite",
            name="backup_webdav_password_env",
        ),
    ]
