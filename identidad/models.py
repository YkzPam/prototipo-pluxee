from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from config.encrypted_fields import EncryptedCharField, EncryptedEmailField


class User(AbstractUser):
    password = EncryptedCharField(_('password'), max_length=128)
    first_name = EncryptedCharField(_('first name'), max_length=150, blank=True)
    last_name = EncryptedCharField(_('last name'), max_length=150, blank=True)
    email = EncryptedEmailField(_('email address'), max_length=254, blank=True)
    must_change_password = models.BooleanField(default=False)
