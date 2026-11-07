"""Demostración local: solo loopback, cuentas ficticias, sin TLS acreditado."""
from .base import *
from config.vault import prepare_application_secrets, require_application_secrets

SECRET_KEY, DATA_ENCRYPTION_KEY = require_application_secrets(prepare_application_secrets())
DEBUG = False
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '[::1]']
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
STORAGES['staticfiles'] = {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
ENVIRONMENT_LABEL = 'Demostración local'
