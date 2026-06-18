from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0117_comentarios_revisao_publicacao"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicacaocomentariorevisao",
            name="contexto_antes",
            field=models.TextField(blank=True, verbose_name="Contexto anterior"),
        ),
        migrations.AddField(
            model_name="publicacaocomentariorevisao",
            name="contexto_depois",
            field=models.TextField(blank=True, verbose_name="Contexto posterior"),
        ),
        migrations.AddField(
            model_name="publicacaocomentariorevisao",
            name="sugestao",
            field=models.TextField(blank=True, verbose_name="Sugestão de alteração"),
        ),
    ]
