# Generated manually for OwnPaper advanced verification and analytics controls.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0143_plausible_direto_ip_dinamico_estatisticas"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosite",
            name="verificacao_head_html",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Use apenas códigos de verificação fornecidos por serviços confiáveis. "
                    "Este conteúdo é inserido no head do site público sem depender de cookies."
                ),
                verbose_name="HTML avançado de verificação no head",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="verificacao_arquivo_nome",
            field=models.CharField(
                blank=True,
                help_text="Exemplo: google1234567890abcdef.html ou verificacao.txt.",
                max_length=120,
                verbose_name="Nome do arquivo de verificação",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="verificacao_arquivo_conteudo",
            field=models.TextField(
                blank=True,
                help_text="Cole aqui o conteúdo integral do arquivo solicitado pelo provedor.",
                verbose_name="Conteúdo do arquivo de verificação",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosite",
            name="plausible_sem_consentimento_ativo",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Use somente quando a configuração do Plausible estiver sem cookies e adequada "
                    "à política de privacidade do projeto."
                ),
                verbose_name="Carregar Plausible sem aceite de cookies opcionais",
            ),
        ),
    ]
