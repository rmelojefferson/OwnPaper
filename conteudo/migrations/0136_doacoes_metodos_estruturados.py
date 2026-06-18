from django.db import migrations, models
import django.db.models.deletion


def ativar_pix_existente(apps, schema_editor):
    ConfiguracaoSite = apps.get_model("conteudo", "ConfiguracaoSite")
    ConfiguracaoSite.objects.exclude(doacoes_pix_chave="").update(doacoes_pix_ativo=True)


class Migration(migrations.Migration):

    dependencies = [
        ("wagtailimages", "0027_image_description"),
        ("conteudo", "0135_remove_webdav_panel_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_apoiase_ativo",
            field=models.BooleanField(default=False, verbose_name="Ativar Apoia.se"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_apoiase_url",
            field=models.URLField(blank=True, verbose_name="URL do Apoia.se"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_bitcoin_ativo",
            field=models.BooleanField(default=False, verbose_name="Ativar Bitcoin"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_bitcoin_endereco",
            field=models.CharField(blank=True, max_length=255, verbose_name="Endereço Bitcoin"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_buymeacoffee_ativo",
            field=models.BooleanField(default=False, verbose_name="Ativar Buy Me a Coffee"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_buymeacoffee_usuario",
            field=models.CharField(blank=True, help_text="Informe apenas o usuário/slug, sem URL.", max_length=120, verbose_name="Usuário Buy Me a Coffee"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_ethereum_ativo",
            field=models.BooleanField(default=False, verbose_name="Ativar Ethereum"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_ethereum_endereco",
            field=models.CharField(blank=True, max_length=255, verbose_name="Endereço Ethereum"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_github_sponsors_ativo",
            field=models.BooleanField(default=False, verbose_name="Ativar GitHub Sponsors"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_github_sponsors_usuario",
            field=models.CharField(blank=True, help_text="Informe apenas o usuário ou organização, sem URL.", max_length=120, verbose_name="Usuário/organização GitHub Sponsors"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_mercadopago_ativo",
            field=models.BooleanField(default=False, verbose_name="Ativar Mercado Pago"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_mercadopago_url",
            field=models.URLField(blank=True, help_text="Link público de pagamento, checkout ou preferência já criada no Mercado Pago.", verbose_name="URL do Mercado Pago"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_paypal_ativo",
            field=models.BooleanField(default=False, verbose_name="Ativar PayPal"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_paypal_business",
            field=models.CharField(blank=True, help_text="E-mail ou payer ID, usado apenas se não houver hosted_button_id.", max_length=255, verbose_name="PayPal business"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_paypal_hosted_button_id",
            field=models.CharField(blank=True, help_text="ID público do botão de doação criado no PayPal.", max_length=120, verbose_name="PayPal hosted_button_id"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_paypal_url",
            field=models.URLField(blank=True, verbose_name="URL PayPal alternativa"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_pix_ativo",
            field=models.BooleanField(default=False, verbose_name="Ativar Pix"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_pix_copia_cola",
            field=models.TextField(blank=True, help_text="Payload EMV do QR Code Pix, quando houver.", verbose_name="Pix copia e cola"),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_pix_qr_code",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="wagtailimages.image", verbose_name="QR Code Pix"),
        ),
        migrations.AlterField(
            model_name="configuracaosite",
            name="doacoes_link_externo",
            field=models.URLField(blank=True, verbose_name="Link externo complementar"),
        ),
        migrations.RunPython(ativar_pix_existente, migrations.RunPython.noop),
    ]
