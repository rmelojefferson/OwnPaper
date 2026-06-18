from django.db import migrations, models
import django.db.models.deletion


def migrar_taxonomia_quiz_para_editorial(apps, schema_editor):
    Categoria = apps.get_model("conteudo", "Categoria")
    TagPublicacao = apps.get_model("conteudo", "TagPublicacao")
    PerguntaQuizCatalogo = apps.get_model("conteudo", "PerguntaQuizCatalogo")
    PerguntaQuizCatalogoTag = apps.get_model("conteudo", "PerguntaQuizCatalogoTag")

    through = PerguntaQuizCatalogo.tags_editoriais.through

    for pergunta in PerguntaQuizCatalogo.objects.select_related("tema").all():
        if pergunta.tema_id and not pergunta.categoria_editorial_id:
            categoria, _ = Categoria.objects.get_or_create(
                slug=pergunta.tema.slug,
                defaults={"nome": pergunta.tema.nome, "descricao": pergunta.tema.descricao or ""},
            )
            pergunta.categoria_editorial = categoria
            pergunta.save(update_fields=["categoria_editorial"])

        old_tag_ids = PerguntaQuizCatalogoTag.objects.filter(
            content_object_id=pergunta.id
        ).values_list("tag_id", flat=True)
        for old_tag in apps.get_model("conteudo", "TagPerguntaQuiz").objects.filter(id__in=old_tag_ids):
            tag_publicacao, _ = TagPublicacao.objects.get_or_create(
                slug=old_tag.slug,
                defaults={"name": old_tag.name},
            )
            through.objects.get_or_create(
                perguntaquizcatalogo_id=pergunta.id,
                tagpublicacao_id=tag_publicacao.id,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0100_temaperguntaquiz_categoria_publicacao_relacionada_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="perguntaquizcatalogo",
            name="categoria_editorial",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="perguntas_quiz_editoriais", to="conteudo.categoria", verbose_name="Tema editorial"),
        ),
        migrations.AddField(
            model_name="perguntaquizcatalogo",
            name="tags_editoriais",
            field=models.ManyToManyField(blank=True, related_name="_perguntaquizcatalogo_tags_editoriais_+", to="conteudo.tagpublicacao", verbose_name="Tags editoriais"),
        ),
        migrations.RunPython(migrar_taxonomia_quiz_para_editorial, migrations.RunPython.noop),
    ]
