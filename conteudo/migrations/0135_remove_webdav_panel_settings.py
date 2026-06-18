# Generated manually for OwnPaper: remove panel-managed WebDAV settings.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0134_configuracaosite_submissoes_exigir_orcid_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="configuracaosite",
            name="backup_webdav_painel_ativo",
        ),
        migrations.RemoveField(
            model_name="configuracaosite",
            name="backup_webdav_painel_url",
        ),
        migrations.RemoveField(
            model_name="configuracaosite",
            name="backup_webdav_painel_username",
        ),
        migrations.RemoveField(
            model_name="configuracaosite",
            name="backup_webdav_painel_password_encrypted",
        ),
        migrations.RemoveField(
            model_name="configuracaosite",
            name="backup_webdav_painel_reter_dias",
        ),
        migrations.RemoveField(
            model_name="configuracaosite",
            name="backup_webdav_painel_ultimo_teste",
        ),
        migrations.RemoveField(
            model_name="configuracaosite",
            name="backup_webdav_painel_ultimo_teste_em",
        ),
    ]
