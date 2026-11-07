from .development import *

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': RUNTIME_DIR / 'testing.sqlite3',
                         'OPTIONS': {'timeout': 20, 'transaction_mode': 'IMMEDIATE'}}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.PBKDF2PasswordHasher']
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
ENVIRONMENT_LABEL = 'Pruebas automatizadas'
