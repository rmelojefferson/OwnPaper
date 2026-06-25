# Generated manually for OwnPaper footer standard configuration.

from django.db import migrations, models


RODAPE_PADRAO_FIELDS = [
    ("contato", "Contato", True),
    ("sobre", "Sobre", True),
    ("privacidade", "Privacidade", True),
    ("cookies", "Cookies", True),
    ("newsletter", "Newsletter", True),
    ("indexador", "Indexador", True),
    ("quiz", "Quiz", True),
]

RODAPE_LABELS = {
    "privacidade": "Privacidade e dados",
}


def rodape_padrao_add_fields():
    operations = []
    for key, label, active_default in RODAPE_PADRAO_FIELDS:
        operations.append(
            migrations.AddField(
                model_name="configuracaosite",
                name=f"rodape_padrao_{key}_ativo",
                field=models.BooleanField(
                    default=active_default,
                    verbose_name=f"Exibir {label} no rodapé padrão",
                ),
            )
        )
        operations.append(
            migrations.AddField(
                model_name="configuracaosite",
                name=f"rodape_padrao_{key}_rotulo",
                field=models.CharField(
                    blank=True,
                    default=RODAPE_LABELS.get(key, label),
                    max_length=120,
                    verbose_name=f"Rótulo de {label} no rodapé",
                ),
            )
        )
    return operations


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0141_menu_padrao_configuravel"),
    ]

    operations = [
        *rodape_padrao_add_fields(),
    ]
