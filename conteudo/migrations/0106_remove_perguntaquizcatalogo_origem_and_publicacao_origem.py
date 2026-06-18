from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0105_remove_quizopcaoperguntapublicacao_pergunta_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="perguntaquizcatalogo",
            name="origem",
        ),
        migrations.RemoveField(
            model_name="perguntaquizcatalogo",
            name="publicacao_origem",
        ),
    ]
