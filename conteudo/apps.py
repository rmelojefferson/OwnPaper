from django.apps import AppConfig


class ConteudoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'conteudo'

    def ready(self):
        from . import signals  # noqa: F401
        from django import forms
        from wagtail.admin.views.account import ChangePasswordPanel, ThemeSettingsPanel
        from wagtail.users.models import UserProfile
        from conteudo.account_security import OwnPaperPasswordChangeForm

        class OwnPaperThemePreferencesForm(forms.ModelForm):
            class Meta:
                model = UserProfile
                fields = ["theme"]

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields["theme"].label = "Tema do painel"

        ThemeSettingsPanel.title = "Tema e zoom"
        ThemeSettingsPanel.form_class = OwnPaperThemePreferencesForm
        ChangePasswordPanel.form_class = OwnPaperPasswordChangeForm
