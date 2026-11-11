from .base import *
from django.core.management.utils import get_random_secret_key

SECRET_KEY = get_random_secret_key()
DATA_ENCRYPTION_KEY = os.urandom(32)
WHITENOISE_USE_FINDERS = True
STORAGES['staticfiles'] = {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:',
                         'OPTIONS': {'timeout': 20, 'transaction_mode': 'IMMEDIATE'}}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.PBKDF2PasswordHasher']
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
ENVIRONMENT_LABEL = 'Pruebas automatizadas'

# Las pruebas no imprimen una línea por petición.
LOGGING['loggers']['beneficios.peticiones']['level'] = 'WARNING'
