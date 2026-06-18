from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0099_quizrespostausuario"),
    ]

    operations = [
        migrations.AddField(
            model_name="tagperguntaquiz",
            name="tag_publicacao_relacionada",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tags_quiz_relacionadas", to="conteudo.tagpublicacao", verbose_name="Tag editorial relacionada"),
        ),
        migrations.AddField(
            model_name="temaperguntaquiz",
            name="categoria_publicacao_relacionada",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="temas_quiz_relacionados", to="conteudo.categoria", verbose_name="Categoria editorial relacionada"),
        ),
    ]
