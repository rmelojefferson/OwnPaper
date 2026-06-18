from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0125_auditlog_hash_chain"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuariopainelperfil",
            name="aceitou_termos_painel_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Aceitou os termos do painel em"),
        ),
        migrations.AddField(
            model_name="usuariopainelperfil",
            name="aceitou_termos_painel_ip",
            field=models.CharField(blank=True, max_length=64, verbose_name="IP do aceite dos termos do painel"),
        ),
        migrations.AddField(
            model_name="usuariopainelperfil",
            name="aceitou_termos_painel_user_agent",
            field=models.CharField(blank=True, max_length=255, verbose_name="User-Agent do aceite dos termos do painel"),
        ),
        migrations.AddField(
            model_name="usuariopainelperfil",
            name="termos_painel_versao",
            field=models.CharField(blank=True, db_index=True, max_length=40, verbose_name="Versão dos termos do painel aceita"),
        ),
    ]
