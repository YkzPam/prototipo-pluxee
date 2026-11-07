"""Cifrado autenticado de campos persistidos por el ORM."""

from base64 import b64decode, urlsafe_b64encode
from binascii import Error as Base64Error
from secrets import token_bytes

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django import forms
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import DataError, models


_PREFIX = 'enc:v1:'
_NONCE_SIZE = 12
_TAG_SIZE = 16
_MAX_AMOUNT = 2_147_483_647


def _cipher():
    key = getattr(settings, 'DATA_ENCRYPTION_KEY', None)
    if not isinstance(key, bytes) or len(key) != 32:
        raise ImproperlyConfigured('Se requiere una clave de cifrado de datos de 32 bytes.')
    return AESGCM(key)


class _EncryptedField:
    def get_internal_type(self):
        return 'TextField'

    def _associated_data(self):
        return f'pluxee:v1:{self.model._meta.label_lower}.{self.name}'.encode('ascii')

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None:
            return None

        plaintext = str(self.to_python(value)).encode('utf-8')
        nonce = token_bytes(_NONCE_SIZE)
        ciphertext = _cipher().encrypt(nonce, plaintext, self._associated_data())
        return _PREFIX + urlsafe_b64encode(nonce + ciphertext).decode('ascii')

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None

        try:
            if not isinstance(value, str) or not value.startswith(_PREFIX):
                raise ValueError
            payload = b64decode(value[len(_PREFIX):], altchars=b'-_', validate=True)
            if len(payload) < _NONCE_SIZE + _TAG_SIZE:
                raise ValueError
            plaintext = _cipher().decrypt(
                payload[:_NONCE_SIZE], payload[_NONCE_SIZE:], self._associated_data()
            )
            return self.to_python(plaintext.decode('utf-8'))
        except (ValueError, Base64Error, InvalidTag, ValidationError):
            raise DataError('No se pudo verificar un campo cifrado.') from None

    def get_lookup(self, lookup_name):
        if lookup_name != 'isnull':
            return None
        return super().get_lookup(lookup_name)


class EncryptedCharField(_EncryptedField, models.CharField):
    pass


class EncryptedEmailField(_EncryptedField, models.EmailField):
    pass


class EncryptedIntegerField(_EncryptedField, models.Field):
    empty_strings_allowed = False

    def __init__(self, *args, min_value=0, **kwargs):
        self.min_value = min_value
        super().__init__(*args, **kwargs)

    @property
    def default_validators(self):
        return [MinValueValidator(self.min_value), MaxValueValidator(_MAX_AMOUNT)]

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.min_value:
            kwargs['min_value'] = self.min_value
        return name, path, args, kwargs

    def to_python(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                raise ValidationError('El monto debe ser un número entero.') from None
        if type(value) is not int or not self.min_value <= value <= _MAX_AMOUNT:
            raise ValidationError('El monto está fuera del rango permitido.')
        return value

    def formfield(self, **kwargs):
        defaults = {
            'form_class': forms.IntegerField,
            'min_value': self.min_value,
            'max_value': _MAX_AMOUNT,
        }
        return super().formfield(**{**defaults, **kwargs})
