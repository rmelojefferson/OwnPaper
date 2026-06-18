from django.contrib.auth import get_user_model

from .models import AuditLog


def _ip_da_requisicao(request):
    if not request:
        return ""
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def registrar_auditoria(
    *,
    acao,
    request=None,
    usuario=None,
    alvo=None,
    detalhes="",
):
    User = get_user_model()
    user = usuario
    if user is None and request is not None and getattr(request, "user", None):
        request_user = request.user
        if request_user.is_authenticated:
            user = request_user

    alvo_tipo = ""
    alvo_id = ""
    alvo_repr = ""
    if alvo is not None:
        meta = getattr(alvo, "_meta", None)
        if meta:
            alvo_tipo = f"{meta.app_label}.{meta.model_name}"
        alvo_pk = getattr(alvo, "pk", None)
        if alvo_pk is not None:
            alvo_id = str(alvo_pk)
        alvo_repr = str(alvo)[:255]

    usuario_id_ref = None
    usuario_email = ""
    usuario_username = ""
    if isinstance(user, User):
        usuario_id_ref = user.pk
        usuario_email = (getattr(user, "email", "") or "")[:254]
        usuario_username = (getattr(user, "username", "") or "")[:150]

    AuditLog.objects.create(
        usuario=user if isinstance(user, User) else None,
        usuario_id_ref=usuario_id_ref,
        usuario_email=usuario_email,
        usuario_username=usuario_username,
        acao=(acao or "").strip()[:80],
        alvo_tipo=alvo_tipo[:120],
        alvo_id=alvo_id[:64],
        alvo_repr=alvo_repr,
        ip=_ip_da_requisicao(request)[:64],
        detalhes=(detalhes or "").strip(),
    )
