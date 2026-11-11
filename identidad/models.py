from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.crypto import salted_hmac
from django.utils.translation import gettext_lazy as _

from config.encrypted_fields import EncryptedCharField, EncryptedEmailField


class User(AbstractUser):
    is_staff = models.BooleanField(
        _('staff status'), default=False, db_default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )
    is_superuser = models.BooleanField(
        _('superuser status'), default=False, db_default=False,
        help_text=_('Designates that this user has all permissions without explicitly assigning them.'),
    )
    password = EncryptedCharField(_('password'), max_length=128)
    first_name = EncryptedCharField(_('first name'), max_length=150, blank=True)
    last_name = EncryptedCharField(_('last name'), max_length=150, blank=True)
    email = EncryptedEmailField(_('email address'), max_length=254, blank=True)
    must_change_password = models.BooleanField(default=False)
    access_revision = models.PositiveIntegerField(default=0, db_default=0)

    def _get_session_auth_hash(self, secret=None):
        if self.access_revision == 0:
            return super()._get_session_auth_hash(secret)
        return salted_hmac(
            'identidad.User.session_access', f'{self.password}:{self.access_revision}',
            secret=secret, algorithm='sha256',
        ).hexdigest()
