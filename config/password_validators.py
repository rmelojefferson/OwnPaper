import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class StrongPasswordValidator:
    def validate(self, password, user=None):
        if not re.search(r"[A-Z]", password or ""):
            raise ValidationError(
                _("A senha deve conter pelo menos uma letra maiúscula."),
                code="password_no_upper",
            )
        if not re.search(r"[a-z]", password or ""):
            raise ValidationError(
                _("A senha deve conter pelo menos uma letra minúscula."),
                code="password_no_lower",
            )
        if not re.search(r"\d", password or ""):
            raise ValidationError(
                _("A senha deve conter pelo menos um número."),
                code="password_no_number",
            )
        if not re.search(r"[^A-Za-z0-9]", password or ""):
            raise ValidationError(
                _("A senha deve conter pelo menos um caractere especial."),
                code="password_no_special",
            )

    def get_help_text(self):
        return (
            "A senha deve ter letra maiúscula, minúscula, número e caractere especial."
        )
