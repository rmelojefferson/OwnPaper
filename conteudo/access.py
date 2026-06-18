from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Q

from .roles import (
    AUTHOR_GROUP_NAME,
    CONTACT_OPERATORS_GROUP_NAME,
    REVIEWER_GROUP_NAME,
)


def _in_group(user, group_name):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return user.groups.filter(name=group_name).exists()


def is_admin(user):
    return bool(user and getattr(user, "is_authenticated", False) and user.is_staff and user.is_superuser)


def is_author(user):
    if is_admin(user):
        return True
    return _in_group(user, AUTHOR_GROUP_NAME)


def is_reviewer(user):
    if is_admin(user):
        return True
    return _in_group(user, REVIEWER_GROUP_NAME)


def is_operator(user):
    if is_admin(user):
        return True
    return _in_group(user, CONTACT_OPERATORS_GROUP_NAME)


def can_access_admin_basic(user):
    return bool(user and getattr(user, "is_authenticated", False) and user.is_staff)


def can_access_publications(user):
    return can_access_admin_basic(user) and (is_admin(user) or is_author(user) or is_reviewer(user))


def can_access_contact(user):
    return can_access_admin_basic(user) and (is_admin(user) or is_operator(user))


def can_manage_site_settings(user):
    return is_admin(user)


def get_panel_profile(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        return user.painel_perfil
    except Exception:
        return None


def can_publish_direct(user):
    if is_admin(user):
        return True
    perfil = get_panel_profile(user)
    return bool(perfil and perfil.pode_publicar_direto)


def eligible_contact_assignees():
    User = get_user_model()
    role_groups = Group.objects.filter(name=CONTACT_OPERATORS_GROUP_NAME)
    return (
        User.objects.filter(is_active=True)
        .filter(is_staff=True)
        .filter(Q(is_superuser=True) | Q(groups__in=role_groups))
        .distinct()
        .order_by("username")
    )


def public_editorial_roles_for_user(user):
    if not user:
        return []
    roles = []
    if is_author(user):
        roles.append("Autor")
    if is_reviewer(user):
        roles.append("Revisor")
    return roles
