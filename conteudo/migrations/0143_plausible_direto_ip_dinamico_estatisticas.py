# Generated manually for OwnPaper analytics configuration.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0142_rodape_padrao_configuravel"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosite",
            name="plausible_script_direto_ativo",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Ative quando o Plausible fornecer apenas um script próprio, sem data-domain. "
                    "O OwnPaper renderiza apenas o snippet seguro predefinido."
                ),
                verbose_name="Usar snippet novo do Plausible sem domínio",
            ),
        ),
        migrations.CreateModel(
            name="IpDinamicoIgnoradoEstatisticas",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.SlugField(db_index=True, default="rede-local", max_length=80, verbose_name="Nome")),
                ("ip", models.GenericIPAddressField(db_index=True, verbose_name="IP público")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                ("expira_em", models.DateTimeField(db_index=True, verbose_name="Expira em")),
            ],
            options={
                "verbose_name": "IP dinâmico ignorado nas estatísticas",
                "verbose_name_plural": "IPs dinâmicos ignorados nas estatísticas",
                "ordering": ["nome"],
            },
        ),
    ]
