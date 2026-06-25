# Generated manually for OwnPaper menu standard configuration.

from django.db import migrations, models


ATALHO_CHOICES = [
    ("home", "Início"),
    ("categorias", "Categorias"),
    ("tags", "Tags"),
    ("autores", "Autores"),
    ("busca", "Busca"),
    ("destaques", "Âncora: Destaques"),
    ("ultimas", "Âncora: Últimas publicações"),
    ("contato", "Contato"),
    ("newsletter", "Newsletter"),
    ("indexador", "Indexador"),
    ("quiz", "Quiz"),
    ("sobre", "Sobre"),
    ("apoio", "Apoie"),
    ("privacidade", "Privacidade"),
    ("cookies", "Cookies"),
    ("rss", "RSS"),
]


MENU_PADRAO_FIELDS = [
    ("categorias", "Categorias", True),
    ("autores", "Autores", True),
    ("tags", "Tags", True),
    ("busca", "Busca", True),
    ("destaques", "Destaques", True),
    ("ultimas", "Últimas publicações", True),
    ("contato", "Contato", True),
    ("sobre", "Sobre", True),
    ("newsletter", "Newsletter", True),
    ("indexador", "Indexador", True),
    ("quiz", "Quiz", True),
    ("apoio", "Apoie", True),
    ("privacidade", "Privacidade", False),
    ("cookies", "Cookies", False),
    ("rss", "RSS", False),
]


def menu_padrao_add_fields():
    operations = []
    for key, label, active_default in MENU_PADRAO_FIELDS:
        operations.append(
            migrations.AddField(
                model_name="configuracaosite",
                name=f"menu_padrao_{key}_ativo",
                field=models.BooleanField(
                    default=active_default,
                    verbose_name=f"Exibir {label} no menu padrão",
                ),
            )
        )
        operations.append(
            migrations.AddField(
                model_name="configuracaosite",
                name=f"menu_padrao_{key}_rotulo",
                field=models.CharField(
                    blank=True,
                    default=label,
                    max_length=120,
                    verbose_name=f"Rótulo de {label}",
                ),
            )
        )
    return operations


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0140_alter_doacoes_rotulo_default_apoie"),
    ]

    operations = [
        *menu_padrao_add_fields(),
        migrations.AlterField(
            model_name="menuprincipalgrupo",
            name="atalho",
            field=models.CharField(blank=True, choices=ATALHO_CHOICES, max_length=30, verbose_name="Atalho do site"),
        ),
        migrations.AlterField(
            model_name="menuprincipalsubitem",
            name="atalho",
            field=models.CharField(blank=True, choices=ATALHO_CHOICES, max_length=30, verbose_name="Atalho do site"),
        ),
        migrations.AlterField(
            model_name="rodapelink",
            name="atalho",
            field=models.CharField(blank=True, choices=ATALHO_CHOICES, max_length=30, verbose_name="Atalho do site"),
        ),
    ]
