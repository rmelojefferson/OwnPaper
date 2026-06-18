import secrets
import string

from django import forms
from django_otp import devices_for_user
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice
from wagtail.admin.forms.auth import PasswordChangeForm


def validar_token_2fa_conta(user, token):
    codigo = (token or "").strip().replace(" ", "")
    if not codigo:
        return False, "Informe o código do autenticador para trocar a senha."

    dispositivos = list(devices_for_user(user, confirmed=True))
    if not dispositivos:
        return (
            False,
            "Você precisa configurar o autenticador em duas etapas para trocar a senha.",
        )

    for dispositivo in dispositivos:
        if dispositivo.verify_token(codigo):
            return True, ""

    return False, "Código do autenticador inválido."


def gerar_codigos_recuperacao(user, quantidade=10):
    dispositivo, _ = StaticDevice.objects.get_or_create(
        user=user,
        name="backup-codes",
        defaults={"confirmed": True},
    )
    if not dispositivo.confirmed:
        dispositivo.confirmed = True
        dispositivo.save(update_fields=["confirmed"])

    dispositivo.token_set.all().delete()

    codigos = []
    for _ in range(max(1, int(quantidade))):
        codigo = "".join(secrets.choice(string.digits) for _ in range(10))
        StaticToken.objects.create(device=dispositivo, token=codigo)
        codigos.append(codigo)
    return codigos


def usuario_tem_totp(user):
    return TOTPDevice.objects.filter(user=user, confirmed=True).exists()


def total_backup_codes(user):
    backup_device = StaticDevice.objects.filter(user=user, confirmed=True).first()
    return backup_device.token_set.count() if backup_device else 0


class OwnPaperPasswordChangeForm(PasswordChangeForm):
    token_2fa = forms.CharField(
        label="Código do autenticador (2FA)",
        required=False,
        help_text="Obrigatório para alterar a senha no painel.",
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        if self.errors:
            return cleaned_data

        token_valido, mensagem = validar_token_2fa_conta(
            self.user,
            cleaned_data.get("token_2fa"),
        )
        if not token_valido:
            self.add_error("token_2fa", mensagem)
        return cleaned_data


    def save(self, commit=True):
        user = super().save(commit=commit)
        from conteudo.audit import registrar_auditoria

        registrar_auditoria(
            request=None,
            usuario=self.user,
            acao="usuario_trocou_senha",
            alvo=self.user,
            detalhes="Senha alterada na conta nativa com validação de 2FA.",
        )
        return user


class BackupCodesAccountForm(forms.Form):
    senha_atual = forms.CharField(
        label="Senha atual",
        widget=forms.PasswordInput,
        required=True,
    )
    token_2fa = forms.CharField(
        label="Código atual do autenticador (2FA)",
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
            }
        ),
        required=True,
    )

    def __init__(self, user, request=None, *args, **kwargs):
        self.user = user
        self.request = request
        super().__init__(*args, **kwargs)

    def clean_senha_atual(self):
        senha = self.cleaned_data["senha_atual"]
        if not self.user.check_password(senha):
            raise forms.ValidationError("A senha atual informada está incorreta.")
        return senha

    def clean(self):
        cleaned_data = super().clean()
        if self.errors:
            return cleaned_data

        if not usuario_tem_totp(self.user):
            self.add_error(
                "token_2fa",
                "Configure o autenticador principal (TOTP) antes de gerar backup codes.",
            )
            return cleaned_data

        token_valido, mensagem = validar_token_2fa_conta(
            self.user,
            cleaned_data.get("token_2fa"),
        )
        if not token_valido:
            self.add_error("token_2fa", mensagem)
        return cleaned_data

    def save(self):
        codigos = gerar_codigos_recuperacao(self.user, quantidade=10)
        if self.request is not None:
            self.request.session["backup_codes_gerados"] = codigos
            from conteudo.audit import registrar_auditoria

            registrar_auditoria(
                request=self.request,
                acao="usuario_regenerou_backup_codes_2fa",
                alvo=self.user,
                detalhes="Regenerou 10 códigos de recuperação do 2FA na conta nativa.",
            )
        return codigos
