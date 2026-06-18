from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0064_configuracaosite_backups_backupexecucao"),
    ]

    operations = [
        migrations.CreateModel(
            name="DisparoEmailDestino",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(db_index=True, max_length=254, verbose_name="E-mail")),
                ("status", models.CharField(choices=[("pendente", "Pendente"), ("enviado", "Enviado"), ("falhou", "Falhou")], db_index=True, default="pendente", max_length=20, verbose_name="Status")),
                ("erro", models.TextField(blank=True, verbose_name="Erro")),
                ("enviado_em", models.DateTimeField(blank=True, null=True, verbose_name="Enviado em")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("disparo", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="destinos", to="conteudo.disparoemail", verbose_name="Disparo")),
            ],
            options={
                "verbose_name": "Destino do disparo de e-mail",
                "verbose_name_plural": "Destinos dos disparos de e-mail",
                "ordering": ["id"],
            },
        ),
    ]
