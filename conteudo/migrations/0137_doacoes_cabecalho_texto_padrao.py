from django.db import migrations, models
import wagtail.fields


DOACOES_DESCRICAO_PADRAO = (
    "<p>Se este projeto é útil para você, considere contribuir para manter "
    "a publicação independente, a infraestrutura técnica e o desenvolvimento "
    "de novos recursos. Todo apoio ajuda a sustentar o trabalho editorial e "
    "a continuidade do site.</p>"
)


def preencher_descricao_vazia(apps, schema_editor):
    ConfiguracaoSite = apps.get_model("conteudo", "ConfiguracaoSite")
    ConfiguracaoSite.objects.filter(doacoes_descricao="").update(doacoes_descricao=DOACOES_DESCRICAO_PADRAO)


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0136_doacoes_metodos_estruturados"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosite",
            name="doacoes_exibir_no_cabecalho",
            field=models.BooleanField(default=True, verbose_name="Exibir link de apoio no cabeçalho"),
        ),
        migrations.AlterField(
            model_name="configuracaosite",
            name="doacoes_descricao",
            field=wagtail.fields.RichTextField(blank=True, default=DOACOES_DESCRICAO_PADRAO, features=["bold", "italic", "link", "ol", "ul"], verbose_name="Descrição da página de apoio"),
        ),
        migrations.AlterField(
            model_name="configuracaosite",
            name="doacoes_rotulo",
            field=models.CharField(blank=True, default="Apoio", max_length=120, verbose_name="Rótulo do botão/link de apoio"),
        ),
        migrations.RunPython(preencher_descricao_vazia, migrations.RunPython.noop),
    ]
