from django.conf import settings
from django.db import migrations
from django.utils.text import slugify


def _slug_autor_unico(Autor, base, user_id):
    candidato_base = slugify(base or "") or f"usuario-{user_id}"
    candidato = candidato_base
    indice = 2
    while Autor.objects.filter(username=candidato).exists():
        candidato = f"{candidato_base}-{indice}"
        indice += 1
    return candidato


def vincular_revisores_sem_autor(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Autor = apps.get_model("conteudo", "Autor")

    revisores = (
        User.objects.filter(is_active=True, groups__name="Revisores")
        .exclude(autor_vinculado__isnull=False)
        .distinct()
    )
    for user in revisores:
        nome = " ".join(
            [
                (getattr(user, "first_name", "") or "").strip(),
                (getattr(user, "last_name", "") or "").strip(),
            ]
        ).strip() or (getattr(user, "username", "") or "").strip() or f"usuario-{user.pk}"
        Autor.objects.create(
            nome_completo=nome,
            nome_exibicao=nome,
            username=_slug_autor_unico(Autor, getattr(user, "username", "") or nome, user.pk),
            email=(getattr(user, "email", "") or "").strip(),
            usuario_admin_id=user.pk,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("conteudo", "0109_backfill_fluxo_editorial_e_papeis"),
    ]

    operations = [
        migrations.RunPython(vincular_revisores_sem_autor, migrations.RunPython.noop),
    ]
