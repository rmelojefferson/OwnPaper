from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0093_configuracaosite_oauth_codeberg_base_url_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="quizperguntapublicacao",
            name="traducoes",
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
        migrations.AddField(
            model_name="quizopcaoperguntapublicacao",
            name="traducoes",
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
    ]
