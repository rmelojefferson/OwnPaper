from django.contrib.auth.models import Group, Permission


AUTHOR_GROUP_NAME = "Autores / Escritores"
REVIEWER_GROUP_NAME = "Revisores"
CONTACT_OPERATORS_GROUP_NAME = "Operadores / Atendimento"


def ensure_staff_group(name):
    group, _ = Group.objects.get_or_create(name=name)
    perm = Permission.objects.filter(
        content_type__app_label="wagtailadmin",
        codename="access_admin",
    ).first()
    if perm:
        group.permissions.add(perm)
    return group


def ensure_role_groups():
    for group_name in [
        AUTHOR_GROUP_NAME,
        REVIEWER_GROUP_NAME,
        CONTACT_OPERATORS_GROUP_NAME,
    ]:
        ensure_staff_group(group_name)
