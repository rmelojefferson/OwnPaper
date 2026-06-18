from django.contrib.auth.models import Permission
from wagtail.models import GroupPagePermission

from .models import Autor, ConviteUsuario, PublicacoesIndexPage, UsuarioPainelPerfil
from .roles import (
    AUTHOR_GROUP_NAME,
    CONTACT_OPERATORS_GROUP_NAME,
    REVIEWER_GROUP_NAME,
    ensure_role_groups,
    ensure_staff_group,
)


def gerar_slug_autor_unico(base_texto):
    from django.utils.text import slugify

    base_slug = slugify(base_texto)[:70] or "autor"
    slug = base_slug
    contador = 2
    while Autor.objects.filter(username=slug).exists():
        sufixo = f"-{contador}"
        slug = f"{base_slug[:80 - len(sufixo)]}{sufixo}"
        contador += 1
    return slug


def vincular_autor_para_usuario(usuario, email="", username_sugerido="", nome=""):
    autor = Autor.objects.filter(
        email__iexact=email,
        usuario_admin__isnull=True,
    ).first()

    if autor:
        autor.usuario_admin = usuario
        if not autor.nome_completo and nome:
            autor.nome_completo = nome
        autor.save()
        return autor

    slug_autor = gerar_slug_autor_unico(username_sugerido or usuario.username)
    return Autor.objects.create(
        nome_completo=nome or usuario.username,
        nome_exibicao=nome or usuario.username,
        username=slug_autor,
        email=email,
        usuario_admin=usuario,
    )


def garantir_permissoes_editoriais_grupo_autor(grupo):
    if not grupo:
        return

    permissoes = Permission.objects.filter(
        content_type__app_label="wagtailcore",
        content_type__model="page",
        codename__in=["add_page", "change_page", "delete_page"],
    )
    permissoes_map = {perm.codename: perm for perm in permissoes}
    pastas_publicacoes = list(PublicacoesIndexPage.objects.all())
    if not pastas_publicacoes:
        return

    for pasta in pastas_publicacoes:
        for codename in ["add_page", "change_page", "delete_page"]:
            permissao = permissoes_map.get(codename)
            if permissao:
                GroupPagePermission.objects.get_or_create(
                    group=grupo,
                    page=pasta,
                    permission=permissao,
                )


def aplicar_papeis_usuario(
    usuario,
    *,
    papel_admin=False,
    papel_autor=False,
    papel_revisor=False,
    papel_operacao=False,
    pode_publicar_direto=False,
    email_monitoramento_respostas="",
    vincular_autor=True,
):
    ensure_role_groups()

    papel_autor = bool(papel_autor or papel_admin)
    usuario.is_staff = bool(papel_admin or papel_autor or papel_revisor or papel_operacao)
    usuario.is_superuser = bool(papel_admin)
    usuario.save()

    grupos = []
    if papel_autor:
        grupo_autor = ensure_staff_group(AUTHOR_GROUP_NAME)
        garantir_permissoes_editoriais_grupo_autor(grupo_autor)
        grupos.append(grupo_autor)
    if papel_revisor:
        grupos.append(ensure_staff_group(REVIEWER_GROUP_NAME))
    if papel_operacao:
        grupos.append(ensure_staff_group(CONTACT_OPERATORS_GROUP_NAME))
    usuario.groups.set(grupos)

    perfil, _ = UsuarioPainelPerfil.objects.get_or_create(usuario=usuario)
    perfil.pode_publicar_direto = bool(pode_publicar_direto)
    if email_monitoramento_respostas is not None:
        perfil.email_monitoramento_respostas = email_monitoramento_respostas
    perfil.save()

    if vincular_autor and (papel_autor or papel_revisor) and not getattr(usuario, "autor_vinculado", None):
        vincular_autor_para_usuario(
            usuario,
            email=(usuario.email or "").strip(),
            username_sugerido=usuario.username,
            nome=usuario.first_name or usuario.username,
        )

    return perfil


def aplicar_papeis_por_convite(usuario, convite: ConviteUsuario, nome=""):
    perfil = aplicar_papeis_usuario(
        usuario,
        papel_admin=convite.papel_admin,
        papel_autor=convite.papel_autor,
        papel_revisor=convite.papel_revisor,
        papel_operacao=convite.papel_operacao,
        pode_publicar_direto=convite.pode_publicar_direto,
        vincular_autor=(convite.papel_admin or convite.papel_autor or convite.papel_revisor),
    )
    if convite.papel_admin or convite.papel_autor or convite.papel_revisor:
        vincular_autor_para_usuario(
            usuario,
            email=convite.email,
            username_sugerido=convite.username_sugerido or usuario.username,
            nome=nome or usuario.first_name or usuario.username,
        )
    return perfil
