from django.conf import settings
from django.db import migrations
from django.utils import timezone
from django.utils.text import slugify


AUTHOR_GROUP_NAME = "Autores / Escritores"
REVIEWER_GROUP_NAME = "Revisores"
CONTACT_OPERATORS_GROUP_NAME = "Operadores / Atendimento"


def _nome_usuario(user):
    nome = " ".join(
        [
            (getattr(user, "first_name", "") or "").strip(),
            (getattr(user, "last_name", "") or "").strip(),
        ]
    ).strip()
    return nome or (getattr(user, "username", "") or "").strip() or f"usuario-{user.pk}"


def _username_autor_unico(Autor, base, user_id):
    candidato_base = slugify(base or "") or f"usuario-{user_id}"
    candidato = candidato_base
    indice = 2
    while Autor.objects.filter(username=candidato).exists():
        candidato = f"{candidato_base}-{indice}"
        indice += 1
    return candidato


def popular_fluxo_editorial_e_papeis(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Categoria = apps.get_model("conteudo", "Categoria")
    TagPublicacao = apps.get_model("conteudo", "TagPublicacao")
    PerguntaQuizCatalogo = apps.get_model("conteudo", "PerguntaQuizCatalogo")
    PublicacaoPage = apps.get_model("conteudo", "PublicacaoPage")
    UsuarioPainelPerfil = apps.get_model("conteudo", "UsuarioPainelPerfil")
    Autor = apps.get_model("conteudo", "Autor")

    author_group, _ = Group.objects.get_or_create(name=AUTHOR_GROUP_NAME)
    Group.objects.get_or_create(name=REVIEWER_GROUP_NAME)
    Group.objects.get_or_create(name=CONTACT_OPERATORS_GROUP_NAME)

    now = timezone.now()

    Categoria.objects.filter(aprovacao_status="pendente").update(
        aprovacao_status="aprovado",
        aprovado_em=now,
    )
    TagPublicacao.objects.filter(aprovacao_status="pendente").update(
        aprovacao_status="aprovado",
        aprovado_em=now,
    )
    PerguntaQuizCatalogo.objects.filter(aprovacao_status="pendente").update(
        aprovacao_status="aprovado",
        aprovado_em=now,
    )

    for publicacao in PublicacaoPage.objects.all():
        if getattr(publicacao, "live", False):
            if publicacao.status_editorial != "publicado":
                publicacao.status_editorial = "publicado"
            if not publicacao.publicado_em:
                publicacao.publicado_em = (
                    getattr(publicacao, "last_published_at", None)
                    or getattr(publicacao, "first_published_at", None)
                    or now
                )
            publicacao.save(update_fields=["status_editorial", "publicado_em"])

    for user in User.objects.filter(is_active=True):
        group_names = set(user.groups.values_list("name", flat=True))
        papel_admin = bool(user.is_superuser and user.is_staff)
        papel_autor = papel_admin or AUTHOR_GROUP_NAME in group_names or Autor.objects.filter(usuario_admin_id=user.pk).exists()
        papel_revisor = REVIEWER_GROUP_NAME in group_names
        papel_operacao = CONTACT_OPERATORS_GROUP_NAME in group_names

        if papel_admin:
            user.groups.add(author_group)
            papel_autor = True

        if papel_autor and not Autor.objects.filter(usuario_admin_id=user.pk).exists():
            nome = _nome_usuario(user)
            username_autor = _username_autor_unico(
                Autor,
                getattr(user, "username", "") or nome,
                user.pk,
            )
            Autor.objects.create(
                nome_completo=nome,
                nome_exibicao=nome,
                username=username_autor,
                usuario_admin_id=user.pk,
                email=(getattr(user, "email", "") or "").strip(),
            )

        if papel_admin or papel_autor or papel_revisor or papel_operacao:
            UsuarioPainelPerfil.objects.get_or_create(
                usuario_id=user.pk,
                defaults={"pode_publicar_direto": bool(papel_admin)},
            )


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0108_remove_conviteusuario_tipo_perfil_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(popular_fluxo_editorial_e_papeis, migrations.RunPython.noop),
    ]
