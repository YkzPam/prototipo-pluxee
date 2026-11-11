"""Demostración HTTPS con las conexiones MySQL limitadas."""
from .base import *
from .database_secure import build_databases
from config.vault import load_vault, require_application_secrets

_vault = load_vault()
SECRET_KEY, DATA_ENCRYPTION_KEY = require_application_secrets(_vault)
DATABASES = build_databases(_vault)
del _vault
DEBUG = False
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_NAME = '__Host-pluxee_portal_session'
CSRF_COOKIE_NAME = '__Host-pluxee_portal_csrf'
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_DOMAIN = None
CSRF_COOKIE_PATH = '/'
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_REFERRER_POLICY = 'same-origin'
ENVIRONMENT_LABEL = 'Demostración local HTTPS'
