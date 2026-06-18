# Generated manually for OwnPaper backup WebDAV panel settings.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0131_alter_backupexecucao_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_webdav_painel_ativo",
            field=models.BooleanField(default=False, verbose_name="Ativar WebDAV externo pelo painel"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_webdav_painel_url",
            field=models.URLField(blank=True, help_text="Use HTTPS e uma pasta exclusiva para backups do OwnPaper.", verbose_name="URL WebDAV"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_webdav_painel_username",
            field=models.CharField(blank=True, max_length=255, verbose_name="Usuário WebDAV"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_webdav_painel_password_encrypted",
            field=models.TextField(blank=True, editable=False, verbose_name="Senha WebDAV criptografada"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_webdav_painel_reter_dias",
            field=models.PositiveIntegerField(default=90, verbose_name="Retenção remota sugerida (dias)"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_webdav_painel_ultimo_teste",
            field=models.JSONField(blank=True, default=dict, verbose_name="Último teste WebDAV"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="backup_webdav_painel_ultimo_teste_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Último teste WebDAV em"),
        ),
    ]
