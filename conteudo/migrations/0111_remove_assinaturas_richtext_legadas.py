from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0110_vincular_autor_para_revisores_existentes"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="configuracaosite",
            name="assinatura_email_padrao",
        ),
        migrations.RemoveField(
            model_name="usuariopainelperfil",
            name="assinatura_email",
        ),
    ]
