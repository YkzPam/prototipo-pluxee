from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class PasswordCompositionValidator:
    def validate(self, password, user=None):
        if not (any(c.isalpha() for c in password) and any(c.isdigit() for c in password)
                and any(not c.isalnum() and not c.isspace() for c in password)):
            raise ValidationError(_('La contraseña debe combinar letras, números y un símbolo.'), code='password_composition')

    def get_help_text(self):
        return 'Debe combinar letras, números y al menos un símbolo.'


# Caracteres que la pauta OWASP del curso pide rechazar en los datos de entrada, más el carácter nulo.
DANGEROUS_CHARACTERS = frozenset('<>"\'%()&+' + chr(92) + chr(0))
DANGEROUS_MESSAGE = 'No se admiten los caracteres < > " \' % ( ) & + ' + chr(92) + ' en este campo.'


def reject_dangerous_characters(value):
    if any(character in DANGEROUS_CHARACTERS for character in value):
        raise ValidationError(DANGEROUS_MESSAGE, code='dangerous_characters')
