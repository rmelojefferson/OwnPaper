from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from wagtail.signals import page_published


@receiver(pre_save, sender=get_user_model())
def bloquear_username_admin(sender, instance, **kwargs):
    username = (instance.username or "").strip().lower()
    if username != "admin":
        return

    if not instance.pk:
        raise ValidationError("O nome de usuário 'admin' é reservado e não pode ser usado.")

    atual = sender.objects.filter(pk=instance.pk).values_list("username", flat=True).first()
    if (atual or "").strip().lower() != "admin":
        raise ValidationError("O nome de usuário 'admin' é reservado e não pode ser usado.")


@receiver(page_published)
def marcar_publicacao_como_publicada(sender, instance, **kwargs):
    from conteudo.models import PublicacaoPage

    publicacao = instance.specific
    if not isinstance(publicacao, PublicacaoPage):
        return

    PublicacaoPage.objects.filter(pk=publicacao.pk).update(
        status_editorial=PublicacaoPage.STATUS_EDITORIAL_PUBLICADO,
        publicado_em=timezone.now(),
        reabertura_solicitada=False,
    )
