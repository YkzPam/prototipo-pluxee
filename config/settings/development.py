"""Demostración local: solo loopback, cuentas ficticias, sin TLS acreditado."""
from .base import *
from django.core.management.utils import get_random_secret_key

SECRET_FILE = RUNTIME_DIR / 'development.key'
if not SECRET_FILE.exists():
    SECRET_FILE.write_text(get_random_secret_key(), encoding='utf-8')
    SECRET_FILE.chmod(0o600)
SECRET_KEY = SECRET_FILE.read_text(encoding='utf-8').strip()
DEBUG = False
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '[::1]']
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
STORAGES['staticfiles'] = {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
ENVIRONMENT_LABEL = 'Demostración local'
