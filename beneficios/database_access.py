"""Selección explícita del rol de lectura, sin cambiar la conexión de escritura."""
from django.conf import settings


def read_alias():
    return 'consulta' if 'consulta' in settings.DATABASES else 'default'
