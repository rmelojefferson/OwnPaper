from django.db import migrations


def migrar_taxonomia_legada_quiz(apps, schema_editor):
    Categoria = apps.get_model("conteudo", "Categoria")
    TagPublicacao = apps.get_model("conteudo", "TagPublicacao")
    TemaPerguntaQuiz = apps.get_model("conteudo", "TemaPerguntaQuiz")
    TagPerguntaQuiz = apps.get_model("conteudo", "TagPerguntaQuiz")
    PerguntaQuizCatalogo = apps.get_model("conteudo", "PerguntaQuizCatalogo")
    PerguntaQuizCatalogoTag = apps.get_model("conteudo", "PerguntaQuizCatalogoTag")
    through_editorial = PerguntaQuizCatalogo.tags_editoriais.through

    for pergunta in PerguntaQuizCatalogo.objects.all().iterator():
        atualizar = []
        if not pergunta.categoria_editorial_id and pergunta.tema_id:
            tema = TemaPerguntaQuiz.objects.filter(id=pergunta.tema_id).first()
            categoria = None
            if tema and tema.categoria_publicacao_relacionada_id:
                categoria = Categoria.objects.filter(
                    id=tema.categoria_publicacao_relacionada_id
                ).first()
            if categoria:
                pergunta.categoria_editorial_id = categoria.id
                atualizar.append("categoria_editorial")

        if atualizar:
            pergunta.save(update_fields=atualizar)

        old_tag_ids = list(
            PerguntaQuizCatalogoTag.objects.filter(content_object_id=pergunta.id)
            .values_list("tag_id", flat=True)
        )
        if not old_tag_ids:
            continue

        editorial_ids_atuais = set(
            through_editorial.objects.filter(perguntaquizcatalogo_id=pergunta.id)
            .values_list("tagpublicacao_id", flat=True)
        )
        for old_tag in TagPerguntaQuiz.objects.filter(id__in=old_tag_ids):
            if not old_tag.tag_publicacao_relacionada_id:
                continue
            if old_tag.tag_publicacao_relacionada_id in editorial_ids_atuais:
                continue
            if not TagPublicacao.objects.filter(id=old_tag.tag_publicacao_relacionada_id).exists():
                continue
            through_editorial.objects.create(
                perguntaquizcatalogo_id=pergunta.id,
                tagpublicacao_id=old_tag.tag_publicacao_relacionada_id,
            )
            editorial_ids_atuais.add(old_tag.tag_publicacao_relacionada_id)


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0101_perguntaquizcatalogo_categoria_editorial_and_more"),
    ]

    operations = [
        migrations.RunPython(migrar_taxonomia_legada_quiz, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="quizperguntapublicacao",
            name="tags",
        ),
        migrations.RemoveField(
            model_name="quizperguntapublicacao",
            name="tema",
        ),
        migrations.RemoveField(
            model_name="perguntaquizcatalogo",
            name="tags",
        ),
        migrations.RemoveField(
            model_name="perguntaquizcatalogo",
            name="tema",
        ),
        migrations.DeleteModel(
            name="PerguntaQuizCatalogoTag",
        ),
        migrations.DeleteModel(
            name="TagPerguntaQuiz",
        ),
        migrations.DeleteModel(
            name="TemaPerguntaQuiz",
        ),
    ]
