"""Perfil HTTPS para una demostración desplegada, no una integración empresarial."""
from .base import *
from django.core.exceptions import ImproperlyConfigured

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY requiere una clave externa de al menos 50 caracteres.')
ALLOWED_HOSTS = [x.strip() for x in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if x.strip()]
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Definir DJANGO_ALLOWED_HOSTS con los hosts exactos de la demostración.')
DEBUG = False
DATABASES['default']['NAME'] = os.environ.get('PLUXEE_DB', str(RUNTIME_DIR / 'demonstration.sqlite3'))
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_REFERRER_POLICY = 'same-origin'
ENVIRONMENT_LABEL = 'Demostración HTTPS'
# Activar solo si el proxy local de confianza elimina el encabezado recibido del cliente.
if os.environ.get('TRUST_LOCAL_HTTPS_PROXY') == '1':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
