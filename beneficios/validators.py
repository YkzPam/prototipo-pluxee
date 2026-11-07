from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class PasswordCompositionValidator:
    def validate(self, password, user=None):
        if not (any(c.isalpha() for c in password) and any(c.isdigit() for c in password)
                and any(not c.isalnum() and not c.isspace() for c in password)):
            raise ValidationError(_('La contraseña debe combinar letras, números y un símbolo.'), code='password_composition')

    def get_help_text(self):
        return 'Debe combinar letras, números y al menos un símbolo.'
