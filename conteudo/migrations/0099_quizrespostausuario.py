from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0098_quizacessocodigo_quizsessaousuario_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuizRespostaUsuario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ultima_correta", models.BooleanField(blank=True, null=True, verbose_name="Última resposta correta")),
                ("selecionadas", models.JSONField(blank=True, default=list, verbose_name="Índices selecionados")),
                ("ultima_respondida_em", models.DateTimeField(auto_now=True, verbose_name="Última resposta em")),
                ("pergunta_catalogo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="respostas_usuario", to="conteudo.perguntaquizcatalogo", verbose_name="Pergunta de catálogo")),
                ("pergunta_publicacao", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="respostas_usuario", to="conteudo.quizperguntapublicacao", verbose_name="Pergunta de publicação")),
                ("publicacao", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="quiz_respostas_usuario", to="conteudo.publicacaopage", verbose_name="Publicação")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quiz_respostas", to="conteudo.usuariocomentario", verbose_name="Usuário")),
            ],
            options={
                "verbose_name": "Resposta de quiz do usuário",
                "verbose_name_plural": "Respostas de quiz dos usuários",
                "ordering": ["-ultima_respondida_em"],
            },
        ),
        migrations.AddConstraint(
            model_name="quizrespostausuario",
            constraint=models.UniqueConstraint(fields=("usuario", "pergunta_publicacao"), name="unique_quiz_resposta_usuario_pergunta_publicacao"),
        ),
        migrations.AddConstraint(
            model_name="quizrespostausuario",
            constraint=models.UniqueConstraint(fields=("usuario", "pergunta_catalogo"), name="unique_quiz_resposta_usuario_pergunta_catalogo"),
        ),
    ]
